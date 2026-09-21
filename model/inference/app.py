import os
import sys
import json
import joblib
import torch
import numpy as np
import pandas as pd
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add final_model directory to sys.path to import src components
current_dir = os.path.dirname(os.path.abspath(__file__))
final_model_dir = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(final_model_dir)

from src.red_revfl_orchestrator import RedRVFLOrchestrator

app = FastAPI(
    title="InsiEDR Stateless Inference API",
    description="Endpoints for Risk, XGBoost classification, and Behavioral Sequence modeling.",
    version="1.0"
)

# --------------------------------------------------------------------------
# Models and Configurations
# --------------------------------------------------------------------------
class ModelState:
    def __init__(self):
        self.shap_weights = None
        self.xgb_features = None
        self.xgb_model = None
        self.rvfl_model = None
        self.rvfl_ridge_models = None
        self.feature_scaler = None
        self.target_scaler = None
        
model_state = ModelState()

@app.on_event("startup")
def load_models():
    print("Loading models and configurations...")
    
    # Paths
    output_dir = os.path.join(final_model_dir, "output")
    models_dir = os.path.join(final_model_dir, "latest_data", "models")
    
    # 1. SHAP Weights
    weights_path = os.path.join(output_dir, "weights.json")
    if os.path.exists(weights_path):
        with open(weights_path, "r") as f:
            model_state.shap_weights = json.load(f)
            
    # 2. XGBoost Features and Model
    xgb_feat_path = os.path.join(models_dir, "scenario_xgb_features.json")
    if os.path.exists(xgb_feat_path):
        with open(xgb_feat_path, "r") as f:
            model_state.xgb_features = json.load(f)
            
    xgb_model_path = os.path.join(output_dir, "xgb_model.pkl")
    if os.path.exists(xgb_model_path):
        model_state.xgb_model = joblib.load(xgb_model_path)
        
    # 3. Behavioral Models & Scalers
    rvfl_model_path = os.path.join(output_dir, "rvfl_model.pkl")
    if os.path.exists(rvfl_model_path):
        model_state.rvfl_model = joblib.load(rvfl_model_path)
        
    rvfl_ridge_path = os.path.join(output_dir, "rvfl_ridge_models.pkl")
    if os.path.exists(rvfl_ridge_path):
        model_state.rvfl_ridge_models = joblib.load(rvfl_ridge_path)
        
    feature_scaler_path = os.path.join(output_dir, "feature_scaler.pkl")
    if os.path.exists(feature_scaler_path):
        model_state.feature_scaler = joblib.load(feature_scaler_path)
        
    target_scaler_path = os.path.join(output_dir, "target_scaler.pkl")
    if os.path.exists(target_scaler_path):
        model_state.target_scaler = joblib.load(target_scaler_path)
        
    print("Startup complete.")

# --------------------------------------------------------------------------
# Pydantic Schemas
# --------------------------------------------------------------------------
class RiskInput(BaseModel):
    file_risk: float
    device_risk: float
    http_risk: float
    logon_risk: float

class XGBoostInput(BaseModel):
    # Flexible dict to accept all required XGB features without explicitly declaring 40 fields
    features: Dict[str, float]

class BehavioralInput(BaseModel):
    # Expects exactly a sequence of 7 daily rvfl_risk values (sequence length = 7)
    rvfl_risk_sequence: List[float]

# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.post("/inference/risk")
def calculate_risk(payload: RiskInput):
    """
    Level 1: Calculates overall risk using pre-calculated SHAP weights.
    (Note: Max Raw Train Score scaling is not applied here to remain stateless, 
    or can be applied if hardcoded. For now returning raw weighted sum).
    """
    if model_state.shap_weights is None:
        raise HTTPException(status_code=500, detail="SHAP weights not loaded.")
        
    # Extracted from run_new_model.py max_raw_train_score
    max_raw_train_score = 0.763629
    
    raw_overall_risk = (
        model_state.shap_weights["file_risk"] * payload.file_risk +
        model_state.shap_weights["device_risk"] * payload.device_risk +
        model_state.shap_weights["http_risk"] * payload.http_risk +
        model_state.shap_weights["logon_risk"] * payload.logon_risk
    )
    
    rescaled_overall_risk = min(raw_overall_risk / max_raw_train_score, 1.0)
    
    return {
        "raw_overall_risk": float(raw_overall_risk),
        "overall_risk": float(rescaled_overall_risk)
    }

@app.post("/inference/xgboost")
def classify_scenario(payload: XGBoostInput):
    """
    Level 2: Multiclass XGBoost Scenario Classification.
    """
    if model_state.xgb_model is None or model_state.xgb_features is None:
        raise HTTPException(status_code=500, detail="XGBoost model/features not loaded.")
        
    # Validate features presence
    missing_features = [f for f in model_state.xgb_features if f not in payload.features]
    if missing_features:
        raise HTTPException(status_code=400, detail=f"Missing features: {missing_features}")
        
    # Prepare DataFrame exactly as XGBoost expects
    df = pd.DataFrame([payload.features])[model_state.xgb_features].fillna(0)
    
    # Predict probabilities
    probabilities = model_state.xgb_model.predict_proba(df)[0]
    
    # Reverse scenario mapping
    REVERSE_SCENARIO_MAP = {
        0: "normal",
        1: "email_exfil",
        2: "sabotage",
        3: "usb_exfil",
        4: "flight_risk",
        5: "cloud_exfil"
    }
    
    result = {REVERSE_SCENARIO_MAP[i]: float(prob) for i, prob in enumerate(probabilities)}
    
    # Determine the most likely scenario
    predicted_class = REVERSE_SCENARIO_MAP[np.argmax(probabilities)]
    
    return {
        "predicted_scenario": predicted_class,
        "probabilities": result
    }

@app.post("/inference/behavioral")
def sequence_drift(payload: BehavioralInput):
    """
    Level 3: Single RedRVFL Sequence Drift Retraining / Evaluation.
    """
    if None in (model_state.rvfl_model, model_state.rvfl_ridge_models, model_state.feature_scaler, model_state.target_scaler):
        raise HTTPException(status_code=500, detail="Behavioral model or scalers not loaded.")
        
    seq = payload.rvfl_risk_sequence
    if len(seq) != 7:
        raise HTTPException(status_code=400, detail="Sequence must be exactly 7 days.")
        
    # The sequence input array is expected to be [batch, seq_len, features]
    # We create one sequence and its target is the last day (or the sequence itself, based on how predict works)
    # create_sequences creates shape: (num_seq, 7, 1) and target (num_seq, 1)
    
    X_raw = np.array(seq).reshape(1, 7, 1)
    # Scale features
    # feature_scaler was fit on flattened (num_seq * 7, 1)
    X_scaled = model_state.feature_scaler.transform(X_raw.reshape(-1, 1)).reshape(X_raw.shape)
    
    # Extract features using RedRVFL
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
    y_pred_scaled = model_state.rvfl_model.predict(X_tensor, model_state.rvfl_ridge_models)
    
    # Inverse transform to get raw predicted risk
    y_pred_raw = model_state.target_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1))[0][0]
    
    # Assuming target is the 7th day (seq[-1]) based on sequence drift formulation
    actual_risk = seq[-1] 
    
    # Compute sequence error (squared error)
    error = float(np.square(actual_risk - y_pred_raw))
    
    return {
        "actual_risk_day7": float(actual_risk),
        "predicted_risk_day7": float(y_pred_raw),
        "sequence_error": error
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
