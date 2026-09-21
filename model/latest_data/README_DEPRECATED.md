# InsiEDR Pipeline Run on Latest Dataset

## 1. Overview
This document describes the execution and evaluation of the InsiEDR pipeline on the new dataset. The pipeline employs a three-tier detection architecture: unsupervised anomaly detection using Isolation Forest models, supervised multiclass classification via XGBoost, and sequence drift modeling using a Recurrent Random Vector Functional Link (RedRVFL) network. All code, data preparation scripts, intermediate features, and trained models for this run are isolated within the `latest_data/` directory.

---

## 2. Stage-by-Stage Implementation

### Stage 1: Data Preprocessing
* **Script**: [latest_data_prep.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_data_prep.py)
* **Mechanical Actions**: Loads raw logs (`logon.csv`, `device.csv`, `file.csv`, and `http.csv`) from `INPUT_LOGS/`. Renames columns: `timestamp` to `date`, `user_id` to `user`, and `event_id` to `id`. Saves the processed outputs to `latest_data/raw_logs/`.
* **Deviations from CERT r4.2**: The column names in the new dataset raw logs differed from the original CERT schema. This script acts as an ingestion wrapper to align the schemas; no other structural changes were made at this stage.

### Stage 2: Feature Extraction
* **Script**: [latest_feature_extractor.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_feature_extractor.py)
* **Mechanical Actions**: Instantiates `CERTBehavioralExtractor` and calls `extract_http_features` to compute daily features for each user. Merges the outputs on `(user, date)` and filters the features to match the 34 columns specified in `models/feature_columns_IF.json`. Saves the resulting table to `latest_data/if_enriched_features.csv`.
* **Deviations from CERT r4.2**: None. The feature extraction logic is identical to the CERT r4.2 run.

### Stage 3: Isolation Forest Training & Anomaly Scoring
* **Script**: [latest_anomaly_scoring.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_anomaly_scoring.py)
* **Mechanical Actions**: Fits four separate `IsolationForest` models (contamination=0.05) representing Logon, File, Device, and HTTP domains. For each daily record, it computes domain risk scores and their raw average to get the overall risk.
* **Deviations from CERT r4.2**: Standardizes the final `overall_risk` column inside `if_enriched_features.csv` by dividing by the observed cohort maximum score of `0.7300`. This scales the overall risk to a maximum of `1.0` to match the project's static threshold definitions. The raw, unscaled overall score is saved in a separate column (`raw_overall_risk`) for auditing.

### Stage 4: XGBoost Scenario Classification
* **Script**: [latest_xgb_classifier.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_xgb_classifier.py)
* **Mechanical Actions**: Maps users to 6 scenario classes (0 = Normal, 1 = email_exfil, 2 = sabotage, 3 = usb_exfil, 4 = flight_risk, 5 = cloud_exfil). Splits the 1,000 users into 80% train and 20% test using a stratified split. Balances train splits via SMOTE for classes 1-5, fits an `XGBClassifier` (num_class=6), and writes predicted class probabilities to the dataset.
* **Deviations from CERT r4.2**: **This stage contains a major methodology change.** The original CERT r4.2 pipeline labeled threat days using explicit start and end timestamps. In the new dataset, only user-level labels exist. To prevent user-identity leakage into the features, a trailing 10-day active window labeling strategy was implemented: only the final 10 active days of a threat user are labeled with their scenario class (Classes 1-5). All remaining active days for that user are excluded from the training and test splits entirely. Normal class (Class 0) samples are drawn exclusively from users with no scenario flag.

### Stage 5: RedRVFL Sequence Drift Modeling
* **Script**: [latest_rvfl_orchestrator.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_rvfl_orchestrator.py)
* **Mechanical Actions**: Fuses the overall Isolation Forest risk and maximum XGBoost scenario probability: $\text{rvfl\_risk} = 0.3 \times \text{overall\_risk} + 0.7 \times \max(\text{scenario\_probs})$. Builds chronological 7-day sliding sequences per user. Fits a 5-layer RedRVFL network (hidden_size=128) via Ridge regression on the training users to predict risk, computing daily Mean Squared Error (MSE) drift values. Computes user scores: $\text{score\_v2} = \text{max\_error} \times \text{mean\_error} \times \sqrt{\text{anomaly\_days}}$ and saves the ranked results to `latest_data/top_users.csv`.
* **Deviations from CERT r4.2**: The network was trained strictly on the 800 training users and evaluated on the 200 held-out test users, preventing user-level leakage. The original run did not isolate test users during RedRVFL training.

### Stage 6: Recall Evaluation
* **Script**: [latest_evaluator.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_evaluator.py)
* **Mechanical Actions**: Evaluates detection recall, precision, and F1-score of `score_v2` rankings inside Top-5, Top-10, and Top-25 queues on the 200 held-out test users.
* **Deviations from CERT r4.2**: Evaluates user rankings solely on the 200 held-out test split users rather than the full user cohort.

---

## 3. Dataset Profile

* **Total Scale**: 1,000 unique users (`U0001` to `U1000`) and **67,112 user-days** of activity.
* **Feature Count**: 34 daily features across Logon, File, Device, and HTTP domains.
* **Class Mapping & Trailing-Window Exclusions**:
  * **Normal Users**: 950 users, contributing **63,356 user-days** (Class 0, all days included).
  * **Insider Threat Users**: 50 users (10 per scenario), contributing **3,756 active days** total.
    * **Labeled Threat Days**: **500 user-days** (Class 1-5, 10 trailing days per user).
    * **Excluded Days**: **3,256 user-days** (Class -1, non-trailing days of insider users omitted from training/testing).

---

## 4. Run Results

### Isolation Forest Score Tiers (Step 3)
* **Raw Overall Score**: Min: `0.4014`, Max: `0.7300`, Mean: `0.4437`
* **Recalibrated Overall Score**: Min: `0.5498`, Max: `1.0000`, Mean: `0.6079`
* **Risk Tier Distribution**:
  * **HIGH (>= 0.80)**: 1,264 user-days (1.88%)
  * **MEDIUM (>= 0.50)**: 65,848 user-days (98.12%)
  * **LOW (< 0.50)**: 0 user-days (0.00%)

### XGBoost Scenario Classifier Performance (Step 4)
Evaluated on the labeled portion of the 200 held-out test users (12,786 total test rows):

| Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `normal` (Class 0) | 0.9999 | 0.9997 | 0.9998 | 12,686 |
| `email_exfil` (Class 1) | 0.8261 | 0.9500 | 0.8837 | 20 |
| `sabotage` (Class 2) | 1.0000 | 1.0000 | 1.0000 | 20 |
| `usb_exfil` (Class 3) | 1.0000 | 1.0000 | 1.0000 | 20 |
| `flight_risk` (Class 4) | 0.9524 | 1.0000 | 0.9756 | 20 |
| `cloud_exfil` (Class 5) | 1.0000 | 0.9500 | 0.9744 | 20 |

### RedRVFL Sequence Drift Rankings (Step 5 & 6)
Evaluated on the 200 held-out test users (including 10 target insiders):

| Metric | Top-5 Queue | Top-10 Queue | Top-25 Queue |
| :--- | :---: | :---: | :---: |
| **Detected Insiders** | 5 / 10 | 9 / 10 | 10 / 10 |
| **Recall** | 0.5000 | 0.9000 | 1.0000 |
| **Precision** | 1.0000 | 0.9000 | 0.4000 |
| **F1-Score** | 0.6667 | 0.9000 | 0.5714 |

---

## 5. Critical Interpretation of Results

### A. Scrutiny of High and Near-Perfect Metrics
The XGBoost model achieved perfect precision or recall (1.0000) on three of the threat classes, and the end-to-end RedRVFL ranking placed 9 of 10 target insiders in ranks 1-10 with only 1 false positive (F1-score of 0.9000 at Top-10). In a security context, near-perfect metrics indicate that the classification task has been artificially simplified. The synthetic generation of threat scenarios likely uses deterministic thresholds or extreme values (e.g., specific high-volume file transfers or off-hours logins) that do not overlap with normal background activity. Consequently, the model is evaluating a highly distinct signature rather than a complex behavioral pattern.

### B. Impact of the Trailing-Window Labeling Exclusion
The exclusion of **3,256 mixed-activity days** (86.69% of the insider threat users' timeline) removed the transitional phases where a user shifts from normal behavior to malicious actions. By training and testing only on the 10-day active windows and completely ignoring the other days, the model was evaluated on a binary contrast between normal profiles and active attack states. Removing these transitional, low-signal days deletes the ambiguous data points where classification errors occur, artificially inflating the downstream recall and precision metrics.

### C. Volatility Due to Small Cohort Size
The evaluation split contains only 10 target insiders out of 200 test users. Because the positive sample size is small, Top-N metrics are highly volatile. A single insider shifting positions in the ranking queue alters recall by 10 percentage points, meaning these results are highly sensitive to small dataset variations and do not prove stable generalization.

### D. Direct Verdict on Run Performance
**The high detection rates observed in this run are primarily driven by the labeling methodology change (the trailing-window labeling and mixed-activity day exclusion) rather than an increase in model capability or dataset quality.** 

By removing 86.69% of the threat users' active history, the dataset was simplified to a clean boundary that the XGBoost classifier could partition with minimal error. This run demonstrates that the pipeline can identify clean, high-signal anomalies under a simplified labeling scheme, but it does not establish equivalent performance on continuous, unfiltered EDR data streams.

---

## 6. Limitations & Next Steps

To validate these findings, the following actions are required:
1. **Retroactive Labeling Analysis**: Apply the trailing-window labeling and mixed-activity day exclusion retroactively to the original CERT r4.2 dataset. This is necessary to isolate the performance impact of the labeling methodology from the differences in the underlying data.
2. **Sensitivity Analysis on Window Sizes**: Retrain the pipeline using different trailing active windows (e.g., 5, 15, 30, and 45 days) to measure how the inclusion of transitional days affects classification boundaries and metrics.
3. **Repeated splits for Cross-Validation**: Execute k-fold cross-validation with at least 5 different random seeds to confirm that the perfect recall is not an artifact of a favorable user split.
4. **Cross-Dataset Evaluation**: Test the trained pipeline against an entirely independent dataset where the model has never observed any telemetry from the target users during any phase of training.
