import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

TRAILING_WINDOW_DAYS = 10

SCENARIO_MAP = {
    "normal": 0,
    "email_exfil": 1,
    "sabotage": 2,
    "usb_exfil": 3,
    "flight_risk": 4,
    "cloud_exfil": 5
}

REVERSE_SCENARIO_MAP = {v: k for k, v in SCENARIO_MAP.items()}

def create_labels(feature_df, labels_df, trailing_days=10):
    """
    Labels user-day features:
    - Normal users (is_insider == 0) -> Class 0 (Normal) for all days.
    - Insider users (is_insider == 1) -> Class 1-5 for their last 'trailing_days' active days.
    - Excludes other days of insider users from training/evaluation.
    """
    df = feature_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # Merge with insider labels
    df = df.merge(labels_df, left_on="user", right_on="user_id", how="left")
    
    # Set default label to -1 (to be excluded)
    df["label"] = -1
    
    # 1. Label Normal users' days as Class 0
    df.loc[df["is_insider"] == 0, "label"] = 0
    
    # 2. Label Insider users' trailing days
    insider_users = labels_df[labels_df["is_insider"] == 1]["user_id"].unique()
    
    for user in insider_users:
        user_mask = df["user"] == user
        user_rows = df[user_mask].sort_values("date")
        
        if len(user_rows) == 0:
            continue
            
        scenario = user_rows.iloc[0]["threat_scenario"]
        class_label = SCENARIO_MAP[scenario]
        
        # Get indices of the trailing N days
        trailing_indices = user_rows.index[-trailing_days:]
        df.loc[trailing_indices, "label"] = class_label
        
    return df

def stratified_user_split(labels_df, test_size=0.2, random_state=42):
    """
    Performs 80/20 train/test split on users, stratified by their threat_scenario.
    Ensures that every class has representation in both splits.
    """
    state = np.random.RandomState(random_state)
    train_users = []
    test_users = []
    
    for scenario, group in labels_df.groupby("threat_scenario"):
        users = list(group["user_id"].unique())
        state.shuffle(users)
        
        split_idx = int(len(users) * (1 - test_size))
        # Ensure at least 1 user in test if possible
        if len(users) > 1 and split_idx == len(users):
            split_idx = len(users) - 1
            
        train_users.extend(users[:split_idx])
        test_users.extend(users[split_idx:])
        
    return train_users, test_users

def train_xgb_classifier(features_csv_path, labels_csv_path, output_features_path, models_dir):
    """
    Prepares training set with SMOTE, splits users, trains XGBoost,
    evaluates it, and predicts probabilities for all records.
    """
    print(f"Loading enriched features from '{features_csv_path}'...")
    feature_df = pd.read_csv(features_csv_path)
    feature_df["date"] = pd.to_datetime(feature_df["date"])
    
    print(f"Loading insider labels from '{labels_csv_path}'...")
    labels_df = pd.read_csv(labels_csv_path)
    
    # Step 1: Create training labels with trailing window approach
    labeled_df = create_labels(feature_df, labels_df, trailing_days=TRAILING_WINDOW_DAYS)
    
    # Print sample counts of the full labeled set (excluding -1)
    valid_labeled = labeled_df[labeled_df["label"] != -1]
    print("\nFull Labeled Dataset Distribution (for XGB training/testing):")
    print(valid_labeled["label"].value_counts().sort_index().rename(index=REVERSE_SCENARIO_MAP))
    
    # Step 2: Split by user (Stratified Group Split)
    train_users, test_users = stratified_user_split(labels_df, test_size=0.2, random_state=42)
    print(f"\nUser Split: {len(train_users)} Train Users, {len(test_users)} Test Users")
    
    train_df = valid_labeled[valid_labeled["user"].isin(train_users)].copy()
    test_df = valid_labeled[valid_labeled["user"].isin(test_users)].copy()
    
    # Print sample counts after split
    print("\nTrain Split Label Distribution:")
    train_dist = train_df["label"].value_counts().sort_index()
    print(train_dist.rename(index=REVERSE_SCENARIO_MAP))
    
    print("\nTest Split Label Distribution:")
    test_dist = test_df["label"].value_counts().sort_index()
    print(test_dist.rename(index=REVERSE_SCENARIO_MAP))
    
    # Check for empty classes in test split and warn explicitly
    for c in range(6):
        if c not in test_dist or test_dist[c] == 0:
            print(f"⚠️ WARNING: Class '{REVERSE_SCENARIO_MAP[c]}' (Class {c}) has ZERO samples in the test split!")
            
    # Prepare feature columns for training
    exclude_cols = ["user", "date", "user_id", "is_insider", "threat_scenario", "label"]
    feature_cols = [c for c in train_df.columns if c not in exclude_cols]
    
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df["label"]
    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df["label"]
    
    # Step 3: Apply SMOTE on minority classes 1-5 (in training set only)
    print("\nApplying SMOTE to balance minority classes 1-5...")
    class_0_count = int(train_dist[0])
    
    # Define sampling strategy: oversample classes 1-5 to class 0 size
    sampling_strategy = {c: class_0_count for c in range(1, 6)}
    
    smote = SMOTE(
        sampling_strategy=sampling_strategy,
        random_state=42,
        k_neighbors=3
    )
    
    X_train_smote, y_train_smote = smote.fit_resample(X_train, y_train)
    print("Class distribution after SMOTE:")
    print(y_train_smote.value_counts().sort_index().rename(index=REVERSE_SCENARIO_MAP))
    
    # Step 4: Train XGBoost Classifier
    print("\nTraining XGBoost Classifier...")
    model = XGBClassifier(
        objective="multi:softprob",
        num_class=6,
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        eval_metric="mlogloss"
    )
    
    model.fit(X_train_smote, y_train_smote)
    
    # Evaluate model
    predictions = model.predict(X_test)
    print("\n" + "=" * 80)
    print("XGBOOST CLASSIFICATION REPORT")
    print("=" * 80)
    print(classification_report(y_test, predictions, target_names=[REVERSE_SCENARIO_MAP[i] for i in range(6)], digits=4))
    
    print("\nCONFUSION MATRIX:")
    print(confusion_matrix(y_test, predictions))
    
    # Save model and features JSON
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, "scenario_xgb.pkl")
    features_json_path = os.path.join(models_dir, "scenario_xgb_features.json")
    
    joblib.dump(model, model_path)
    with open(features_json_path, "w") as f:
        json.dump(feature_cols, f, indent=4)
        
    print(f"\nSaved XGBoost model to '{model_path}'")
    print(f"Saved feature list to '{features_json_path}'")
    
    # Step 5: Predict probabilities for ALL rows in dataset
    print("\nGenerating probability features for all records...")
    all_X = feature_df[feature_cols].fillna(0)
    probabilities = model.predict_proba(all_X)
    
    # Add probability columns
    output_df = feature_df.copy()
    for c in range(6):
        prob_col = f"rf_{REVERSE_SCENARIO_MAP[c]}_prob"
        output_df[prob_col] = probabilities[:, c]
        
    # Also attach ground truth label column for clarity
    # Join with labels_df again to get is_insider and threat_scenario
    output_df = output_df.merge(labels_df, left_on="user", right_on="user_id", how="left").drop(columns=["user_id"])
    
    # Save enriched dataset
    output_df.to_csv(output_features_path, index=False)
    print(f"Saved enriched dataset with probabilities to '{output_features_path}' (Shape: {output_df.shape})")
    
    return model, feature_cols, test_users

if __name__ == "__main__":
    features_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\if_enriched_features.csv"
    labels_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\OUTPUT_LABELS\insider_labels.csv"
    output_features = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"
    models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
    train_xgb_classifier(features_csv, labels_csv, output_features, models_dir)
