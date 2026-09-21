import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import torch
import joblib

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.server.inference import InferenceEngine
from src.server.features.feature_schema import (
    LOGON_FEATURES,
    FILE_FEATURES,
    DEVICE_FEATURES,
    HTTP_FEATURES
)

class LatestInferenceEngine(InferenceEngine):
    """
    Inference Engine wrapper for the latest models.
    Recalibrates overall Isolation Forest score using the new divisor (0.7300)
    and predicts probabilities for the 6 target classes.
    """
    def _load_models(self):
        # Overrides the base method to load the four RedRVFL models and the Logistic Regression fusion classifier
        if_path = os.path.join(self.models_dir, "domain_isolation_forest.pkl")
        metadata_path = os.path.join(self.models_dir, "rvfl_metadata.json")
        columns_path = os.path.join(self.models_dir, "feature_columns_IF.json")
        xgb_model_path = os.path.join(self.models_dir, "scenario_xgb.pkl")
        xgb_features_path = os.path.join(self.models_dir, "scenario_xgb_features.json")
        
        # Load domain isolation forest
        if not os.path.exists(if_path):
            raise FileNotFoundError(f"Persisted Isolation Forest model not found at {if_path}")
        self.domain_if = joblib.load(if_path)
        
        # Load RVFL metadata
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Persisted RVFL metadata not found at {metadata_path}")
        with open(metadata_path, "r") as f:
            self.rvfl_metadata = json.load(f)
            
        # Load feature columns
        if not os.path.exists(columns_path):
            raise FileNotFoundError(f"Persisted feature columns not found at {columns_path}")
        with open(columns_path, "r") as f:
            self.feature_columns = json.load(f)
            
        # Load Scenario XGB model & features
        if not os.path.exists(xgb_model_path):
            raise FileNotFoundError(f"Scenario XGB model not found at {xgb_model_path}")
        self.scenario_model = joblib.load(xgb_model_path)
        
        if not os.path.exists(xgb_features_path):
            raise FileNotFoundError(f"Scenario feature list not found at {xgb_features_path}")
        with open(xgb_features_path, "r") as f:
            self.scenario_features = json.load(f)
            
        # Load the 4 RedRVFL models, target models, and scalers
        self.rvfl_orchestrators = {}
        self.ridge_models = {}
        self.feature_scalers = {}
        self.target_scalers = {}
        
        domains = ["logon", "http", "device", "file"]
        for dom in domains:
            self.feature_scalers[dom] = joblib.load(os.path.join(self.models_dir, f"feature_scaler_{dom}.pkl"))
            self.target_scalers[dom] = joblib.load(os.path.join(self.models_dir, f"target_scaler_{dom}.pkl"))
            self.rvfl_orchestrators[dom] = joblib.load(os.path.join(self.models_dir, f"rvfl_model_{dom}.pkl"))
            self.ridge_models[dom] = joblib.load(os.path.join(self.models_dir, f"rvfl_ridge_models_{dom}.pkl"))
            
        # Load fusion scaler and classifier
        self.fusion_scaler = joblib.load(os.path.join(self.models_dir, "fusion_scaler.pkl"))
        self.fusion_classifier = joblib.load(os.path.join(self.models_dir, "fusion_classifier.pkl"))

    def predict_current_risk(self, payload):
        if "features" not in payload:
            raise ValueError("Missing 'features'")
            
        features = payload["features"]
        
        logon_cols = [c for c in LOGON_FEATURES if c in features]
        file_cols = [c for c in FILE_FEATURES if c in features]
        device_cols = [c for c in DEVICE_FEATURES if c in features]
        http_cols = [c for c in HTTP_FEATURES if c in features]
        
        logon_X = np.array([[features[c] for c in logon_cols]], dtype=np.float32)
        file_X = np.array([[features[c] for c in file_cols]], dtype=np.float32)
        device_X = np.array([[features[c] for c in device_cols]], dtype=np.float32)
        http_X = np.array([[features[c] for c in http_cols]], dtype=np.float32)
        
        scores = self.domain_if.score(logon_X, file_X, device_X, http_X)
        
        logon_score = float(scores["logon"][0])
        file_score = float(scores["file"][0])
        device_score = float(scores["device"][0])
        http_score = float(scores["http"][0])
        
        raw_overall_score = (logon_score + file_score + device_score + http_score) / 4.0
        
        # Rescale overall risk to [0, 1] relative to the observed max raw score (0.7300)
        overall_score = min(raw_overall_score / 0.7300, 1.0)
        
        if overall_score >= 0.80:
            risk_level = "HIGH"
        elif overall_score >= 0.50:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
            
        return {
            "overall_score": overall_score,
            "raw_overall_score": raw_overall_score,
            "risk_level": risk_level,
            "domain_scores": {
                "logon": logon_score,
                "file": file_score,
                "device": device_score,
                "http": http_score
            }
        }

    def predict_scenario(self, payload):
        if "features" not in payload:
            raise ValueError("Missing 'features'")
            
        features = payload["features"]
        missing = set(self.scenario_features) - set(features.keys())
        if missing:
            raise ValueError(f"Missing scenario features: {sorted(list(missing))}")
            
        X = np.array([[features[col] for col in self.scenario_features]])
        probabilities = self.scenario_model.predict_proba(X)[0]
        class_labels = self.scenario_model.classes_
        
        class_map = {
            0: "normal",
            1: "email_exfil",
            2: "sabotage",
            3: "usb_exfil",
            4: "flight_risk",
            5: "cloud_exfil"
        }
        
        prob_dict = {}
        for idx, cls in enumerate(class_labels):
            prob_dict[f"rf_{class_map[cls]}_prob"] = float(probabilities[idx])
            
        predicted_class = class_labels[np.argmax(probabilities)]
        
        return {
            "scenario": class_map[predicted_class],
            "confidence": float(np.max(probabilities)),
            **prob_dict
        }

    def predict_behavioral_risk(self, payload):
        required_keys = ["payload_id", "username", "hostname", "daily_sequence"]
        for key in required_keys:
            if key not in payload:
                raise ValueError(f"Missing required payload key: '{key}'")
                
        daily_sequence = payload["daily_sequence"]
        seq_len = self.rvfl_metadata["sequence_length"]
        if len(daily_sequence) < seq_len + 1:
            raise ValueError(f"daily_sequence must contain at least {seq_len + 1} days. Provided: {len(daily_sequence)}")
            
        target_sequence = daily_sequence[-(seq_len + 1):]
        
        domains = ["logon", "http", "device", "file"]
        domain_errors = {}
        
        for dom in domains:
            col = f"{dom}_risk"
            vals = [[float(day[col])] for day in target_sequence]
            features_array = np.array(vals, dtype=np.float32)
            X_seq = features_array[:seq_len]
            y_actual = features_array[seq_len:]
            
            # Scale input/target using MinMax scalers
            X_flat_scaled = self.feature_scalers[dom].transform(X_seq.reshape(-1, 1)).reshape(X_seq.shape)
            y_actual_scaled = self.target_scalers[dom].transform(y_actual.reshape(-1, 1))
            
            X_tensor = torch.tensor(X_flat_scaled, dtype=torch.float32).unsqueeze(0)
            y_pred_scaled = self.rvfl_orchestrators[dom].predict(X_tensor, self.ridge_models[dom])
            
            # Error computed in scaled space
            error = float(np.mean(np.square(y_actual_scaled - y_pred_scaled)))
            domain_errors[f"error_{dom}"] = error
            
        return {
            "payload_id": payload["payload_id"],
            "username": payload["username"],
            **domain_errors
        }

def analyze_user(user_id, engine, features_df, labels_df, top_users_df, test_users_list):
    """
    Performs full pipeline evaluation on a given user's timeline.
    Outputs structured diagnostic string.
    """
    # 1. Pull user's full log history
    user_timeline = features_df[features_df["user"] == user_id].sort_values("date").copy()
    if len(user_timeline) == 0:
        raise ValueError(f"User ID '{user_id}' not found in features dataset.")
        
    # Get ground truth (verification only)
    user_label = labels_df[labels_df["user_id"] == user_id].iloc[0]
    gt_is_insider = int(user_label["is_insider"])
    gt_scenario = user_label["threat_scenario"]
    
    # 2. Get user rank in test set
    test_ranked_df = top_users_df[top_users_df["user"].isin(test_users_list)].sort_values("score_v2", ascending=False).reset_index(drop=True)
    
    # Find rank index
    rank_idx = test_ranked_df[test_ranked_df["user"] == user_id].index
    if len(rank_idx) > 0:
        rank_str = f"#{rank_idx[0] + 1}"
    else:
        rank_str = "N/A (User is in training split)"
        
    # Top-10 threshold (the score of the 10th ranked user in test split)
    top_10_threshold = test_ranked_df.iloc[9]["score_v2"]
    
    exclude_cols = [
        "user", "date", "label", "is_insider", "threat_scenario",
        "logon_risk", "file_risk", "device_risk", "http_risk", "overall_risk",
        "raw_overall_risk", "daily_risk_delta", "daily_risk_rolling_mean_7d", "daily_risk_rolling_std_7d",
        "rf_normal_prob", "rf_email_exfil_prob", "rf_sabotage_prob", "rf_usb_exfil_prob", "rf_flight_risk_prob", "rf_cloud_exfil_prob",
        "scenario_risk", "rvfl_risk"
    ]
    
    # Trace stage 1 & 2 day by day
    stage_1_rows = []
    stage_2_rows = []
    daily_sequence = []
    
    for idx, row in enumerate(user_timeline.itertuples()):
        features = {}
        for col in user_timeline.columns:
            if col in exclude_cols:
                continue
            features[col] = float(getattr(row, col))
            
        payload = {"features": features}
        
        # Tier 1
        risk_result = engine.predict_current_risk(payload)
        
        # Populate features for Tier 2
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
        
        # Tier 2
        scenario_result = engine.predict_scenario(payload)
        
        # Save sequence logs
        date_str = str(user_timeline.iloc[idx]["date"])[:10]
        
        # Stage 1 format
        stage_1_rows.append(
            f"| {date_str} | L:{risk_result['domain_scores']['logon']:.4f} F:{risk_result['domain_scores']['file']:.4f} D:{risk_result['domain_scores']['device']:.4f} H:{risk_result['domain_scores']['http']:.4f} | {risk_result['overall_score']:.4f} | {risk_result['risk_level']} |"
        )
        
        # Stage 2 format
        stage_2_rows.append(
            f"| {date_str} | {scenario_result['scenario']:<15} | {scenario_result['confidence']:.2%} |"
        )
        
        daily_sequence.append({
            "overall_risk": risk_result["overall_score"],
            "logon_risk": risk_result["domain_scores"]["logon"],
            "file_risk": risk_result["domain_scores"]["file"],
            "device_risk": risk_result["domain_scores"]["device"],
            "http_risk": risk_result["domain_scores"]["http"],
            "rf_email_exfil_prob": scenario_result["rf_email_exfil_prob"],
            "rf_sabotage_prob": scenario_result["rf_sabotage_prob"],
            "rf_usb_exfil_prob": scenario_result["rf_usb_exfil_prob"],
            "rf_flight_risk_prob": scenario_result["rf_flight_risk_prob"],
            "rf_cloud_exfil_prob": scenario_result["rf_cloud_exfil_prob"]
        })
        
    # Tier 3 (Sequence Drift)
    seq_len = 7
    domain_errors = {"logon": [], "http": [], "device": [], "file": []}
    
    for i in range(seq_len, len(daily_sequence)):
        sub_seq = daily_sequence[i-seq_len:i+1]
        sub_payload = {
            "payload_id": "SUB",
            "username": user_id,
            "hostname": "SUB",
            "daily_sequence": sub_seq
        }
        res = engine.predict_behavioral_risk(sub_payload)
        for dom in ["logon", "http", "device", "file"]:
            domain_errors[dom].append(res[f"error_{dom}"])
            
    # Calculate max and mean errors for all 4 domains
    user_domain_scores = {}
    anomaly_days = len(daily_sequence) - seq_len
    for dom in ["logon", "http", "device", "file"]:
        max_err = np.max(domain_errors[dom]) if domain_errors[dom] else 0.0
        mean_err = np.mean(domain_errors[dom]) if domain_errors[dom] else 0.0
        user_domain_scores[f"score_{dom}"] = max_err * mean_err * np.sqrt(anomaly_days)
        
    # Scale domain scores using the saved scaler
    X_score = np.array([[user_domain_scores[f"score_{dom}"] for dom in ["logon", "http", "device", "file"]]])
    X_score_scaled = engine.fusion_scaler.transform(X_score)
    
    # Calculate final ranking score (Logistic Regression probability)
    score_v2 = float(engine.fusion_classifier.predict_proba(X_score_scaled)[0][1])
    mean_error = np.mean([np.mean(domain_errors[dom]) for dom in ["logon", "http", "device", "file"]])
    
    # 5. Verdict
    is_flagged = score_v2 >= top_10_threshold
    verdict_str = "FLAGGED FOR REVIEW" if is_flagged else "NOT FLAGGED"
    
    # Ground truth representation
    gt_scenario_str = "Normal" if gt_is_insider == 0 else f"Insider - {gt_scenario}"
    
    # Verdict matches
    match_str = "YES" if (is_flagged == (gt_is_insider == 1)) else "NO"
    
    # Format tables
    stage_1_table = "\n".join(stage_1_rows[:5]) + "\n| ...        | ...                                                 | ...    | ...      |\n" + "\n".join(stage_1_rows[-5:])
    stage_2_table = "\n".join(stage_2_rows[:5]) + "\n| ...        | ...             | ...    |\n" + "\n".join(stage_2_rows[-5:])
    
    output = f"""================================================================================
INSIDER THREAT CHECK — USER: {user_id}
WHAT THIS TOOL DOES: Analyzes daily endpoint logs to detect abnormal user behavior 
and classifies potential insider threat paths using a three-tier model pipeline.
================================================================================

STAGE 1: DAILY ANOMALY SCORE (Isolation Forest)
Checks each day's behavior against what's normal for this user population.

| Date       | Domain Scores (L:Logon, F:File, D:Device, H:HTTP) | Overall Risk | Risk Tier |
| :---       | :---                                              | :---:        | :---:     |
{stage_1_table}

STAGE 2: THREAT TYPE CLASSIFICATION (XGBoost)
Predicts which of 6 categories each day's behavior resembles.

| Date       | Predicted Class   | Confidence |
| :---       | :---              | :---:      |
{stage_2_table}

STAGE 3: BEHAVIORAL DRIFT OVER TIME (RedRVFL)
Looks at the pattern across days, not just single days.

Sequence length: {len(daily_sequence)} days | Drift error (MSE): {mean_error:.6f} | Final risk score: {score_v2:.6f}

FINAL VERDICT

This user ranks {rank_str} out of 200 test users. Top-10 threshold: {top_10_threshold:.6f}

VERDICT: {verdict_str}
Ground truth (verification only, not used in scoring): {gt_scenario_str}
Model verdict matches ground truth: {match_str}

HOW TO READ THIS

A single HIGH day alone does not mean insider — Stage 3's pattern-over-time is the real signal.
This model was trained using only each insider's final 10 active days as positive
examples; performance on subtle/early-stage behavior has not been separately validated.
================================================================================
"""
    return output, user_id

def main():
    parser = argparse.ArgumentParser(description="Diagnostic command-line checker for InsiEDR models.")
    parser.add_argument("--user", type=str, help="User ID to evaluate (e.g., U0430)")
    parser.add_argument("--compare", action="store_true", help="Runs one insider and one normal user side by side.")
    parser.add_argument("--pick-demo-user", action="store_true", help="Auto-selects a known insider for diagnostic check.")
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..'))
    
    models_dir = os.path.join(base_dir, "models")
    features_csv = os.path.join(base_dir, "if_enriched_features.csv")
    labels_csv = os.path.join(project_root, "OUTPUT_LABELS", "insider_labels.csv")
    top_users_csv = os.path.join(base_dir, "top_users.csv")
    test_users_json = os.path.join(base_dir, "test_users.json")
    
    # Load support files
    features_df = pd.read_csv(features_csv)
    labels_df = pd.read_csv(labels_csv)
    top_users_df = pd.read_csv(top_users_csv)
    
    with open(test_users_json, "r") as f:
        test_users_list = json.load(f)
        
    engine = LatestInferenceEngine(models_dir=models_dir)
    
    # Pick users based on flags
    target_users = []
    
    if args.compare:
        # Normal user: U0002 (not insider, test split)
        # Insider user: U0430 (cloud_exfil, test split)
        target_users = ["U0430", "U0002"]
    elif args.pick_demo_user:
        target_users = ["U0430"]
    elif args.user:
        target_users = [args.user]
    else:
        print("Usage: python check_insider.py --user <user_id> | --compare | --pick-demo-user")
        sys.exit(1)
        
    for user_id in target_users:
        report, _ = analyze_user(user_id, engine, features_df, labels_df, top_users_df, test_users_list)
        
        # Print to console
        print(report)
        print("\n" + "=" * 80 + "\n")
        
        # Save to file
        output_file = f"insider_check_{user_id}.txt"
        with open(output_file, "w") as f:
            f.write(report)
        print(f"Saved diagnostic report to '{output_file}'")

if __name__ == "__main__":
    main()
