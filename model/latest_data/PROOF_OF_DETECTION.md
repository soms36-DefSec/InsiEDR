# InsiEDR Pipeline Proof of Detection Report

## 1. Purpose
This document demonstrates that the trained InsiEDR pipeline correctly separates insider threat users from normal users on held-out test data that it was never exposed to during training. By evaluating the model against unseen users from the test split, this report provides empirical evidence of the system's detection capability.

---

## 2. Method
For each user evaluated, the complete three-tier pipeline is executed:
1. **Tier 1 (Isolation Forest)**: Computes daily baseline anomaly risk scores across Logon, File, Device, and HTTP domains, rescaled relative to the cohort raw maximum of `0.7300`.
2. **Tier 2 (XGBoost)**: Predicts multi-class scenario probabilities for each daily record.
3. **Tier 3 (RedRVFL)**: Fuses the Tier 1 and Tier 2 risk signals and fits sequential predictions over a 7-day sliding window to identify temporal behavior drift.

The final user threat score is calculated using `score_v2` ($max\_error \times mean\_error \times \sqrt{anomaly\_days}$). The user is then ranked against all 200 users in the held-out test split. If the final risk score meets or exceeds the Top-10 queue threshold of **`0.042845`**, the user is flagged for manual review; otherwise, they are cleared.

---

## 3. Proof Cases
The pipeline was evaluated against a representative sample of 10 users from the test split:
* **5 Insider Threat Users**: Exactly one target insider selected from each of the 5 threat scenario classes.
* **5 Normal Users**: Selected programmatically using a fixed sorting index from the pool of normal test split users (`U0002`, `U0005`, `U0015`, `U0016`, `U0022`).

| User ID | True Label | Final Risk Score | Rank (of 200) | Model Verdict | Correct? |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **U0604** | Insider - email_exfil | 0.209343 | #1 | FLAGGED FOR REVIEW | YES |
| **U0430** | Insider - cloud_exfil | 0.206403 | #2 | FLAGGED FOR REVIEW | YES |
| **U0349** | Insider - sabotage | 0.121768 | #5 | FLAGGED FOR REVIEW | YES |
| **U0028** | Insider - usb_exfil | 0.111130 | #6 | FLAGGED FOR REVIEW | YES |
| **U0221** | Insider - flight_risk | 0.103582 | #8 | FLAGGED FOR REVIEW | YES |
| **U0016** | Normal | 0.000051 | #37 | NOT FLAGGED | YES |
| **U0015** | Normal | 0.000039 | #51 | NOT FLAGGED | YES |
| **U0022** | Normal | 0.000034 | #68 | NOT FLAGGED | YES |
| **U0005** | Normal | 0.000020 | #94 | NOT FLAGGED | YES |
| **U0002** | Normal | 0.000001 | #180 | NOT FLAGGED | YES |

---

## 4. Aggregate Result
From this 10-user verification sample, the model achieved **10 out of 10 correct verdicts**. 

All 5 insider threats representing different exfiltration and sabotage attack vectors were successfully flagged in the top ranks of the review queue, and all 5 normal users were correctly cleared with risk scores near zero, placing them safely below the review threshold.

---

## 5. Detailed Diagnostic Traces

### Case A: Clear Insider Detection (User: U0430, cloud_exfil scenario)

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
| 2024-01-03 | L:0.4858 F:0.5015 D:0.4607 H:0.3858 | 0.6280 | MEDIUM |
| 2024-01-04 | L:0.3709 F:0.5458 D:0.4607 H:0.3978 | 0.6079 | MEDIUM |
| 2024-01-05 | L:0.4043 F:0.5270 D:0.4607 H:0.3732 | 0.6045 | MEDIUM |
| ...        | ...                                                 | ...    | ...      |
| 2024-03-27 | L:0.3964 F:0.7461 D:0.4607 H:0.7025 | 0.7896 | MEDIUM |
| 2024-03-28 | L:0.3856 F:0.7651 D:0.4607 H:0.7585 | 0.8116 | HIGH |
| 2024-03-29 | L:0.4576 F:0.7839 D:0.4607 H:0.7767 | 0.8489 | HIGH |
| 2024-03-30 | L:0.6398 F:0.6304 D:0.4607 H:0.7859 | 0.8619 | HIGH |
| 2024-03-31 | L:0.7166 F:0.7270 D:0.4607 H:0.7761 | 0.9180 | HIGH |

STAGE 2: THREAT TYPE CLASSIFICATION (XGBoost)
Predicts which of 6 categories each day's behavior resembles.

| Date       | Predicted Class   | Confidence |
| :---       | :---              | :---:      |
| 2024-01-01 | normal          | 100.00% |
| 2024-01-02 | normal          | 100.00% |
| 2024-01-03 | normal          | 100.00% |
| 2024-01-04 | normal          | 100.00% |
| 2024-01-05 | normal          | 100.00% |
| ...        | ...             | ...    |
| 2024-03-27 | cloud_exfil     | 100.00% |
| 2024-03-28 | cloud_exfil     | 100.00% |
| 2024-03-29 | cloud_exfil     | 100.00% |
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

HOW TO READ THIS

A single HIGH day alone does not mean insider — Stage 3's pattern-over-time is the real signal.
This model was trained using only each insider's final 10 active days as positive
examples; performance on subtle/early-stage behavior has not been separately validated.
================================================================================
```

### Case B: Clear Normal User Clearance (User: U0002, normal scenario)

```text
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
| 2024-01-02 | L:0.4200 F:0.5309 D:0.4607 H:0.3727 | 0.6110 | MEDIUM |
| 2024-01-03 | L:0.4001 F:0.5796 D:0.4607 H:0.3831 | 0.6245 | MEDIUM |
| 2024-01-04 | L:0.4151 F:0.4779 D:0.4607 H:0.4073 | 0.6031 | MEDIUM |
| 2024-01-05 | L:0.3788 F:0.4836 D:0.4607 H:0.3639 | 0.5778 | MEDIUM |
| ...        | ...                                                 | ...    | ...      |
| 2024-03-25 | L:0.3707 F:0.4365 D:0.4607 H:0.3921 | 0.5685 | MEDIUM |
| 2024-03-26 | L:0.3877 F:0.4327 D:0.4607 H:0.4049 | 0.5774 | MEDIUM |
| 2024-03-27 | L:0.3818 F:0.4587 D:0.4607 H:0.3735 | 0.5735 | MEDIUM |
| 2024-03-28 | L:0.5722 F:0.4725 D:0.4607 H:0.3600 | 0.6388 | MEDIUM |
| 2024-03-29 | L:0.3708 F:0.4666 D:0.4607 H:0.3793 | 0.5744 | MEDIUM |

STAGE 2: THREAT TYPE CLASSIFICATION (XGBoost)
Predicts which of 6 categories each day's behavior resembles.

| Date       | Predicted Class   | Confidence |
| :---       | :---              | :---:      |
| 2024-01-01 | normal          | 99.99% |
| 2024-01-02 | normal          | 100.00% |
| 2024-01-03 | normal          | 100.00% |
| 2024-01-04 | normal          | 100.00% |
| 2024-01-05 | normal          | 100.00% |
| ...        | ...             | ...    |
| 2024-03-25 | normal          | 100.00% |
| 2024-03-26 | normal          | 100.00% |
| 2024-03-27 | normal          | 100.00% |
| 2024-03-28 | normal          | 100.00% |
| 2024-03-29 | normal          | 100.00% |

STAGE 3: BEHAVIORAL DRIFT OVER TIME (RedRVFL)
Looks at the pattern across days, not just single days.

Sequence length: 66 days | Drift error (MSE): 0.000158 | Final risk score: 0.000001

FINAL VERDICT

This user ranks #180 out of 200 test users. Top-10 threshold: 0.042845

VERDICT: NOT FLAGGED
Ground truth (verification only, not used in scoring): Normal
Model verdict matches ground truth: YES

HOW TO READ THIS

A single HIGH day alone does not mean insider — Stage 3's pattern-over-time is the real signal.
This model was trained using only each insider's final 10 active days as positive
examples; performance on subtle/early-stage behavior has not been separately validated.
================================================================================
```

---

## 6. Caveats
* This document reviews a 10-user subset to demonstrate functional correctness and behavior under different threat scenarios. It does not replace a statistically exhaustive validation.
* For the full model evaluation on the complete 200-user held-out test split, refer to the tables and metrics detailed in [PROJECT_REPORT.md](file:///c:/Users/Guruchandar/Downloads/insiEDR%20project/InsiEDR/latest_data/PROJECT_REPORT.md).
