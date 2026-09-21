# InsiEDR Model Pipeline Performance Comparison

## Executive Summary
This report compares the performance of the InsiEDR pipeline using the `score_v2` ranking metric ($max\_error \times mean\_error \times \sqrt{anomaly\_days}$) on the original CERT r4.2 dataset vs. the newly adapted dataset.

> [!WARNING]
> **Important Caveat**: The Isolation Forest anomaly scoring thresholds and the label density differ significantly between these two datasets. In particular, the new dataset contains 5% target insider users in the test set (10/200), whereas the old CERT r4.2 dataset contained ~4.5% (9/198). Furthermore, threat day definitions differ. Therefore, these recall, precision, and F1-score comparisons are not strictly apples-to-apples, but rather serve as a baseline transfer sanity-check.

## Side-by-Side Metrics Table

| Dataset / Metric | Top-5 Review Queue | Top-10 Review Queue | Top-25 Review Queue |
| :--- | :---: | :---: | :---: |
| **CERT r4.2 (Old) Recall** | 0.4444 (4/9) | **1.0000** (9/9) | 1.0000 (9/9) |
| **New Dataset Recall** | 0.5000 (5/10) | **0.7000** (7/10) | 0.8000 (8/10) |
| | | | |
| **CERT r4.2 (Old) Precision** | 0.8000 | **0.9000** | 0.3600 |
| **New Dataset Precision** | 1.0000 | **0.7000** | 0.3200 |
| | | | |
| **CERT r4.2 (Old) F1-Score** | 0.5714 | **0.9474** | 0.5294 |
| **New Dataset F1-Score** | 0.6667 | **0.7000** | 0.4571 |

## Overall Binary Confusion Matrices (New Dataset)

### 5-User Review Queue (Top-5)
* **True Positives (TP)**: 5 (Insiders correctly flagged)
* **False Positives (FP)**: 0 (Normal users incorrectly flagged)
* **False Negatives (FN)**: 5 (Insiders missed)
* **True Negatives (TN)**: 190 (Normal users correctly ignored)

| | Predicted Insider (Flagged) | Predicted Normal (Ignored) |
| :--- | :---: | :---: |
| **Actual Insider** | **5** (TP) | 5 (FN) |
| **Actual Normal** | 0 (FP) | **190** (TN) |

### 10-User Review Queue (Top-10)
* **True Positives (TP)**: 7 (Insiders correctly flagged)
* **False Positives (FP)**: 3 (Normal users incorrectly flagged)
* **False Negatives (FN)**: 3 (Insiders missed)
* **True Negatives (TN)**: 187 (Normal users correctly ignored)

| | Predicted Insider (Flagged) | Predicted Normal (Ignored) |
| :--- | :---: | :---: |
| **Actual Insider** | **7** (TP) | 3 (FN) |
| **Actual Normal** | 3 (FP) | **187** (TN) |

### 25-User Review Queue (Top-25)
* **True Positives (TP)**: 8 (Insiders correctly flagged)
* **False Positives (FP)**: 17 (Normal users incorrectly flagged)
* **False Negatives (FN)**: 2 (Insiders missed)
* **True Negatives (TN)**: 173 (Normal users correctly ignored)

| | Predicted Insider (Flagged) | Predicted Normal (Ignored) |
| :--- | :---: | :---: |
| **Actual Insider** | **8** (TP) | 2 (FN) |
| **Actual Normal** | 17 (FP) | **173** (TN) |

## Detailed Rankings of Test Split Insiders

Here is where the 10 target test insiders ended up in the final ranked list:

| Rank | User ID | Threat Scenario | `score_v2` |
| --- | --- | --- | --- |
| 1 | U0028 | usb_exfil | 0.995704 |
| 2 | U0349 | sabotage | 0.987338 |
| 3 | U0430 | cloud_exfil | 0.938437 |
| 4 | U0891 | sabotage | 0.697513 |
| 5 | U0221 | flight_risk | 0.607156 |
| 6 | U0229 | usb_exfil | 0.590752 |
| 7 | U0719 | cloud_exfil | 0.405543 |
| 11 | U0282 | flight_risk | 0.270446 |
| 91 | U0143 | email_exfil | 0.004639 |
| 131 | U0604 | email_exfil | 0.001485 |