# InsiEDR Stateless Inference API — Documentation

## Overview

The InsiEDR Inference API is a **stateless REST API** built with FastAPI that exposes the trained insider threat detection models as HTTP endpoints. It provides three levels of inference corresponding to the three stages of the InsiEDR detection pipeline:

| Level | Endpoint | Model | Purpose |
|-------|----------|-------|---------|
| **Level 1** | `POST /inference/risk` | Isolation Forest (SHAP-weighted) | Domain risk scoring |
| **Level 2** | `POST /inference/xgboost` | XGBoost Multiclass Classifier | Threat scenario classification |
| **Level 3** | `POST /inference/behavioral` | RedRVFL Neural Network | Behavioral sequence drift detection |

### Key Design Principles

- **Stateless**: The API does not store any user data or maintain session state. All required data must be passed in each request.
- **Pre-loaded Models**: Trained model artifacts (`.pkl` files) and configuration (`.json` files) are loaded into memory once at server startup for fast inference.
- **Validated Input**: All payloads are validated using Pydantic schemas before being processed.

---

## Getting Started

### Prerequisites

Ensure all dependencies are installed:

```bash
cd final_model/inference
pip install -r requirements.txt
```

### Starting the Server

```bash
cd final_model/inference
python app.py
```

Or using uvicorn directly:

```bash
cd final_model/inference
uvicorn app:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.

### Interactive API Docs (Swagger UI)

Once the server is running, open your browser and navigate to:

```
http://127.0.0.1:8000/docs
```

This provides an interactive Swagger UI where you can test all endpoints directly.

---

## Model Artifacts Required

The API loads the following files from the `final_model/output/` and `final_model/latest_data/models/` directories on startup:

| File | Source Script | Description |
|------|--------------|-------------|
| `output/weights.json` | `run_new_model.py` | SHAP domain weights for risk calculation |
| `output/xgb_model.pkl` | `run_new_model.py` | Trained XGBoost multiclass classifier |
| `output/rvfl_model.pkl` | `run_new_model.py` | Trained RedRVFL neural network orchestrator |
| `output/rvfl_ridge_models.pkl` | `run_new_model.py` | Ridge regression models for RedRVFL layers |
| `output/feature_scaler.pkl` | `run_new_model.py` | MinMaxScaler for behavioral sequence features |
| `output/target_scaler.pkl` | `run_new_model.py` | MinMaxScaler for behavioral sequence targets |
| `latest_data/models/scenario_xgb_features.json` | Pre-configured | List of 40 feature names expected by XGBoost |

> **Important**: You must run `run_isolation_forest.py` followed by `run_new_model.py` before starting the inference server, so that all model artifacts are generated.

---

## Endpoints

---

### Level 1: Domain Risk Scoring

**`POST /inference/risk`**

Calculates the SHAP-weighted overall risk score from the 4 Isolation Forest domain anomaly scores.

#### Formula

```
raw_overall_risk = (file_risk × 0.1737) + (device_risk × 0.0250) + (http_risk × 0.6145) + (logon_risk × 0.1869)
overall_risk     = min(raw_overall_risk / max_raw_train_score, 1.0)
```

Where `max_raw_train_score = 0.763629` (the maximum raw score observed during training, used for normalization).

#### Request Body

```json
{
    "file_risk": 0.5,
    "device_risk": 0.1,
    "http_risk": 0.8,
    "logon_risk": 0.3
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_risk` | `float` | Anomaly score from the File Isolation Forest (higher = more anomalous) |
| `device_risk` | `float` | Anomaly score from the Device/USB Isolation Forest |
| `http_risk` | `float` | Anomaly score from the HTTP Isolation Forest |
| `logon_risk` | `float` | Anomaly score from the Logon Isolation Forest |

#### Response

```json
{
    "raw_overall_risk": 0.6370,
    "overall_risk": 0.8341
}
```

| Field | Type | Description |
|-------|------|-------------|
| `raw_overall_risk` | `float` | Unscaled weighted sum of domain risks |
| `overall_risk` | `float` | Normalized risk score (0.0 to 1.0), where 1.0 = maximum observed during training |

#### Error Responses

| Status Code | Cause |
|-------------|-------|
| `422` | Missing or invalid field in request body |
| `500` | SHAP weights not loaded (model artifacts missing) |

---

### Level 2: XGBoost Scenario Classification

**`POST /inference/xgboost`**

Classifies a single user-day record into one of 6 threat scenarios using the trained XGBoost multiclass classifier.

#### Threat Scenarios

| Class | Label | Description |
|-------|-------|-------------|
| 0 | `normal` | Normal user behavior |
| 1 | `email_exfil` | Data exfiltration via email |
| 2 | `sabotage` | System sabotage or destruction |
| 3 | `usb_exfil` | Data exfiltration via USB devices |
| 4 | `flight_risk` | Employee preparing to leave the organization |
| 5 | `cloud_exfil` | Data exfiltration via cloud services |

#### Request Body

```json
{
    "features": {
        "logon_count": 5.0,
        "logoff_count": 5.0,
        "unique_pc_count": 1.0,
        "daily_unique_pc_count": 1.0,
        "after_hours_logon": 2.0,
        "daily_after_hours_logon_ratio": 0.4,
        "first_logon_time": 7.0,
        "last_logoff_time": 22.0,
        "weekend_logon": 0.0,
        "daily_pc_access_entropy": 0.0,
        "file_access_count": 15.0,
        "daily_unique_filename_count": 14.0,
        "daily_new_filename_count": 12.0,
        "daily_file_access_entropy": 2.6,
        "usb_connect_count": 1.0,
        "usb_disconnect_count": 1.0,
        "after_hours_usb_usage": 0.0,
        "daily_device_connect_count": 1.0,
        "daily_device_usage_flag": 1.0,
        "first_usb_usage_time": 10.0,
        "http_count": 45.0,
        "daily_http_request_count": 45.0,
        "unique_url_count": 8.0,
        "suspicious_url_count": 2.0,
        "file_sharing_site_visits": 3.0,
        "job_search_site_visits": 1.0,
        "http_after_hours": 5.0,
        "daily_unique_domain_count": 6.0,
        "daily_new_domain_count": 2.0,
        "daily_domain_access_entropy": 1.5,
        "daily_external_domain_ratio": 0.8,
        "logon_risk": 0.45,
        "file_risk": 0.52,
        "device_risk": 0.48,
        "http_risk": 0.61,
        "overall_risk": 0.55,
        "raw_overall_risk": 0.42,
        "daily_risk_delta": 0.03,
        "daily_risk_rolling_mean_7d": 0.50,
        "daily_risk_rolling_std_7d": 0.02
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `features` | `Dict[str, float]` | A dictionary mapping **all 40 feature names** to their numerical values. All 40 features must be present. |

#### Complete Feature List (40 features required)

**Logon Domain (10):**
`logon_count`, `logoff_count`, `unique_pc_count`, `daily_unique_pc_count`, `after_hours_logon`, `daily_after_hours_logon_ratio`, `first_logon_time`, `last_logoff_time`, `weekend_logon`, `daily_pc_access_entropy`

**File Domain (4):**
`file_access_count`, `daily_unique_filename_count`, `daily_new_filename_count`, `daily_file_access_entropy`

**Device Domain (6):**
`usb_connect_count`, `usb_disconnect_count`, `after_hours_usb_usage`, `daily_device_connect_count`, `daily_device_usage_flag`, `first_usb_usage_time`

**HTTP Domain (11):**
`http_count`, `daily_http_request_count`, `unique_url_count`, `suspicious_url_count`, `file_sharing_site_visits`, `job_search_site_visits`, `http_after_hours`, `daily_unique_domain_count`, `daily_new_domain_count`, `daily_domain_access_entropy`, `daily_external_domain_ratio`

**IF Risk Scores (4):**
`logon_risk`, `file_risk`, `device_risk`, `http_risk`

**Combined Risk & Trends (5):**
`overall_risk`, `raw_overall_risk`, `daily_risk_delta`, `daily_risk_rolling_mean_7d`, `daily_risk_rolling_std_7d`

#### Response

```json
{
    "predicted_scenario": "email_exfil",
    "probabilities": {
        "normal": 0.12,
        "email_exfil": 0.45,
        "sabotage": 0.08,
        "usb_exfil": 0.15,
        "flight_risk": 0.10,
        "cloud_exfil": 0.10
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `predicted_scenario` | `string` | The most likely threat scenario (highest probability) |
| `probabilities` | `Dict[str, float]` | Probability distribution across all 6 scenarios (sums to 1.0) |

#### Error Responses

| Status Code | Cause |
|-------------|-------|
| `400` | Missing features in the `features` dictionary |
| `422` | Invalid payload structure |
| `500` | XGBoost model or feature list not loaded |

---

### Level 3: Behavioral Sequence Drift

**`POST /inference/behavioral`**

Analyzes a 7-day chronological sequence of daily fused risk values through the RedRVFL (Reduced Random Vector Functional Link) neural network to detect behavioral drift — sudden changes in a user's risk pattern that may indicate the onset of malicious activity.

#### How It Works

1. The input is a 7-day sequence of `rvfl_risk` values, where each value represents a single day's fused risk score.
2. The RedRVFL model predicts what the 7th day's risk *should* be based on the preceding 6 days.
3. The **sequence error** (squared difference between actual and predicted) indicates how unexpected the user's behavior was.
4. A high sequence error means the user's behavior deviated significantly from the model's expectation — a strong insider threat signal.

#### How to Calculate `rvfl_risk` (Input Values)

Each day's `rvfl_risk` value is computed from the XGBoost scenario probabilities and overall risk:

```
scenario_risk = max(email_exfil_prob, sabotage_prob, usb_exfil_prob, flight_risk_prob, cloud_exfil_prob)
rvfl_risk     = 0.3 × overall_risk + 0.7 × scenario_risk
```

#### Request Body

```json
{
    "rvfl_risk_sequence": [0.10, 0.12, 0.11, 0.15, 0.35, 0.55, 0.80]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `rvfl_risk_sequence` | `List[float]` | Exactly **7 float values** representing daily `rvfl_risk` scores in chronological order (Day 1 → Day 7) |

#### Response

```json
{
    "actual_risk_day7": 0.80,
    "predicted_risk_day7": 0.446,
    "sequence_error": 0.1255
}
```

| Field | Type | Description |
|-------|------|-------------|
| `actual_risk_day7` | `float` | The actual risk value passed for day 7 |
| `predicted_risk_day7` | `float` | What the RedRVFL model predicted day 7's risk should be |
| `sequence_error` | `float` | Squared error between actual and predicted. Higher = more anomalous drift |

#### Interpreting Results

| Sequence Error | Interpretation |
|----------------|----------------|
| `< 0.01` | Normal behavior — consistent with historical patterns |
| `0.01 – 0.05` | Mild deviation — worth monitoring |
| `0.05 – 0.10` | Significant deviation — elevated risk |
| `> 0.10` | High behavioral drift — strong insider threat indicator |

#### Error Responses

| Status Code | Cause |
|-------------|-------|
| `400` | Sequence length is not exactly 7 |
| `422` | Invalid payload structure |
| `500` | RedRVFL model or scalers not loaded |

---

## End-to-End Inference Workflow

To perform a complete insider threat assessment for a single user-day, a client application should call the endpoints in the following order:

```
┌─────────────────────────┐
│  Raw Log Data (1 day)   │
│  logon, file, device,   │
│  http events            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Feature Extraction     │
│  (Client-side)          │
│  31 statistical features│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Isolation Forest       │
│  (Client-side or        │
│   pre-computed)         │
│  → 4 domain risk scores │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌──────────────────────┐
│  POST /inference/risk   │────▶│  overall_risk         │
│  (Level 1)              │     │  raw_overall_risk     │
└───────────┬─────────────┘     └──────────────────────┘
            │
            ▼
┌─────────────────────────┐     ┌──────────────────────┐
│  POST /inference/xgboost│────▶│  predicted_scenario   │
│  (Level 2)              │     │  6 class probabilities│
└───────────┬─────────────┘     └──────────────────────┘
            │
            │  Accumulate 7 days of rvfl_risk values
            ▼
┌─────────────────────────┐     ┌──────────────────────┐
│  POST /inference/        │────▶│  sequence_error       │
│  behavioral (Level 3)   │     │  (drift detection)    │
└─────────────────────────┘     └──────────────────────┘
```

### Example: Full Pipeline in Python

```python
import requests

BASE = "http://127.0.0.1:8000"

# Step 1: Calculate overall risk from IF domain scores
risk_resp = requests.post(f"{BASE}/inference/risk", json={
    "file_risk": 0.52,
    "device_risk": 0.48,
    "http_risk": 0.61,
    "logon_risk": 0.45
}).json()

print(f"Overall Risk: {risk_resp['overall_risk']:.4f}")

# Step 2: Classify threat scenario
features = {
    "logon_count": 5, "logoff_count": 5,
    # ... (all 40 features) ...
    "overall_risk": risk_resp["overall_risk"],
    "raw_overall_risk": risk_resp["raw_overall_risk"],
    "daily_risk_delta": 0.03,
    "daily_risk_rolling_mean_7d": 0.50,
    "daily_risk_rolling_std_7d": 0.02
}

xgb_resp = requests.post(f"{BASE}/inference/xgboost", json={
    "features": features
}).json()

print(f"Predicted Scenario: {xgb_resp['predicted_scenario']}")
print(f"Probabilities: {xgb_resp['probabilities']}")

# Step 3: Check behavioral drift (needs 7 days of data)
behavioral_resp = requests.post(f"{BASE}/inference/behavioral", json={
    "rvfl_risk_sequence": [0.10, 0.12, 0.11, 0.15, 0.35, 0.55, 0.80]
}).json()

print(f"Sequence Error: {behavioral_resp['sequence_error']:.4f}")
```

---

## Testing

A test script is provided at `inference/test_inference.py`. Start the server first, then run:

```bash
python test_inference.py
```

This sends sample requests to all three endpoints and prints the responses.

---

## Configuration

| Setting | Default | Location |
|---------|---------|----------|
| Host | `0.0.0.0` | `app.py` (line: `uvicorn.run`) |
| Port | `8000` | `app.py` (line: `uvicorn.run`) |
| Model directory | `../output/` | Relative to `inference/app.py` |
| Feature schema | `../latest_data/models/scenario_xgb_features.json` | Relative to `inference/app.py` |
