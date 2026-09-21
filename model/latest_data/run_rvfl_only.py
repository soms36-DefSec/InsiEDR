import os
import sys
import json

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from latest_rvfl_orchestrator import train_and_evaluate_rvfl
from latest_evaluator import evaluate_new_run

def main():
    test_users_json = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\test_users.json"
    enriched_xgb_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\scenario_training_dataset_with_xgb.csv"
    anomaly_days_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\all_anomaly_days.csv"
    top_users_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\top_users.csv"
    models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
    comparison_report_path = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\comparison_report.md"

    with open(test_users_json, "r") as f:
        test_users = json.load(f)

    print("Running Step 5: RedRVFL sequence drift retraining...")
    train_and_evaluate_rvfl(
        enriched_xgb_csv,
        test_users,
        anomaly_days_csv,
        top_users_csv,
        models_dir
    )

    print("Running Step 6: Recalibrating Evaluation metrics...")
    evaluate_new_run(top_users_csv, test_users, comparison_report_path)
    print("Done!")

if __name__ == "__main__":
    main()
