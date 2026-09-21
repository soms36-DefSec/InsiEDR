import os
import sys
import json
import joblib
import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.linear_model import Ridge, LogisticRegression

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.red_revfl_orchestrator import RedRVFLOrchestrator
from src.run.feature_to_sequence import create_sequences

def train_and_evaluate_rvfl(enriched_csv_path, test_users_list, output_anomaly_csv, output_users_csv, models_dir):
    """
    Step 5: Loads XGBoost probability enriched dataset, builds sequence windows
    separately for Logon, HTTP, Device, and File risk domains, scales features, 
    trains four distinct RedRVFL models via Ridge regression, computes prediction errors,
    aggregates domain scores per user, fits a Logistic Regression fusion model to determine
    feature importance, and outputs final decision scores.
    """
    print(f"Loading enriched dataset from '{enriched_csv_path}'...")
    df = pd.read_csv(enriched_csv_path)
    df["date"] = pd.to_datetime(df["date"])
    
    domains = ["logon", "http", "device", "file"]
    
    # Split users into train and test
    train_users = [u for u in df["user"].unique() if u not in test_users_list]
    test_users = list(test_users_list)
    
    print(f"RVFL Split: {len(train_users)} Train Users, {len(test_users)} Test Users")
    
    daily_errors = {}
    
    # Train separate models and predict for each domain
    for dom in domains:
        col = f"{dom}_risk"
        print(f"\n--- Training RedRVFL for Domain: {dom} ({col}) ---")
        
        # Keep only the columns we need for sequencing
        seq_df = df[["user", "date", col]].copy()
        
        train_df = seq_df[seq_df["user"].isin(train_users)].copy()
        test_df = seq_df[seq_df["user"].isin(test_users)].copy()
        
        # Build sequences (7-day window)
        print(f"Building sequences for {dom} (length=7)...")
        X_train_raw, y_train_raw, metadata_train = create_sequences(train_df, [col], sequence_length=7)
        X_test_raw, y_test_raw, metadata_test = create_sequences(test_df, [col], sequence_length=7)
        X_all_raw, y_all_raw, metadata_all = create_sequences(seq_df, [col], sequence_length=7)
        
        # Scale features
        print(f"Scaling features for {dom}...")
        feature_scaler = MinMaxScaler()
        feature_scaler.fit(X_train_raw.reshape(-1, X_train_raw.shape[2]))
        
        X_train = feature_scaler.transform(X_train_raw.reshape(-1, X_train_raw.shape[2])).reshape(X_train_raw.shape)
        X_all = feature_scaler.transform(X_all_raw.reshape(-1, X_all_raw.shape[2])).reshape(X_all_raw.shape)
        
        target_scaler = MinMaxScaler()
        target_scaler.fit(y_train_raw)
        
        y_train = target_scaler.transform(y_train_raw)
        y_all = target_scaler.transform(y_all_raw)
        
        # Save scalers
        os.makedirs(models_dir, exist_ok=True)
        joblib.dump(feature_scaler, os.path.join(models_dir, f"feature_scaler_{dom}.pkl"))
        joblib.dump(target_scaler, os.path.join(models_dir, f"target_scaler_{dom}.pkl"))
        
        # Train RedRVFL
        print(f"Training RedRVFL Model for {dom} (hidden_size=128, layers=5)...")
        model = RedRVFLOrchestrator(
            input_features=1,
            hidden_size=128,
            num_layers=5
        )
        
        X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
        feature_matrices = model.extract_features(X_train_tensor)
        
        ridge_models = []
        for D in feature_matrices:
            ridge = Ridge(alpha=0.01, solver="lsqr")
            ridge.fit(D, y_train)
            ridge_models.append(ridge)
            
        # Save models
        joblib.dump(model, os.path.join(models_dir, f"rvfl_model_{dom}.pkl"))
        joblib.dump(ridge_models, os.path.join(models_dir, f"rvfl_ridge_models_{dom}.pkl"))
        
        # Predict on ALL sequences to get error timeline
        print(f"Predicting and calculating drift errors for {dom}...")
        X_all_tensor = torch.tensor(X_all, dtype=torch.float32)
        y_pred = model.predict(X_all_tensor, ridge_models)
        
        # Compute MSE prediction error (avoiding 2D/1D broadcasting bug)
        errors = np.square(y_all.ravel() - y_pred.ravel())
        
        # Store prediction errors dynamically
        for err, meta in zip(errors, metadata_all):
            u = meta["user"]
            dt = meta["target_date"]
            key = (u, dt)
            if key not in daily_errors:
                daily_errors[key] = {}
            daily_errors[key][f"error_{dom}"] = float(err)

    # Save daily anomaly error DataFrame
    anomaly_rows = []
    for (u, dt), errs in daily_errors.items():
        row = {
            "user": u,
            "date": dt,
            "error_logon": errs.get("error_logon", 0.0),
            "error_http": errs.get("error_http", 0.0),
            "error_device": errs.get("error_device", 0.0),
            "error_file": errs.get("error_file", 0.0)
        }
        anomaly_rows.append(row)
        
    anomaly_df = pd.DataFrame(anomaly_rows)
    anomaly_df.to_csv(output_anomaly_csv, index=False)
    print(f"\nSaved daily anomaly drift errors to '{output_anomaly_csv}' (Shape: {anomaly_df.shape})")
    
    # Aggregate per-user statistics per domain
    print("Aggregating per-user threat scores per domain...")
    user_scores_list = []
    
    # Calculate anomaly days (sequence predictions per user)
    user_sequence_counts = anomaly_df.groupby("user")["date"].count().to_dict()
    
    for dom in domains:
        col_err = f"error_{dom}"
        agg_df = anomaly_df.groupby("user")[col_err].agg(
            max_err="max",
            mean_err="mean"
        ).reset_index()
        
        # Compute domain score: score_dom = max_err * mean_err * sqrt(days)
        agg_df[f"score_{dom}"] = agg_df.apply(
            lambda r: r["max_err"] * r["mean_err"] * np.sqrt(user_sequence_counts.get(r["user"], 1)),
            axis=1
        )
        user_scores_list.append(agg_df[["user", f"score_{dom}", "max_err", "mean_err"]].rename(
            columns={"max_err": f"max_error_{dom}", "mean_err": f"mean_error_{dom}"}
        ))
        
    # Merge all domain scores into a single user score dataframe
    user_df = user_scores_list[0]
    for other_df in user_scores_list[1:]:
        user_df = user_df.merge(other_df, on="user")
        
    # Attach labels
    labels_df = df[["user", "is_insider", "threat_scenario"]].drop_duplicates()
    user_df = user_df.merge(labels_df, on="user", how="left")
    
    # Train Logistic Regression Fusion Classifier on the training split
    train_users_df = user_df[user_df["user"].isin(train_users)].copy()
    
    feature_cols = [f"score_{dom}" for dom in domains]
    X_train = train_users_df[feature_cols].values
    y_train = train_users_df["is_insider"].values
    
    print("\nTraining Logistic Regression Fusion Classifier...")
    fusion_scaler = StandardScaler()
    X_train_scaled = fusion_scaler.fit_transform(X_train)
    
    fusion_clf = LogisticRegression(penalty="l2", C=1.0, random_state=42)
    fusion_clf.fit(X_train_scaled, y_train)
    
    # Save the fusion scaler and classifier
    joblib.dump(fusion_scaler, os.path.join(models_dir, "fusion_scaler.pkl"))
    joblib.dump(fusion_clf, os.path.join(models_dir, "fusion_classifier.pkl"))
    print("Saved fusion_scaler.pkl and fusion_classifier.pkl to models directory.")
    
    # Extract and display feature importance
    coefs = fusion_clf.coef_[0]
    intercept = fusion_clf.intercept_[0]
    
    # Relative importance = absolute weight / sum of absolute weights
    sum_abs = np.sum(np.abs(coefs))
    importances = np.abs(coefs) / sum_abs if sum_abs > 0 else np.array([0.25]*4)
    
    print("\n" + "=" * 80)
    print("DOMAIN FEATURE IMPORTANCE (Logistic Regression weights)")
    print("=" * 80)
    for dom, weight, imp in zip(domains, coefs, importances):
        print(f"  {dom:<10} Risk Score weight: {weight:+.4f} (Relative Importance: {imp:.2%})")
        
    # Print the exact mathematical decision formula
    means = fusion_scaler.mean_
    stds = fusion_scaler.scale_
    
    formula_parts = []
    for i, dom in enumerate(domains):
        w = coefs[i]
        mu = means[i]
        sigma = stds[i]
        formula_parts.append(f"({w:+.4f} * (S_{dom} - {mu:.6f}) / {sigma:.6f})")
    
    formula_str = f"z = " + " + ".join(formula_parts) + f" {intercept:+.6f}"
    print("\nVALID INSIDER CLASSIFICATION FORMULA:")
    print(formula_str)
    print("Probability of being an Insider: P(Insider) = 1 / (1 + exp(-z))")
    print("=" * 80)
    
    # Calculate final ranking score for all users
    # We will use the predict_proba (probability of class 1) as the final score_v2
    all_X = user_df[feature_cols].values
    all_X_scaled = fusion_scaler.transform(all_X)
    probabilities = fusion_clf.predict_proba(all_X_scaled)[:, 1]
    
    # Assign score_v2 and anomaly_days
    user_df["score_v2"] = probabilities
    user_df["anomaly_days"] = user_df["user"].map(user_sequence_counts)
    
    # For compatibility, create a general max_error and mean_error column from overall average
    user_df["max_error"] = user_df[[f"max_error_{dom}" for dom in domains]].mean(axis=1)
    user_df["mean_error"] = user_df[[f"mean_error_{dom}" for dom in domains]].mean(axis=1)
    
    # Rank users by score_v2 descending
    user_df = user_df.sort_values("score_v2", ascending=False).reset_index(drop=True)
    
    # Save ranked users CSV
    user_df.to_csv(output_users_csv, index=False)
    print(f"\nSaved ranked users by score_v2 to '{output_users_csv}' (Shape: {user_df.shape})")
    
    print("\nTop 10 Suspicious Users under 4-Model RedRVFL Fusion:")
    print(user_df.head(10)[["user", "score_v2", "is_insider", "threat_scenario"]])
    
    # Write/update metadata to models_dir for check_insider.py
    metadata = {
        "input_features": 1,
        "hidden_size": 128,
        "num_layers": 5,
        "sequence_length": 7,
        "domains": domains,
        "intercept": float(intercept),
        "coefs": [float(c) for c in coefs],
        "means": [float(m) for m in means],
        "stds": [float(s) for s in stds]
    }
    with open(os.path.join(models_dir, "rvfl_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
    print("Created rvfl_metadata.json with hyperparameters and coefficients.")
    
    return user_df

if __name__ == "__main__":
    enriched_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"
    dummy_test_users = ["U0001", "U0002"]
    out_anomaly = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\all_anomaly_days.csv"
    out_users = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\top_users.csv"
    models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
    train_and_evaluate_rvfl(enriched_csv, dummy_test_users, out_anomaly, out_users, models_dir)
