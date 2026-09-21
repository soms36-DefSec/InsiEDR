# InsiEDR Pipeline — Complete Technical Documentation

## 1. System Overview

InsiEDR (Insider Endpoint Detection & Response) is a multi-stage insider threat detection system that analyzes employee behavioral logs to identify malicious insiders. The pipeline processes raw activity logs through four sequential machine learning stages to produce a ranked list of suspected insider threats.

### Pipeline Architecture

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                        RAW INPUT LOGS                                   │
 │   logon.csv  |  file.csv  |  device.csv  |  http.csv  |  labels.csv    │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  STAGE 1: Feature Extraction + Isolation Forest  (run_isolation_forest) │
 │  ────────────────────────────────────────────────────────────────────── │
 │  • Extracts 31 statistical features from raw logs                      │
 │  • Trains 4 domain-specific Isolation Forests                          │
 │  • Produces 4 anomaly risk scores per user-day                         │
 │  OUTPUT: if_enriched_features.csv (31 raw + 9 risk features)           │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  STAGE 2: SHAP Domain Weighting                        (run_new_model) │
 │  ────────────────────────────────────────────────────────────────────── │
 │  • Applies pre-calculated SHAP weights to 4 domain risks               │
 │  • Recomputes overall_risk as a weighted sum                            │
 │  • Adds 7-day rolling trend features                                    │
 │  OUTPUT: if_enriched_features_shap.csv                                  │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  STAGE 3: XGBoost Multiclass Scenario Classifier       (run_new_model) │
 │  ────────────────────────────────────────────────────────────────────── │
 │  • Trains a 6-class XGBoost to identify the threat type                 │
 │  • Outputs probability distribution across all scenarios                │
 │  OUTPUT: xgb_model.pkl, scenario_training_dataset_with_xgb_shap.csv     │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  STAGE 4: RedRVFL Behavioral Sequence Drift            (run_new_model) │
 │  ────────────────────────────────────────────────────────────────────── │
 │  • Fuses risk + scenario probabilities into single rvfl_risk signal     │
 │  • Builds 7-day sliding window sequences                                │
 │  • Trains RedRVFL neural network to model normal behavior               │
 │  • Detects insiders via prediction error (behavioral drift)             │
 │  OUTPUT: top_users_shap.csv (ranked user list)                          │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  EVALUATION: Top-K Review Queue                                         │
 │  ────────────────────────────────────────────────────────────────────── │
 │  • Ranks test users by score_v2 (descending)                            │
 │  • Reports Recall & Precision at Top-5, Top-10, etc.                    │
 │  • Lists caught insiders with their scores and threat class              │
 │  OUTPUT: confusion_matrix.txt                                           │
 └─────────────────────────────────────────────────────────────────────────┘
```

### How to Run

The entire pipeline is unified into a single command:

```bash
# Runs the entire end-to-end pipeline:
# 1. Feature Extraction + Domain Isolation Forests
# 2. SHAP Domain Weighting & Overall Risk Computation
# 3. Multiclass XGBoost Scenario Classifier
# 4. Single RedRVFL Behavioral Sequence Drift Retraining
# 5. Top-K Review Queue Evaluation
python run_new_model.py
```

---

## 2. Input Data

### 2.1 Raw Log Files

Location: `final_model/INPUT_LOGS/`

| File | Description | Key Columns |
|------|-------------|-------------|
| `logon.csv` | Employee login/logout events | `event_id`, `timestamp`, `user_id`, `pc`, `activity` (Logon/Logoff), `auth_result`, `site` |
| `file.csv` | File access events | `event_id`, `timestamp`, `user_id`, `pc`, `activity`, `filename`, `file_extension`, `file_path`, `destination`, `file_size_mb` |
| `device.csv` | USB device connect/disconnect events | `event_id`, `timestamp`, `user_id`, `pc`, `activity` (Connect/Disconnect), `device_id`, `file_size_mb` |
| `http.csv` | Web browsing activity | `event_id`, `timestamp`, `user_id`, `pc`, `url`, `domain`, `activity`, `content_type`, `bytes_transferred` |

### 2.2 Ground Truth Labels

Location: `final_model/INPUT_LOGS/OUTPUT_LABELS/insider_labels.csv`

| Column | Description |
|--------|-------------|
| `user_id` | Employee identifier (e.g., `U0001`) |
| `is_insider` | Binary flag: `0` = normal, `1` = insider |
| `threat_scenario` | Type of insider threat: `normal`, `email_exfil`, `sabotage`, `usb_exfil`, `flight_risk`, `cloud_exfil` |

---

## 3. Stage 1: Feature Extraction + Isolation Forest

**Script:** `run_new_model.py` (Stage 1)

### 3.1 Feature Extraction

The `CERTBehavioralExtractor` class reads the 4 raw log CSVs and aggregates events into **daily per-user statistical features**. Each row in the output represents one user's activity on one day.

#### Logon Domain (10 features)

| Feature | Description |
|---------|-------------|
| `logon_count` | Number of logon events that day |
| `logoff_count` | Number of logoff events that day |
| `unique_pc_count` | Number of unique PCs accessed (cumulative) |
| `daily_unique_pc_count` | Number of unique PCs accessed that specific day |
| `after_hours_logon` | Number of logon events outside 7 AM – 6 PM |
| `daily_after_hours_logon_ratio` | Ratio of after-hours logons to total logons |
| `first_logon_time` | Hour of first logon (0–23) |
| `last_logoff_time` | Hour of last logoff (0–23) |
| `weekend_logon` | Binary flag: 1 if any logon occurred on a weekend |
| `daily_pc_access_entropy` | Shannon entropy of PC access distribution |

#### File Domain (4 features)

| Feature | Description |
|---------|-------------|
| `file_access_count` | Number of file access events that day |
| `daily_unique_filename_count` | Number of distinct filenames accessed |
| `daily_new_filename_count` | Number of filenames not seen in prior days |
| `daily_file_access_entropy` | Shannon entropy of file access distribution |

#### Device/USB Domain (6 features)

| Feature | Description |
|---------|-------------|
| `usb_connect_count` | Number of USB connect events |
| `usb_disconnect_count` | Number of USB disconnect events |
| `after_hours_usb_usage` | Number of USB events outside business hours |
| `daily_device_connect_count` | Number of device connections that day |
| `daily_device_usage_flag` | Binary: 1 if any USB activity occurred |
| `first_usb_usage_time` | Hour of first USB event (0–23), 0 if none |

#### HTTP Domain (11 features)

| Feature | Description |
|---------|-------------|
| `http_count` | Total number of HTTP requests |
| `daily_http_request_count` | HTTP requests made that day |
| `unique_url_count` | Number of distinct URLs visited |
| `suspicious_url_count` | Count of visits to known suspicious domains (e.g., wikileaks.org, mediafire.com) |
| `file_sharing_site_visits` | Visits to file sharing sites (dropbox.com, box.com, etc.) |
| `job_search_site_visits` | Visits to job search sites (monster.com, indeed.com, etc.) |
| `http_after_hours` | HTTP requests outside business hours |
| `daily_unique_domain_count` | Number of distinct domains visited |
| `daily_new_domain_count` | Domains not seen in prior days |
| `daily_domain_access_entropy` | Shannon entropy of domain access distribution |
| `daily_external_domain_ratio` | Ratio of external to total domain visits |

**Total raw features extracted: 31**

### 3.2 Isolation Forest Training

The `DomainIsolationForest` class trains **4 separate Isolation Forest** models — one per behavioral domain. Each model learns the "normal" distribution of features for its domain and then scores every user-day record based on how anomalous it looks.

**Model:** `sklearn.ensemble.IsolationForest`

| Hyperparameter | Value | Description |
|----------------|-------|-------------|
| `n_estimators` | 200 | Number of isolation trees per domain |
| `contamination` | 0.05 | Expected proportion of anomalies (5%) |
| `random_state` | 42 | Reproducibility seed |
| `n_jobs` | -1 | Use all CPU cores |

**How scoring works:**
- `sklearn`'s `score_samples()` returns a value where *lower = more anomalous*
- InsiEDR negates this: `risk_score = -model.score_samples(X)`, so **higher = more anomalous**

### 3.3 Risk Aggregation

After scoring, 4 domain risk scores are produced per user-day:

| Output Column | Source |
|---------------|--------|
| `logon_risk` | Logon Isolation Forest anomaly score |
| `file_risk` | File Isolation Forest anomaly score |
| `device_risk` | Device Isolation Forest anomaly score |
| `http_risk` | HTTP Isolation Forest anomaly score |
| `overall_risk` | Mean of 4 domain risks, rescaled so max = 1.0 |
| `raw_overall_risk` | Unscaled mean of 4 domain risks |
| `daily_risk_delta` | Day-to-day change in `overall_risk` |
| `daily_risk_rolling_mean_7d` | 7-day rolling mean of `overall_risk` |
| `daily_risk_rolling_std_7d` | 7-day rolling standard deviation of `overall_risk` |

### 3.4 Output Files

| File | Description |
|------|-------------|
| `latest_data/if_enriched_features.csv` | Complete dataset: 31 raw features + 9 risk features per user-day |
| `latest_data/raw_features.csv` | Raw statistical features only (no risk scores) |
| `output/domain_isolation_forest.pkl` | Trained Isolation Forest model (for inference API) |

---

## 4. Stage 2: SHAP Domain Weighting

**Script:** `run_new_model.py` — STEP 2 & STEP 3 (Lines 135–178)

### 4.1 Purpose

Not all behavioral domains are equally important for detecting insiders. SHAP (SHapley Additive exPlanations) analysis determines which domain risks are most predictive of insider activity.

### 4.2 How the SHAP Weights Were Originally Calculated

A separate script (`feature_importance/feature_importance.py`) trained a binary XGBoost classifier on only the 4 domain risk scores to predict insider vs. normal. `shap.TreeExplainer` then calculated the global mean absolute SHAP value for each domain, and these were normalized to sum to 1.0.

### 4.3 Current Hardcoded Weights

| Domain | Weight | Interpretation |
|--------|--------|----------------|
| `http_risk` | **61.45%** | HTTP browsing anomalies are the strongest insider signal |
| `logon_risk` | **18.69%** | Login/logout anomalies are the second strongest signal |
| `file_risk` | **17.37%** | File access anomalies are moderately important |
| `device_risk` | **2.50%** | USB/device anomalies have the least predictive power |

### 4.4 Weighted Overall Risk Computation

The pipeline replaces the simple mean-based `overall_risk` (from Stage 1) with a SHAP-weighted version:

```
raw_overall_risk = (file_risk × 0.1737) + (device_risk × 0.0250) +
                   (http_risk × 0.6145) + (logon_risk × 0.1869)

max_raw_train_score = max(raw_overall_risk for all training users)

overall_risk = min(raw_overall_risk / max_raw_train_score, 1.0)
```

### 4.5 Trend Feature Recomputation

After recalculating `overall_risk`, three rolling trend features are recomputed:

| Feature | Formula |
|---------|---------|
| `daily_risk_delta` | `overall_risk[today] - overall_risk[yesterday]` |
| `daily_risk_rolling_mean_7d` | 7-day rolling average of `overall_risk` |
| `daily_risk_rolling_std_7d` | 7-day rolling standard deviation of `overall_risk` |

### 4.6 Output Files

| File | Description |
|------|-------------|
| `output/weights.json` | SHAP weights dictionary (used by inference API) |
| `output/if_enriched_features_shap.csv` | Full dataset with SHAP-weighted risk scores |

---

## 5. Stage 3: XGBoost Multiclass Scenario Classifier

**Script:** `run_new_model.py` — STEP 1 & STEP 4 (Lines 117–271)

### 5.1 Purpose

While Stage 1 detects *anomalous* behavior, Stage 3 classifies *what type* of insider threat is occurring. It distinguishes between 6 scenarios.

### 5.2 Scenario Classes

| Class ID | Label | Description |
|----------|-------|-------------|
| 0 | `normal` | Normal employee behavior |
| 1 | `email_exfil` | Data exfiltration through email channels |
| 2 | `sabotage` | Deliberate damage to systems or data |
| 3 | `usb_exfil` | Data exfiltration through USB storage devices |
| 4 | `flight_risk` | Employee planning to leave the organization (e.g., browsing job sites) |
| 5 | `cloud_exfil` | Data exfiltration through cloud services (Dropbox, etc.) |

### 5.3 Data Splitting

The pipeline performs an **80/20 user-level stratified split**:
- **800 train users** / **200 test users**
- Stratified by `threat_scenario` so each scenario is proportionally represented in both splits
- The split is at the *user* level, not the row level — all days for a user go to the same split

### 5.4 Labeling Strategy

- Normal users (`is_insider == 0`): All their days are labeled as class `0` (normal)
- Insider users (`is_insider == 1`): All their days are labeled as class `1–5` based on their specific `threat_scenario`
- Other insider days that don't meet criteria: Marked as `-1` and excluded from training/evaluation

### 5.5 Class Imbalance Handling (Manual Oversampling)

Since insider records are far fewer than normal records (~750 insider days vs ~55,000+ normal days), the pipeline uses **random oversampling with replacement**:

1. Count the number of normal (class 0) training records
2. For each of the 6 classes, randomly sample (with replacement) to match the class 0 count
3. This creates a perfectly balanced training set

### 5.6 XGBoost Model Configuration

| Hyperparameter | Value | Description |
|----------------|-------|-------------|
| `objective` | `multi:softprob` | Multiclass classification with probability output |
| `num_class` | 6 | Number of threat scenarios |
| `n_estimators` | 500 | Number of boosting rounds |
| `max_depth` | 6 | Maximum tree depth |
| `learning_rate` | 0.05 | Step size shrinkage |
| `subsample` | 0.8 | Row subsampling ratio |
| `colsample_bytree` | 0.8 | Column subsampling ratio |
| `eval_metric` | `mlogloss` | Multiclass log loss |
| `random_state` | 42 | Reproducibility |
| `n_jobs` | -1 | Use all CPU cores |

### 5.7 Input Features (40 total)

The XGBoost model takes all 40 features defined in `latest_data/models/scenario_xgb_features.json`:

- **31 raw statistical features** (from Stage 1)
- **4 domain risk scores**: `logon_risk`, `file_risk`, `device_risk`, `http_risk`
- **5 combined risk/trend features**: `overall_risk`, `raw_overall_risk`, `daily_risk_delta`, `daily_risk_rolling_mean_7d`, `daily_risk_rolling_std_7d`

### 5.8 Output

For every user-day record in the entire dataset, the model produces 6 probability columns:

| Output Column | Description |
|---------------|-------------|
| `rf_normal_prob` | Probability of being normal |
| `rf_email_exfil_prob` | Probability of email exfiltration |
| `rf_sabotage_prob` | Probability of sabotage |
| `rf_usb_exfil_prob` | Probability of USB exfiltration |
| `rf_flight_risk_prob` | Probability of flight risk |
| `rf_cloud_exfil_prob` | Probability of cloud exfiltration |

### 5.9 Output Files

| File | Description |
|------|-------------|
| `output/xgb_model.pkl` | Trained XGBoost classifier |
| `output/scenario_training_dataset_with_xgb_shap.csv` | Full dataset enriched with scenario probabilities |

---

## 6. Stage 4: RedRVFL Behavioral Sequence Drift Detection

**Script:** `run_new_model.py` — STEP 5 (Lines 273–358)

### 6.1 Purpose

XGBoost classifies each day independently. But insider threats often manifest as *gradual behavioral changes* over time. The RedRVFL (Reduced Random Vector Functional Link) neural network captures these temporal patterns by analyzing 7-day sequences and detecting **behavioral drift** — sudden deviations from expected patterns.

### 6.2 Risk Signal Fusion

Before feeding data into the RedRVFL, the pipeline creates a single fused risk signal per user-day:

```
scenario_risk = max(email_exfil_prob, sabotage_prob, usb_exfil_prob, flight_risk_prob, cloud_exfil_prob)

rvfl_risk = 0.3 × overall_risk + 0.7 × scenario_risk
```

This blends the Isolation Forest anomaly score (30% weight) with the XGBoost scenario classification confidence (70% weight) into one comprehensive risk value.

### 6.3 Sequence Construction

The `create_sequences()` function builds sliding window sequences:

- **Window size:** 7 days
- **Input shape:** `(num_sequences, 7, 1)` — 7 days of `rvfl_risk` per sequence
- **Target:** The `rvfl_risk` value of the 7th day
- Sequences are created per-user, so a user's sequence never crosses into another user's data

### 6.4 Feature Scaling

Two `MinMaxScaler` objects are fitted on the training data only:

| Scaler | What it scales | Range |
|--------|----------------|-------|
| `feature_scaler` | Input sequences (7-day `rvfl_risk` windows) | [0, 1] |
| `target_scaler` | Target values (day-7 `rvfl_risk`) | [0, 1] |

### 6.5 RedRVFL Architecture

The RedRVFL (Reduced Random Vector Functional Link) is a neural network architecture that combines:
- **Random LSTM layers** (frozen weights, no gradient-based training)
- **Ridge regression** (closed-form solution, no backpropagation)

#### Architecture Components

| Component | Class | Description |
|-----------|-------|-------------|
| `RandomLSTM` | `architecture.py` | An LSTM with randomly initialized, frozen weights. Acts as a fixed nonlinear feature extractor. |
| `RedRVFLOrchestrator` | `red_revfl_orchestrator.py` | Manages multiple RandomLSTM layers and constructs feature matrices. |
| `Ridge` | `sklearn.linear_model` | Trained analytically (closed-form) on the extracted features. |

#### Model Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `input_features` | 1 | Single input feature (`rvfl_risk`) |
| `hidden_size` | 128 | LSTM hidden state dimensionality |
| `num_layers` | 5 | Number of stacked RandomLSTM layers |
| `ridge_alpha` | 0.01 | L2 regularization strength |

#### How It Works (Layer by Layer)

1. **Layer 1:** Input sequence `(batch, 7, 1)` → RandomLSTM → hidden state `(batch, 128)`
2. **Feature Matrix D₁:** Concatenate `[hidden_state₁, flattened_input]` → `(batch, 128 + 7)`
3. **Ridge₁:** Fit `D₁ → y_target` using closed-form solution
4. **Layer 2:** Input becomes `[hidden_state₁ expanded across time, original input]` → shape `(batch, 7, 129)` → RandomLSTM → hidden state₂
5. **Feature Matrix D₂:** Concatenate `[hidden_state₂, flattened_input]` → Ridge₂
6. **Layers 3–5:** Same pattern with increasingly enriched representations
7. **Final Prediction:** Median of all 5 Ridge model predictions

#### Why Random Weights?

The LSTM weights are **randomly initialized and frozen** (no gradient training). This is by design:
- Training is extremely fast (only Ridge regression needs fitting)
- The random projections act as diverse nonlinear feature extractors
- Multiple layers with different random seeds capture different aspects of the temporal signal
- The ensemble of Ridge models (via median) provides robust predictions

### 6.6 Drift Detection (Prediction Error)

After training, the model predicts `rvfl_risk` for every user-day across the entire dataset. The **squared prediction error** measures how unexpected each day's behavior was:

```
error = (actual_rvfl_risk - predicted_rvfl_risk)²
```

- **Low error:** The user's behavior follows expected patterns → likely normal
- **High error:** The user's behavior deviates from expectations → potential insider

### 6.7 User-Level Score Aggregation

Daily errors are aggregated per user into a single `score_v2`:

```
score_v2 = max_error × mean_error × √(num_sequences)
```

| Component | Purpose |
|-----------|---------|
| `max_error` | Captures the single most anomalous day |
| `mean_error` | Captures sustained deviation over time |
| `√(num_sequences)` | Gives more weight to users with more data (more evidence) |

Users are then **ranked by `score_v2` in descending order**. The highest-scoring users are the most likely insiders.

### 6.8 Output Files

| File | Description |
|------|-------------|
| `output/rvfl_model.pkl` | Trained RedRVFL orchestrator (frozen LSTMs) |
| `output/rvfl_ridge_models.pkl` | List of 5 trained Ridge regression models |
| `output/feature_scaler.pkl` | MinMaxScaler for input sequences |
| `output/target_scaler.pkl` | MinMaxScaler for target values |
| `output/top_users_shap.csv` | All users ranked by `score_v2` with ground truth labels |

---

## 7. Evaluation: Top-K Review Queue

**Script:** `run_new_model.py` — STEP 6 (Lines 360–428)

### 7.1 Purpose

In a real Security Operations Center (SOC), analysts have limited time. The Top-K Review Queue simulates this by asking: "If we only review the top K most suspicious users, how many insiders do we catch?"

### 7.2 Metrics

| Metric | Formula | What it measures |
|--------|---------|-----------------|
| **Recall** | `insiders_found / total_insiders` | What fraction of all insiders are caught at this K? |
| **Precision** | `insiders_found / K` | Of the K users reviewed, what fraction are actual insiders? |

### 7.3 Evaluation Process

1. Filter to test users only (200 users)
2. Sort by `score_v2` descending
3. Start at K=5, increment by 5
4. At each K, report Recall and Precision
5. Stop when 100% Recall is achieved (all insiders found)
6. List each caught insider's user ID, score, and threat class

### 7.4 Example Output

```
Top-5    | Recall:  50.00% (5/10) | Precision: 100.00% (5/5)
          -> Insiders Found:
             U0430 (Score: 0.1888, Class: cloud_exfil)
             U0349 (Score: 0.1887, Class: sabotage)
             U0891 (Score: 0.1683, Class: sabotage)
             U0221 (Score: 0.1653, Class: flight_risk)
             U0719 (Score: 0.1545, Class: cloud_exfil)
Top-10   | Recall: 100.00% (10/10) | Precision: 100.00% (10/10)
          -> Insiders Found:
             ... (all 10 insiders)
```

### 7.5 Output Files

| File | Description |
|------|-------------|
| `output/confusion_matrix.txt` | Complete evaluation report (XGBoost classification report + Top-K results) |
| `output/trained_users.txt` | List of 800 train user IDs |
| `output/testing_users.txt` | List of 200 test user IDs |

---

## 8. Complete Output Files Summary

All output files are saved to `final_model/output/`:

| File | Stage | Description |
|------|-------|-------------|
| `domain_isolation_forest.pkl` | Stage 1 | 4 trained domain IF models |
| `weights.json` | Stage 2 | SHAP domain weights |
| `if_enriched_features_shap.csv` | Stage 2 | Dataset with SHAP-weighted risks |
| `xgb_model.pkl` | Stage 3 | Trained XGBoost classifier |
| `xgb_confusion_matrix.csv` | Stage 3 | Confusion matrix dataframe for XGBoost multiclass classification |
| `xgb_classification_report.txt` | Stage 3 | Complete precision, recall, f1-score & confusion matrix for XGBoost |
| `scenario_training_dataset_with_xgb_shap.csv` | Stage 3 | Dataset enriched with scenario probabilities |
| `rvfl_model.pkl` | Stage 4 | Trained RedRVFL neural network |
| `rvfl_ridge_models.pkl` | Stage 4 | 5 Ridge regression models |
| `feature_scaler.pkl` | Stage 4 | Input sequence scaler |
| `target_scaler.pkl` | Stage 4 | Target value scaler |
| `top_users_shap.csv` | Stage 4 | All users ranked by insider threat score |
| `confusion_matrix.txt` | Evaluation | Full evaluation report |
| `trained_users.txt` | Data Split | Training user IDs |
| `testing_users.txt` | Data Split | Testing user IDs |

---

## 9. Folder Structure

```
final_model/
├── INPUT_LOGS/                          # Raw input data
│   ├── logon.csv
│   ├── file.csv
│   ├── device.csv
│   ├── http.csv
│   └── OUTPUT_LABELS/
│       └── insider_labels.csv
│
├── latest_data/                         # Intermediate data
│   ├── raw_features.csv                 # 31 raw features (no risk scores)
│   ├── if_enriched_features.csv         # Features + IF risk scores
│   └── models/
│       └── scenario_xgb_features.json   # 40 feature names for XGBoost
│
├── output/                              # All trained models and results
│   ├── domain_isolation_forest.pkl
│   ├── weights.json
│   ├── xgb_model.pkl
│   ├── rvfl_model.pkl
│   ├── rvfl_ridge_models.pkl
│   ├── feature_scaler.pkl
│   ├── target_scaler.pkl
│   ├── top_users_shap.csv
│   ├── confusion_matrix.txt
│   └── ...
│
├── src/                                 # Source code modules
│   ├── architecture.py                  # RandomLSTM, feature matrix builders
│   ├── red_revfl_orchestrator.py        # RedRVFL orchestrator class
│   ├── server/
│   │   ├── anomaly/
│   │   │   ├── isolation_forest.py      # IFDetector wrapper
│   │   │   ├── domain_models.py         # DomainIsolationForest (4 IFs)
│   │   │   └── rolling_features.py      # Risk trend feature computation
│   │   └── features/
│   │       ├── feature_schema.py        # Domain feature column definitions
│   │       ├── cert_behavioural.py      # Feature extractor orchestrator
│   │       └── extractors/
│   │           ├── logon.py             # Logon feature extraction
│   │           ├── file.py              # File feature extraction
│   │           ├── device.py            # Device feature extraction
│   │           └── http.py              # HTTP feature extraction
│   └── run/
│       └── feature_to_sequence.py       # Sliding window sequence builder
│
├── inference/                           # Stateless REST API
│   ├── app.py                           # FastAPI application
│   ├── test_inference.py                # API test script
│   ├── requirements.txt                 # Python dependencies
│   └── DOCUMENTATION.md                 # API documentation
│
├── feature_importance/                  # SHAP weight calculation (standalone)
│   └── feature_importance.py            # XGBoost + SHAP analysis script
│
├── domain_features/                     # Feature name references
│   ├── logon_features.txt
│   ├── file_features.txt
│   ├── device_features.txt
│   └── http_features.txt
│
├── run_new_model.py                     # Unified Pipeline: IF + SHAP + XGBoost + RedRVFL
└── readme/
    └── PIPELINE_DOCUMENTATION.md        # This file
```

---

## 10. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | ≥ 2.0 | Data manipulation |
| `numpy` | ≥ 1.26 | Numerical computation |
| `scikit-learn` | ≥ 1.5 | Isolation Forest, Ridge Regression, MinMaxScaler, Metrics |
| `xgboost` | ≥ 3.0 | Multiclass gradient boosted classifier |
| `torch` | ≥ 2.0 | RandomLSTM neural network layers |
| `shap` | ≥ 0.40 | SHAP feature importance (imported but currently using hardcoded weights) |
| `joblib` | ≥ 1.5 | Model serialization (.pkl files) |
| `scipy` | ≥ 1.14 | Shannon entropy calculations in feature extractors |
| `fastapi` | ≥ 0.141 | Inference REST API framework |
| `uvicorn` | ≥ 0.46 | ASGI web server for FastAPI |
