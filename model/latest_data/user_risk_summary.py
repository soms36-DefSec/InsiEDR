import os
import sys
import numpy as np
import pandas as pd

def generate_risk_report():
    print("=" * 80)
    print("              INSIEDR COHORT RISK SUMMARY GENERATOR")
    print("=" * 80)
    
    top_users_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\top_users.csv"
    dataset_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"
    output_report_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\cohort_risk_summary.csv"
    
    if not os.path.exists(top_users_csv) or not os.path.exists(dataset_csv):
        print("Error: Required data files do not exist. Please run the pipeline first.")
        sys.exit(1)
        
    print("Loading datasets...")
    top_users_df = pd.read_csv(top_users_csv)
    dataset_df = pd.read_csv(dataset_csv)
    
    # Sort user logs by date to ensure proper timeline progression
    dataset_df = dataset_df.sort_values(["user", "date"]).reset_index(drop=True)
    
    # Calculate daily fused rvfl_risk signal to identify peak threat days
    prob_cols = [
        "rf_email_exfil_prob", "rf_sabotage_prob", "rf_usb_exfil_prob", 
        "rf_flight_risk_prob", "rf_cloud_exfil_prob"
    ]
    dataset_df["max_scenario_prob"] = dataset_df[prob_cols].max(axis=1)
    dataset_df["rvfl_risk"] = 0.3 * dataset_df["overall_risk"] + 0.7 * dataset_df["max_scenario_prob"]
    
    # Static threshold from evaluation run (Top-10 test split boundary)
    THRESHOLD = 0.042845
    
    summary_rows = []
    print("Analyzing primary anomalous activities per user...")
    
    for idx, row in top_users_df.iterrows():
        user_id = row["user"]
        score_v2 = row["score_v2"]
        
        # Get logs for this specific user
        user_logs = dataset_df[dataset_df["user"] == user_id]
        if user_logs.empty:
            continue
            
        # Find the peak risk record (maximum daily rvfl_risk)
        peak_idx = user_logs["rvfl_risk"].idxmax()
        peak_row = user_logs.loc[peak_idx]
        
        # Find primary active domain trigger on that peak day
        domains = {
            "Logon Activity": peak_row["logon_risk"],
            "File System Activity": peak_row["file_risk"],
            "Device Connectivity": peak_row["device_risk"],
            "HTTP Browser Activity": peak_row["http_risk"]
        }
        primary_domain = max(domains, key=domains.get)
        primary_domain_score = domains[primary_domain]
        
        # Find maximum scenario probability on that day
        scenarios = {
            "email_exfil": peak_row["rf_email_exfil_prob"],
            "sabotage": peak_row["rf_sabotage_prob"],
            "usb_exfil": peak_row["rf_usb_exfil_prob"],
            "flight_risk": peak_row["rf_flight_risk_prob"],
            "cloud_exfil": peak_row["rf_cloud_exfil_prob"]
        }
        primary_scenario = max(scenarios, key=scenarios.get)
        primary_scenario_prob = scenarios[primary_scenario]
        
        # Build description of the activity they are risked on
        if primary_scenario_prob >= 0.50:
            activity_trigger = f"Peak anomaly on {str(peak_row['date'])[:10]} driven by {primary_domain} and suspicious {primary_scenario} indicators"
        else:
            activity_trigger = f"Peak anomaly on {str(peak_row['date'])[:10]} driven primarily by elevated {primary_domain}"
            
        # Mark as insider check if they exceed the Top-10 threshold
        verdict = "FLAGGED (INSIDER CHECK)" if score_v2 >= THRESHOLD else "CLEARED"
        
        summary_rows.append({
            "User ID": user_id,
            "Risk Score": score_v2,
            "Primary Risk Activity": activity_trigger,
            "Status": verdict
        })
        
    summary_df = pd.DataFrame(summary_rows)
    # Sort by risk scores high to low
    summary_df = summary_df.sort_values("Risk Score", ascending=False).reset_index(drop=True)
    
    # Save report to CSV
    summary_df.to_csv(output_report_csv, index=False)
    print(f"Saved cohort summary report to '{output_report_csv}' (Total: {len(summary_df)} users)\n")
    
    # Print ALL users to console
    print("ALL USERS IN COHORT (SORTED BY RISK SCORE):")
    print("-" * 120)
    print(f"{'User ID':<10} | {'Risk Score':<12} | {'Status':<25} | {'Primary Risk Activity'}")
    print("-" * 120)
    for idx, row in summary_df.iterrows():
        print(f"{row['User ID']:<10} | {row['Risk Score']:<12.6f} | {row['Status']:<25} | {row['Primary Risk Activity']}")
    print("-" * 120)

if __name__ == "__main__":
    generate_risk_report()
