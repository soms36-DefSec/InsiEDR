import os
import sys
import numpy as np
import pandas as pd
import torch
import joblib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from latest_data.check_insider import LatestInferenceEngine

models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
dataset_path = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"

df = pd.read_csv(dataset_path)
user_df = df[df["user"] == "U0160"].sort_values("date")
engine = LatestInferenceEngine(models_dir=models_dir)

exclude_cols = [
    "user", "date", "label", "is_insider", "threat_scenario",
    "logon_risk", "file_risk", "device_risk", "http_risk", "overall_risk",
    "raw_overall_risk", "daily_risk_delta", "daily_risk_rolling_mean_7d", "daily_risk_rolling_std_7d",
    "rf_normal_prob", "rf_email_exfil_prob", "rf_sabotage_prob", "rf_usb_exfil_prob", "rf_flight_risk_prob", "rf_cloud_exfil_prob",
    "scenario_risk", "rvfl_risk"
]

daily_sequence = []
for row in user_df.itertuples():
    features = {col: float(getattr(row, col)) for col in user_df.columns if col not in exclude_cols}
    payload = {"features": features}
    risk_result = engine.predict_current_risk(payload)
    
    features["logon_risk"] = risk_result["domain_scores"]["logon"]
    features["file_risk"] = risk_result["domain_scores"]["file"]
    features["device_risk"] = risk_result["domain_scores"]["device"]
    features["http_risk"] = risk_result["domain_scores"]["http"]
    features["overall_risk"] = risk_result["overall_score"]
    features["raw_overall_risk"] = risk_result["raw_overall_score"]
    
    prev_overall_risks = [day["overall_risk"] for day in daily_sequence]
    if len(prev_overall_risks) > 0:
        features["daily_risk_delta"] = risk_result["overall_score"] - prev_overall_risks[-1]
    else:
        features["daily_risk_delta"] = 0.0
        
    all_overall_risks = prev_overall_risks + [risk_result["overall_score"]]
    recent_7d = all_overall_risks[-7:]
    features["daily_risk_rolling_mean_7d"] = np.mean(recent_7d)
    features["daily_risk_rolling_std_7d"] = np.std(recent_7d) if len(recent_7d) > 1 else 0.0
    
    scenario_result = engine.predict_scenario(payload)
    
    daily_sequence.append({
        "overall_risk": risk_result["overall_score"],
        "rf_email_exfil_prob": scenario_result["rf_email_exfil_prob"],
        "rf_sabotage_prob": scenario_result["rf_sabotage_prob"],
        "rf_usb_exfil_prob": scenario_result["rf_usb_exfil_prob"],
        "rf_flight_risk_prob": scenario_result["rf_flight_risk_prob"],
        "rf_cloud_exfil_prob": scenario_result["rf_cloud_exfil_prob"]
    })

# Check the error on the very last day
seq_len = 7
sub_seq = daily_sequence[-8:]
sub_payload = {
    "payload_id": "SUB",
    "username": "U0160",
    "hostname": "SUB",
    "daily_sequence": sub_seq
}

# Run print inside predict_behavioral_risk
rvfl_values = []
for day in sub_seq:
    overall_risk = float(day["overall_risk"])
    scenario_risk = max(
        float(day.get("rf_email_exfil_prob", 0)),
        float(day.get("rf_sabotage_prob", 0)),
        float(day.get("rf_usb_exfil_prob", 0)),
        float(day.get("rf_flight_risk_prob", 0)),
        float(day.get("rf_cloud_exfil_prob", 0))
    )
    rvfl_risk = engine.if_weight * overall_risk + engine.xgb_weight * scenario_risk
    rvfl_values.append([rvfl_risk])
    
features_array = np.array(rvfl_values, dtype=np.float32)
X_seq = features_array[:seq_len]
y_actual = features_array[seq_len:]

X_flat_scaled = engine.feature_scaler.transform(X_seq.reshape(-1, 1)).reshape(X_seq.shape)
y_actual_scaled = engine.target_scaler.transform(y_actual.reshape(-1, 1))

print(f"X_seq raw:\n{X_seq}")
print(f"X_flat_scaled:\n{X_flat_scaled}")
print(f"y_actual raw: {y_actual}")
print(f"y_actual_scaled: {y_actual_scaled}")

X_tensor = torch.tensor(X_flat_scaled, dtype=torch.float32).unsqueeze(0)
y_pred_scaled = engine.rvfl_orchestrator.predict(X_tensor, engine.ridge_models)
print(f"y_pred_scaled: {y_pred_scaled}")

error = float(np.mean(np.square(y_actual_scaled - y_pred_scaled)))
print(f"error (scaled space): {error}")
