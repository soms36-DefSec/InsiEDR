import os
import sys
import json
import pandas as pd
import numpy as np

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def evaluate_new_run(top_users_csv_path, test_users_list, comparison_report_path):
    """
    Step 6: Evaluates detection recall, precision, and F1-score on the held-out
    test users at Top-5, Top-10, and Top-25, and creates a side-by-side comparison
    with the old CERT r4.2 results.
    """
    print(f"Evaluating user rankings from '{top_users_csv_path}' on test users...")
    df = pd.read_csv(top_users_csv_path)
    
    # Filter to only the 200 held-out test users
    test_users_list = list(test_users_list)
    test_ranked_df = df[df["user"].isin(test_users_list)].copy()
    test_ranked_df = test_ranked_df.sort_values("score_v2", ascending=False).reset_index(drop=True)
    
    total_test_users = len(test_ranked_df)
    total_insiders = int(test_ranked_df["is_insider"].sum())
    
    print(f"Total test users: {total_test_users}")
    print(f"Total insiders in test split: {total_insiders}")
    
    # Evaluate at Top-N
    results = {}
    for n in [5, 10, 25]:
        top_n = test_ranked_df.head(n)
        detected_insiders = int(top_n["is_insider"].sum())
        
        recall = detected_insiders / total_insiders if total_insiders > 0 else 0
        precision = detected_insiders / n
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
        
        tp = detected_insiders
        fp = n - detected_insiders
        fn = total_insiders - detected_insiders
        tn = total_test_users - total_insiders - n + detected_insiders
        
        results[n] = {
            "detected": detected_insiders,
            "total": total_insiders,
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn
        }
        
    # Hardcoded old CERT r4.2 stats (score_v2) from walkthrough.md
    # Total insiders in old CERT test set = 9
    cert_stats = {
        5: {"recall": 0.4444, "precision": 0.8000, "f1": 0.5714, "detected": 4, "total": 9},
        10: {"recall": 1.0000, "precision": 0.9000, "f1": 0.9474, "detected": 9, "total": 9},
        25: {"recall": 1.0000, "precision": 0.3600, "f1": 0.5294, "detected": 9, "total": 9}
    }
    
    report_lines = []
    report_lines.append("# InsiEDR Model Pipeline Performance Comparison")
    report_lines.append("")
    report_lines.append("## Executive Summary")
    report_lines.append("This report compares the performance of the InsiEDR pipeline using the `score_v2` ranking metric ($max\\_error \\times mean\\_error \\times \\sqrt{anomaly\\_days}$) on the original CERT r4.2 dataset vs. the newly adapted dataset.")
    report_lines.append("")
    report_lines.append("> [!WARNING]")
    report_lines.append("> **Important Caveat**: The Isolation Forest anomaly scoring thresholds and the label density differ significantly between these two datasets. In particular, the new dataset contains 5% target insider users in the test set (10/200), whereas the old CERT r4.2 dataset contained ~4.5% (9/198). Furthermore, threat day definitions differ. Therefore, these recall, precision, and F1-score comparisons are not strictly apples-to-apples, but rather serve as a baseline transfer sanity-check.")
    report_lines.append("")
    report_lines.append("## Side-by-Side Metrics Table")
    report_lines.append("")
    report_lines.append("| Dataset / Metric | Top-5 Review Queue | Top-10 Review Queue | Top-25 Review Queue |")
    report_lines.append("| :--- | :---: | :---: | :---: |")
    
    # Recall line
    report_lines.append(f"| **CERT r4.2 (Old) Recall** | {cert_stats[5]['recall']:.4f} ({cert_stats[5]['detected']}/{cert_stats[5]['total']}) | **{cert_stats[10]['recall']:.4f}** ({cert_stats[10]['detected']}/{cert_stats[10]['total']}) | {cert_stats[25]['recall']:.4f} ({cert_stats[25]['detected']}/{cert_stats[25]['total']}) |")
    report_lines.append(f"| **New Dataset Recall** | {results[5]['recall']:.4f} ({results[5]['detected']}/{results[5]['total']}) | **{results[10]['recall']:.4f}** ({results[10]['detected']}/{results[10]['total']}) | {results[25]['recall']:.4f} ({results[25]['detected']}/{results[25]['total']}) |")
    report_lines.append("| | | | |")
    
    # Precision line
    report_lines.append(f"| **CERT r4.2 (Old) Precision** | {cert_stats[5]['precision']:.4f} | **{cert_stats[10]['precision']:.4f}** | {cert_stats[25]['precision']:.4f} |")
    report_lines.append(f"| **New Dataset Precision** | {results[5]['precision']:.4f} | **{results[10]['precision']:.4f}** | {results[25]['precision']:.4f} |")
    report_lines.append("| | | | |")
    
    # F1 line
    report_lines.append(f"| **CERT r4.2 (Old) F1-Score** | {cert_stats[5]['f1']:.4f} | **{cert_stats[10]['f1']:.4f}** | {cert_stats[25]['f1']:.4f} |")
    report_lines.append(f"| **New Dataset F1-Score** | {results[5]['f1']:.4f} | **{results[10]['f1']:.4f}** | {results[25]['f1']:.4f} |")
    report_lines.append("")
    
    report_lines.append("## Overall Binary Confusion Matrices (New Dataset)")
    report_lines.append("")
    for n in [5, 10, 25]:
        res = results[n]
        report_lines.append(f"### {n}-User Review Queue (Top-{n})")
        report_lines.append(f"* **True Positives (TP)**: {res['tp']} (Insiders correctly flagged)")
        report_lines.append(f"* **False Positives (FP)**: {res['fp']} (Normal users incorrectly flagged)")
        report_lines.append(f"* **False Negatives (FN)**: {res['fn']} (Insiders missed)")
        report_lines.append(f"* **True Negatives (TN)**: {res['tn']} (Normal users correctly ignored)")
        report_lines.append("")
        report_lines.append("| | Predicted Insider (Flagged) | Predicted Normal (Ignored) |")
        report_lines.append("| :--- | :---: | :---: |")
        report_lines.append(f"| **Actual Insider** | **{res['tp']}** (TP) | {res['fn']} (FN) |")
        report_lines.append(f"| **Actual Normal** | {res['fp']} (FP) | **{res['tn']}** (TN) |")
        report_lines.append("")
        
    report_lines.append("## Detailed Rankings of Test Split Insiders")
    report_lines.append("")
    report_lines.append("Here is where the 10 target test insiders ended up in the final ranked list:")
    report_lines.append("")
    report_lines.append("| Rank | User ID | Threat Scenario | `score_v2` |")
    report_lines.append("| --- | --- | --- | --- |")
    
    # Find positions of all insiders in test_ranked_df
    for rank, row in test_ranked_df.iterrows():
        if row["is_insider"] == 1:
            report_lines.append(f"| {rank + 1} | {row['user']} | {row['threat_scenario']} | {row['score_v2']:.6f} |")
            
    report_text = "\n".join(report_lines)
    
    os.makedirs(os.path.dirname(comparison_report_path), exist_ok=True)
    with open(comparison_report_path, "w") as f:
        f.write(report_text)
        
    print("\n" + "=" * 80)
    print("EVALUATION REPORT")
    print("=" * 80)
    print(report_text)
    print("=" * 80)
    print(f"Saved evaluation report to '{comparison_report_path}'")
    
    return results

if __name__ == "__main__":
    # Dynamically resolve relative paths for portability
    base_dir = os.path.dirname(os.path.abspath(__file__))
    top_users_csv = os.path.join(base_dir, "top_users.csv")
    test_users_json = os.path.join(base_dir, "test_users.json")
    report_path = os.path.join(base_dir, "comparison_report.md")
    
    if os.path.exists(test_users_json):
        with open(test_users_json, "r") as f:
            test_users = json.load(f)
    else:
        test_users = [f"U{i:04d}" for i in range(1, 201)]
        
    evaluate_new_run(top_users_csv, test_users, report_path)
