import os
import sys
import numpy as np
import pandas as pd
import torch

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
    Subclass of InferenceEngine adapted for the 6-class scenario labels,
    correct threshold division factor (0.7300), and probability columns.
    """
    def predict_current_risk(self, payload):
        if "features" not in payload:
            raise ValueError("Missing 'features'")
            
        features = payload["features"]
        
        # logon_features, file_features, etc.
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
        
        # Rescale using 0.7300 divisor
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
        
        rvfl_values = []
        for day in target_sequence:
            overall_risk = float(day["overall_risk"])
            
            # Extract the max scenario probability using the 5 threat classes
            scenario_risk = max(
                float(day.get("rf_email_exfil_prob", 0)),
                float(day.get("rf_sabotage_prob", 0)),
                float(day.get("rf_usb_exfil_prob", 0)),
                float(day.get("rf_flight_risk_prob", 0)),
                float(day.get("rf_cloud_exfil_prob", 0))
            )
            
            rvfl_risk = self.if_weight * overall_risk + self.xgb_weight * scenario_risk
            rvfl_values.append([rvfl_risk])
            
        features_array = np.array(rvfl_values, dtype=np.float32)
        X_seq = features_array[:seq_len]
        y_actual = features_array[seq_len:]
        
        # Scale inputs using the trained feature_scaler
        X_flat_scaled = self.feature_scaler.transform(X_seq.reshape(-1, 1)).reshape(X_seq.shape)
        
        X_tensor = torch.tensor(X_flat_scaled, dtype=torch.float32).unsqueeze(0)
        
        # Ridge predictions
        y_pred_scaled = self.rvfl_orchestrator.predict(X_tensor, self.ridge_models)
        
        # Invert scale using 2D array reshape
        y_pred = self.feature_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1))
        
        error = float(np.mean(np.square(y_actual - y_pred)))
        
        return {
            "payload_id": payload["payload_id"],
            "username": payload["username"],
            "prediction_error": error,
            "behavioral_risk": float(y_pred[0][0])
        }

def run_demo():
    print("=" * 80)
    print("              INSIEDR DEMO SIMULATION (LATEST DATA RUN)")
    print("=" * 80)
    
    models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
    dataset_path = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"
    
    # Initialize Engine
    print("Initializing Latest Inference Engine...")
    engine = LatestInferenceEngine(models_dir=models_dir)
    print("Engine loaded successfully.\n")
    
    # Load dataset to select a suspicious test user
    df = pd.read_csv(dataset_path)
    
    # Select user U0430 (who is a cloud_exfil insider in the test set)
    selected_user = "U0430"
    user_df = df[df["user"] == selected_user].sort_values("date").head(8)
    
    if len(user_df) < 8:
        # Fallback to any user with >= 8 days if U0430 is not present
        for user, g in df.groupby("user"):
            if len(g) >= 8:
                selected_user = user
                user_df = g.sort_values("date").head(8)
                break
                
    print(f"Selected Target User: {selected_user} (Scenario: {user_df.iloc[0]['threat_scenario']})")
    print(f"Days of active logs: {len(user_df)}\n")
    
    exclude_cols = [
        "user", "date", "label", "is_insider", "threat_scenario",
        "logon_risk", "file_risk", "device_risk", "http_risk", "overall_risk",
        "raw_overall_risk", "daily_risk_delta", "daily_risk_rolling_mean_7d", "daily_risk_rolling_std_7d",
        "rf_normal_prob", "rf_email_exfil_prob", "rf_sabotage_prob", "rf_usb_exfil_prob", "rf_flight_risk_prob", "rf_cloud_exfil_prob",
        "scenario_risk", "rvfl_risk"
    ]
    
    daily_sequence = []
    
    print("-" * 60)
    print("Simulating Daily Telemetry Processing (IF + XGB)")
    print("-" * 60)
    
    for idx, row in enumerate(user_df.itertuples()):
        features = {}
        for col in user_df.columns:
            if col in exclude_cols:
                continue
            features[col] = float(getattr(row, col))
            
        payload = {"features": features}
        
        # 1. Predict Current Risk (Isolation Forest)
        risk_result = engine.predict_current_risk(payload)
        
        # Update features dict with risk metrics before passing to XGBoost
        features["logon_risk"] = risk_result["domain_scores"]["logon"]
        features["file_risk"] = risk_result["domain_scores"]["file"]
        features["device_risk"] = risk_result["domain_scores"]["device"]
        features["http_risk"] = risk_result["domain_scores"]["http"]
        features["overall_risk"] = risk_result["overall_score"]
        features["raw_overall_risk"] = risk_result["raw_overall_score"]
        
        # Compute rolling features from accumulated sequence
        prev_overall_risks = [day["overall_risk"] for day in daily_sequence]
        if len(prev_overall_risks) > 0:
            features["daily_risk_delta"] = risk_result["overall_score"] - prev_overall_risks[-1]
        else:
            features["daily_risk_delta"] = 0.0
            
        all_overall_risks = prev_overall_risks + [risk_result["overall_score"]]
        recent_7d = all_overall_risks[-7:]
        
        features["daily_risk_rolling_mean_7d"] = np.mean(recent_7d)
        features["daily_risk_rolling_std_7d"] = np.std(recent_7d) if len(recent_7d) > 1 else 0.0
        
        # 2. Predict Scenario (XGBoost)
        scenario_result = engine.predict_scenario(payload)
        
        print(f"Day {idx + 1} ({user_df.iloc[idx]['date']}):")
        print(f"  Domain Scores: Logon: {risk_result['domain_scores']['logon']:.4f}, File: {risk_result['domain_scores']['file']:.4f}, Device: {risk_result['domain_scores']['device']:.4f}, HTTP: {risk_result['domain_scores']['http']:.4f}")
        print(f"  Recalibrated Overall Anomaly Risk: {risk_result['overall_score']:.4f}")
        print(f"  XGBoost Predicted Scenario: {scenario_result['scenario']} (Confidence: {scenario_result['confidence']:.4%})")
        print(f"  Exfiltration Probabilities:")
        print(f"    Email: {scenario_result['rf_email_exfil_prob']:.4f} | Sabotage: {scenario_result['rf_sabotage_prob']:.4f} | USB: {scenario_result['rf_usb_exfil_prob']:.4f} | Flight: {scenario_result['rf_flight_risk_prob']:.4f} | Cloud: {scenario_result['rf_cloud_exfil_prob']:.4f}")
        print("-" * 60)
        
        daily_sequence.append({
            "overall_risk": risk_result["overall_score"],
            "rf_email_exfil_prob": scenario_result["rf_email_exfil_prob"],
            "rf_sabotage_prob": scenario_result["rf_sabotage_prob"],
            "rf_usb_exfil_prob": scenario_result["rf_usb_exfil_prob"],
            "rf_flight_risk_prob": scenario_result["rf_flight_risk_prob"],
            "rf_cloud_exfil_prob": scenario_result["rf_cloud_exfil_prob"]
        })
        
    # 3. Predict Behavioral Risk (RedRVFL Sequence model)
    print("\n" + "-" * 60)
    print("Simulating Temporal Sequence Drift Analysis (RedRVFL)")
    print("-" * 60)
    
    rvfl_payload = {
        "payload_id": "DEMO-USER-U0430",
        "username": selected_user,
        "hostname": "WORKSTATION-0430",
        "daily_sequence": daily_sequence
    }
    
    rvfl_result = engine.predict_behavioral_risk(rvfl_payload)
    
    print("\nBehavioral Analysis Completed:")
    print(f"  User ID: {rvfl_result['username']}")
    print(f"  Sequence Length Evaluated: {len(daily_sequence)} days")
    print(f"  RedRVFL Sequence Prediction Error (MSE): {rvfl_result['prediction_error']:.6f}")
    print(f"  Final Aggregated Behavioral Risk Score: {rvfl_result['behavioral_risk']:.4f}")
    print("=" * 80)

if __name__ == "__main__":
    run_demo()
