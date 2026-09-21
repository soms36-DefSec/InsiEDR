# InsiEDR New Dataset Pipeline Project Report

## 1. Overview
InsiEDR is an endpoint threat detection pipeline designed to identify malicious insider activities within an enterprise network. The system processes raw endpoint telemetry logs and passes them through a three-tier architecture: unsupervised anomaly detection using Isolation Forests to capture daily baseline deviation, supervised multiclass classification via XGBoost to categorize threat scenarios, and recurrent temporal drift modeling using a Recurrent Random Vector Functional Link (RedRVFL) network. By analyzing daily activities as sequential patterns rather than isolated events, InsiEDR aims to detect complex, multi-day threat progressions before data exfiltration or sabotage occurs.

---

## 2. Glossary

* **Isolation Forest (IF)**: An unsupervised learning algorithm that isolates anomalies by randomly partitioning feature spaces. In this pipeline, it is used to assign daily anomaly scores to user-days without relying on historical threat labels.
* **RedRVFL (Recurrent Random Vector Functional Link)**: A hybrid recurrent neural network architecture that combines frozen, randomly initialized LSTM weights with a linear Ridge regression readout layer. It models temporal dependencies in user behavior sequences and generates predictions without backpropagation.
* **SMOTE (Synthetic Minority Over-sampling Technique)**: A data augmentation technique that synthesizes new examples of minority classes by interpolating between existing minority samples. It is used to balance the highly skewed scenario classes in the training set before fitting the XGBoost classifier.
* **GroupShuffleSplit**: A cross-validation splitting technique that ensures all daily records of any individual user are kept entirely within either the training split or the test split, preventing data leakage across user identities.
* **score_v1 / score_v2**: Metrics used to rank users by threat severity. While `score_v1` is a basic average of sequence prediction errors, `score_v2` is computed as $max\_error \times mean\_error \times \sqrt{anomaly\_days}$, penalizing both extreme daily deviation and persistent abnormal behavior.
* **Top-N Recall / Precision**: Evaluation metrics that measure model effectiveness within a fixed review queue of size $N$. Recall is the percentage of total insiders successfully detected in the Top-N queue, while Precision is the proportion of true insiders among all users in the queue.

---

## 3. Pipeline Stage-by-Stage Implementation

### Stage 1: Data Preprocessing
* **Script Path**: [latest_data_prep.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_data_prep.py)
* **Actions**: Reads raw logon, device, file, and browser logs from `INPUT_LOGS/`. Renames key columns (`timestamp` $\rightarrow$ `date`, `user_id` $\rightarrow$ `user`, `event_id` $\rightarrow$ `id`) to align schemas. Saves cleaned logs to `latest_data/raw_logs/`.
* **Deviations from CERT r4.2**: Functions as an ingestion adapter to map the new dataset's distinct raw schema columns to the expected pipeline format.

### Stage 2: Feature Extraction
* **Script Path**: [latest_feature_extractor.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_feature_extractor.py)
* **Actions**: Instantiates `CERTBehavioralExtractor` and browser-domain feature parsers. Computes daily features for all users, merges them on `(user, date)`, and filters them to the 34 columns defined in `models/feature_columns_IF.json`. Outputs `latest_data/if_enriched_features.csv`.
* **Deviations from CERT r4.2**: None. The feature extraction math and logic are identical.

### Stage 3: Isolation Forest Recalibration
* **Script Path**: [latest_anomaly_scoring.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_anomaly_scoring.py)
* **Actions**: Fits Logon, File, Device, and HTTP domain Isolation Forest models. Standardizes overall risk scores by dividing by the observed raw maximum cohort score of `0.7300` to scale output scores to a maximum of `1.0`.
* **Deviations from CERT r4.2**: The scaling divisor was adjusted from `0.7287` (the maximum raw score on CERT r4.2) to `0.7300` to properly calibrate the risk scores on the new dataset.

### Stage 4: XGBoost Scenario Classifier
* **Script Path**: [latest_xgb_classifier.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_xgb_classifier.py)
* **Actions**: Splits users into 80% train and 20% test splits. Balances train splits via SMOTE, fits a 6-class XGBoost model, and appends daily threat scenario probabilities to `latest_data/scenario_training_dataset_with_xgb.csv`.
* **Deviations from CERT r4.2**: **This stage contains a major methodology change.** The original CERT pipeline used exact start/end timestamps to label threat days. The new dataset provides only user-level scenario classes. To prevent user-identity leakage, a trailing 10-day active window labeling strategy was implemented: only the final 10 active days of a threat user are labeled as Classes 1-5. All remaining active days for that user are excluded from the dataset entirely. Normal class (Class 0) samples are drawn exclusively from users with no scenario flag.

### Stage 5: RedRVFL Sequence Drift Modeling
* **Script Path**: [latest_rvfl_orchestrator.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_rvfl_orchestrator.py)
* **Actions**: Fuses daily overall risk and max scenario probabilities: $\text{rvfl\_risk} = 0.3 \times \text{overall\_risk} + 0.7 \times \max(\text{scenario\_probs})$. Builds chronological 7-day sequences per user, fits a 5-layer RedRVFL network using Ridge regression on the training split, and computes sequence drift errors (MSE). Ranks test split users using `score_v2` and outputs `latest_data/top_users.csv`.
* **Deviations from CERT r4.2**: Restricts Ridge regression fitting to the training split users (the original run did not isolate test users during Ridge training) and implements sequence window predictions strictly within individual user timelines.

### Stage 6: Evaluation
* **Script Path**: [latest_evaluator.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_evaluator.py)
* **Actions**: Measures ranking recall, precision, and F1-scores of `score_v2` in Top-5, Top-10, and Top-25 queues on the 200 held-out test split users.
* **Deviations from CERT r4.2**: Evaluates user rankings solely on the 200 held-out test users rather than the full user cohort.

---

## 4. The Bug We Found and Fixed

During validation of the sequence drift stage, a major implementation error was discovered in [latest_rvfl_orchestrator.py](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/latest_rvfl_orchestrator.py).

### The NumPy Broadcasting Bug
In the error calculation step, the target vector `y_all` (a 2D array of shape `(N, 1)`) was subtracted from the predicted vector `y_pred` (a 1D array of shape `(N,)` returned by the Ridge models). 
Because of the differing dimensions, NumPy broadcast the subtraction, resulting in a matrix of shape `(N, N)` instead of a 1D error array of shape `(N,)`. When `np.mean(..., axis=1)` was executed, it calculated the average error of user $i$ against the predictions of **all other users** in the dataset. This distorted the sequence drift MSE, mixing normal and anomalous error timelines.

### Code Diff of the Fix
```diff
     X_all_tensor = torch.tensor(X_all, dtype=torch.float32)
     y_pred = model.predict(X_all_tensor, ridge_models)
     
-    # Compute MSE prediction error
-    errors = np.mean(np.square(y_all - y_pred), axis=1)
+    # Compute MSE prediction error (avoiding 2D/1D broadcasting bug)
+    errors = np.square(y_all.ravel() - y_pred.ravel())
```

### Impact on Metrics
Before this bug was fixed, the system reported an artificially perfect Top-10 Recall of `1.0000` (10/10 test insiders detected with 0 false positives). The pre-fix "perfect" scores were an artifact of this broadcasting error, which averaged out individual user variations and masked true model performance.

Following the fix, the models were retrained and evaluated. The post-bugfix metrics are the correct, verified results:

| Metric | Top-5 Review Queue | Top-10 Review Queue | Top-25 Review Queue |
| :--- | :---: | :---: | :---: |
| **Detected Insiders** | 5 / 10 | 9 / 10 | 10 / 10 |
| **Recall** | 0.5000 | **0.9000** | 1.0000 |
| **Precision** | 1.0000 | **0.9000** | 0.4000 |
| **F1-Score** | 0.6667 | **0.9000** | 0.5714 |

---

## 5. Dataset Profile

* **Scale**: 1,000 unique users (`U0001` to `U1000`) and **67,112 total user-days** of activity.
* **Feature Count**: 34 daily features across Logon, File, Device, and HTTP domains.
* **Class Mapping & Trailing-Window Exclusions**:
  * **Normal Users**: 950 users, contributing **63,356 user-days** (Class 0, 100% included).
  * **Insider Threat Users**: 50 users (10 per scenario), contributing **3,756 active days** total.
    * **Labeled Threat Days**: **500 user-days** (Class 1-5, 10 trailing days per user).
    * **Excluded Days**: **3,256 user-days** (Class -1, non-trailing days of insider users omitted from training/testing). This represents **4.85% of total dataset rows** and **86.69% of the insider threat users' timeline**.

---

## 6. Verification Results (Post-Bugfix)

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

---

## 7. Critical Interpretation of Results

### A. Impact of the Trailing-Window Labeling Exclusion
The exclusion of **3,256 mixed-activity days** (86.69% of the insider threat users' timeline) removed the transitional phases where a user shifts from normal behavior to malicious actions. By training and testing only on the 10-day active windows and completely ignoring the other days, the model was evaluated on a binary contrast between normal profiles and active attack states. Removing these transitional, low-signal days deletes the ambiguous data points where classification errors occur, artificially inflating the downstream recall and precision metrics.

### B. Volatility Due to Small Cohort Size
The evaluation split contains only 10 target insiders out of 200 test users. Because the positive sample size is small, Top-N metrics are highly volatile. A single insider shifting positions in the ranking queue alters recall by 10 percentage points, meaning these results are highly sensitive to small dataset variations and do not prove stable generalization.

### C. Direct Verdict on Performance Drivers
**The high detection rates observed in this run are primarily driven by the labeling methodology change (the trailing-window labeling and mixed-activity day exclusion) rather than an increase in model capability or dataset quality.** 

By removing 86.69% of the threat users' active history, the dataset was simplified to a clean boundary that the XGBoost classifier could partition with minimal error. This run demonstrates that the pipeline can identify clean, high-signal anomalies under a simplified labeling scheme, but it does not establish equivalent performance on continuous, unfiltered EDR data streams.

---

## 8. Demo Instructions

A diagnostic check utility is provided to demonstrate the inference steps on test users. To run a side-by-side comparison between an unseen test-split insider (`U0430`, cloud exfiltration scenario) and an unseen test-split normal user (`U0002`):

```powershell
python latest_data/check_insider.py --compare
```

### Verified Demo Console Output

```text
================================================================================
INSIDER THREAT CHECK — USER: U0430
WHAT THIS TOOL DOES: Analyzes daily endpoint logs to detect abnormal user behavior 
and classifies potential insider threat paths using a three-tier model pipeline.
================================================================================

STAGE 1: DAILY ANOMALY SCORE (Isolation Forest)
Checks each day's behavior against what's normal for this user population.

| Date       | Domain Scores (L:Logon, F:File, D:Device, H:HTTP) | Overall Risk | Risk Tier |
| :---       | :---                                              | :---:        | :---:     |
| 2024-01-01 | L:0.4273 F:0.5424 D:0.4607 H:0.5934 | 0.6931 | MEDIUM |
| 2024-01-02 | L:0.4563 F:0.5142 D:0.4607 H:0.3764 | 0.6190 | MEDIUM |
| ...        | ...                                                 | ...    | ...      |
| 2024-03-30 | L:0.6398 F:0.6304 D:0.4607 H:0.7859 | 0.8619 | HIGH |
| 2024-03-31 | L:0.7166 F:0.7270 D:0.4607 H:0.7761 | 0.9180 | HIGH |

STAGE 2: THREAT TYPE CLASSIFICATION (XGBoost)
Predicts which of 6 categories each day's behavior resembles.

| Date       | Predicted Class   | Confidence |
| :---       | :---              | :---:      |
| 2024-01-01 | normal          | 100.00% |
| ...        | ...             | ...    |
| 2024-03-30 | cloud_exfil     | 100.00% |
| 2024-03-31 | flight_risk     | 99.99% |

STAGE 3: BEHAVIORAL DRIFT OVER TIME (RedRVFL)
Looks at the pattern across days, not just single days.

Sequence length: 76 days | Drift error (MSE): 0.028778 | Final risk score: 0.206403

FINAL VERDICT

This user ranks #2 out of 200 test users. Top-10 threshold: 0.042845

VERDICT: FLAGGED FOR REVIEW
Ground truth (verification only, not used in scoring): Insider - cloud_exfil
Model verdict matches ground truth: YES
================================================================================

================================================================================
INSIDER THREAT CHECK — USER: U0002
WHAT THIS TOOL DOES: Analyzes daily endpoint logs to detect abnormal user behavior 
and classifies potential insider threat paths using a three-tier model pipeline.
================================================================================

STAGE 1: DAILY ANOMALY SCORE (Isolation Forest)
Checks each day's behavior against what's normal for this user population.

| Date       | Domain Scores (L:Logon, F:File, D:Device, H:HTTP) | Overall Risk | Risk Tier |
| :---       | :---                                              | :---:        | :---:     |
| 2024-01-01 | L:0.3850 F:0.6104 D:0.4607 H:0.5843 | 0.6987 | MEDIUM |
| ...        | ...                                                 | ...    | ...      |
| 2024-03-29 | L:0.3708 F:0.4666 D:0.4607 H:0.3793 | 0.5744 | MEDIUM |

STAGE 2: THREAT TYPE CLASSIFICATION (XGBoost)
Predicts which of 6 categories each day's behavior resembles.

| Date       | Predicted Class   | Confidence |
| :---       | :---              | :---:      |
| 2024-01-01 | normal          | 99.99% |
| ...        | ...             | ...    |
| 2024-03-29 | normal          | 100.00% |

STAGE 3: BEHAVIORAL DRIFT OVER TIME (RedRVFL)
Looks at the pattern across days, not just single days.

Sequence length: 66 days | Drift error (MSE): 0.000158 | Final risk score: 0.000001

FINAL VERDICT

This user ranks #180 out of 200 test users. Top-10 threshold: 0.042845

VERDICT: NOT FLAGGED
Ground truth (verification only, not used in scoring): Normal
Model verdict matches ground truth: YES
================================================================================
```

---

## 9. Limitations & Next Steps

1. **Retroactive Labeling Test**: Apply the trailing-window labeling and mixed-activity day exclusion retroactively to the original CERT r4.2 dataset to isolate the performance impact of the labeling methodology from the differences in the underlying data.
2. **Sensitivity Analysis on Window Sizes**: Retrain the pipeline using different trailing active windows (e.g., 5, 15, 30, and 45 days) to measure how the inclusion of transitional days affects classification boundaries and metrics.
3. **Repeated splits for Cross-Validation**: Execute k-fold cross-validation with at least 5 different random seeds to confirm that the perfect recall is not an artifact of a favorable user split.
4. **Cross-Dataset Evaluation**: Test the trained pipeline against an entirely independent dataset where the model has never observed any telemetry from the target users during any phase of training.
