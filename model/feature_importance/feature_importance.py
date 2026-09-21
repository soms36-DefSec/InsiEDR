import os
import sys
import json
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
latest_data_dir = os.path.join(project_root, "latest_data")
features_csv_path = os.path.join(latest_data_dir, "if_enriched_features.csv")
labels_csv_path = os.path.join(project_root, "INPUT_LOGS", "OUTPUT_LABELS", "insider_labels.csv")
output_dir = os.path.join(os.path.dirname(__file__), "outputs")

os.makedirs(output_dir, exist_ok=True)

# 1. Load Data
print("Loading data...")
feature_df = pd.read_csv(features_csv_path)
feature_df["date"] = pd.to_datetime(feature_df["date"])
labels_df = pd.read_csv(labels_csv_path)

# 2. Assign Labels (10-day trailing window logic)
print("Assigning labels...")
df = feature_df.copy()
df = df.merge(labels_df, left_on="user", right_on="user_id", how="left")
df["label"] = -1
df.loc[df["is_insider"] == 0, "label"] = 0

trailing_days = 10
insider_users = labels_df[labels_df["is_insider"] == 1]["user_id"].unique()
for user in insider_users:
    user_mask = df["user"] == user
    user_rows = df[user_mask].sort_values("date")
    if len(user_rows) == 0:
        continue
    trailing_indices = user_rows.index[-trailing_days:]
    df.loc[trailing_indices, "label"] = 1

valid_df = df[df["label"] != -1].copy()

# 3. Stratified Split by User
print("Splitting data...")
# Extract user and their insider status
user_status = labels_df.drop_duplicates(subset=["user_id"])[["user_id", "threat_scenario"]]
train_users, test_users = train_test_split(
    user_status["user_id"], 
    test_size=0.2, 
    random_state=42, 
    stratify=user_status["threat_scenario"]
)

train_df = valid_df[valid_df["user"].isin(train_users)].copy()
test_df = valid_df[valid_df["user"].isin(test_users)].copy()

features = ["file_risk", "http_risk", "logon_risk", "device_risk"]
X_train = train_df[features].fillna(0)
y_train = train_df["label"]
X_test = test_df[features].fillna(0)
y_test = test_df["label"]

# 4. Train Binary XGBoost Classifier
print("Training model...")
xgb_model = XGBClassifier(
    objective="binary:logistic",
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    random_state=42,
    eval_metric="logloss"
)
xgb_model.fit(X_train, y_train)

# 5. Evaluate Model
print("Evaluating model...")
y_pred = xgb_model.predict(X_test)
y_prob = xgb_model.predict_proba(X_test)[:, 1]

metrics = {
    "Accuracy": float(accuracy_score(y_test, y_pred)),
    "Precision": float(precision_score(y_test, y_pred)),
    "Recall": float(recall_score(y_test, y_pred)),
    "F1_Score": float(f1_score(y_test, y_pred)),
    "ROC_AUC": float(roc_auc_score(y_test, y_prob))
}

with open(os.path.join(output_dir, "model_metrics.json"), "w") as f:
    json.dump(metrics, f, indent=4)

# 6. SHAP Feature Importance
print("Calculating SHAP values...")
explainer = shap.TreeExplainer(xgb_model)
shap_values = explainer.shap_values(X_test)

# Handle possible list output for binary classification in older shap versions
if isinstance(shap_values, list):
    shap_values = shap_values[1] # Take positive class

# Global importance: mean absolute SHAP value
mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

# Normalize
sum_shap = np.sum(mean_abs_shap)
if sum_shap > 0:
    normalized_importance = mean_abs_shap / sum_shap
else:
    normalized_importance = np.array([0.25, 0.25, 0.25, 0.25])

# Save global importance
importance_df = pd.DataFrame({
    "Domain": ["File Risk", "HTTP Risk", "Email Risk (Logon)", "USB Risk (Device)"],
    "Mean_Abs_SHAP": mean_abs_shap,
    "Normalized_Importance": normalized_importance
})
importance_df.to_csv(os.path.join(output_dir, "feature_importance.csv"), index=False)

print("\n--- Normalized Global Feature Importance ---")
for _, row in importance_df.iterrows():
    print(f"{row['Domain']}: {row['Normalized_Importance']:.4%}")

print("\n--- Model Metrics ---")
for k, v in metrics.items():
    print(f"{k}: {v:.4f}")

# Save individual SHAP values
shap_df = pd.DataFrame(shap_values, columns=features)
shap_df["user"] = test_df["user"].values
shap_df["date"] = test_df["date"].values
shap_df["actual_label"] = y_test.values
shap_df["predicted_prob"] = y_prob
shap_df.to_csv(os.path.join(output_dir, "shap_values.csv"), index=False)

# 7. Generate Plots
plt.figure(figsize=(10, 6))
plt.bar(importance_df["Domain"], importance_df["Normalized_Importance"], color='skyblue')
plt.title("Global Feature Importance (Normalized Mean |SHAP|)")
plt.ylabel("Importance")
plt.xlabel("Domain Risk")
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "feature_importance.png"))
plt.close()

plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X_test, feature_names=["File", "HTTP", "Email (Logon)", "USB (Device)"], show=False)
plt.title("SHAP Summary Plot")
plt.tight_layout()
plt.savefig(os.path.join(output_dir, "shap_summary.png"))
plt.close()

print(f"\nAll outputs saved successfully to {output_dir}")
