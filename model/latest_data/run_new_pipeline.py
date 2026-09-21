import os
import sys
import json
import time
import traceback

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from latest_data_prep import preprocess_logs
from latest_feature_extractor import run_feature_extraction
from latest_anomaly_scoring import train_anomaly_models
from latest_xgb_classifier import train_xgb_classifier
from latest_rvfl_orchestrator import train_and_evaluate_rvfl
from latest_evaluator import evaluate_new_run

def main():
    print("=" * 80)
    # Align text center or use standard formatting
    print("                STARTING INSIEDR LATEST DATA PIPELINE RUN")
    print("=" * 80)
    
    start_time = time.time()
    
    # Define directories and paths
    latest_data_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(latest_data_dir, '..'))
    
    input_logs_dir = os.path.join(project_root, "INPUT_LOGS")
    raw_logs_dir = os.path.join(latest_data_dir, "raw_logs")
    models_dir = os.path.join(latest_data_dir, "models")
    
    features_csv = os.path.join(latest_data_dir, "if_enriched_features.csv")
    enriched_xgb_csv = os.path.join(latest_data_dir, "scenario_training_dataset_with_xgb.csv")
    anomaly_days_csv = os.path.join(latest_data_dir, "all_anomaly_days.csv")
    top_users_csv = os.path.join(latest_data_dir, "top_users.csv")
    comparison_report_path = os.path.join(latest_data_dir, "comparison_report.md")
    
    feature_columns_json = os.path.join(models_dir, "feature_columns_IF.json")
    insider_labels_csv = os.path.join(project_root, "OUTPUT_LABELS", "insider_labels.csv")
    test_users_json = os.path.join(latest_data_dir, "test_users.json")
    
    try:
        # ----------------------------------------------------------------------
        # STEP 1: Data Preprocessing
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 1: Data Preprocessing")
        print("-" * 50)
        preprocess_logs(input_logs_dir, raw_logs_dir, limit_users=None)
        
        # Verify raw files exist and have content
        for f in ["logon.csv", "device.csv", "file.csv", "http.csv"]:
            p = os.path.join(raw_logs_dir, f)
            if not os.path.exists(p) or os.path.getsize(p) == 0:
                raise ValueError(f"Step 1 failed: Raw file '{p}' was not created or is empty.")
        print("Step 1 successfully completed.")
        
        # ----------------------------------------------------------------------
        # STEP 2: Feature Extraction
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 2: Feature Extraction")
        print("-" * 50)
        df_features = run_feature_extraction(raw_logs_dir, features_csv, feature_columns_json)
        
        # Validate columns and shape
        if df_features.empty:
            raise ValueError("Step 2 failed: Feature DataFrame is empty.")
        print(f"Step 2 successfully completed. Shape: {df_features.shape}")
        
        # ----------------------------------------------------------------------
        # STEP 3: Isolation Forest training & scoring
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 3: Domain Isolation Forest & Threshold Recalibration")
        print("-" * 50)
        max_raw_overall_risk = train_anomaly_models(features_csv, features_csv, models_dir)
        print(f"Step 3 successfully completed. Observed maximum raw score divisor: {max_raw_overall_risk:.4f}")
        
        # ----------------------------------------------------------------------
        # STEP 4: XGBoost Scenario Classification
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 4: XGBoost Scenario Classifier")
        print("-" * 50)
        model_xgb, xgb_features, test_users = train_xgb_classifier(
            features_csv,
            insider_labels_csv,
            enriched_xgb_csv,
            models_dir
        )
        
        # Save test users to JSON
        with open(test_users_json, "w") as f:
            json.dump(test_users, f, indent=4)
        print(f"Step 4 successfully completed. Saved test user split of {len(test_users)} users.")
        
        # ----------------------------------------------------------------------
        # STEP 5: RedRVFL Drift Modeling
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 5: RedRVFL Sequence Drift Model")
        print("-" * 50)
        train_and_evaluate_rvfl(
            enriched_xgb_csv,
            test_users,
            anomaly_days_csv,
            top_users_csv,
            models_dir
        )
        print("Step 5 successfully completed.")
        
        # ----------------------------------------------------------------------
        # STEP 6: Evaluation & Comparison
        # ----------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("STEP 6: Recall Evaluation & Comparison")
        print("-" * 50)
        evaluate_new_run(top_users_csv, test_users, comparison_report_path)
        print("Step 6 successfully completed.")
        
        print("\n" + "=" * 80)
        print(f"PIPELINE RUN COMPLETE IN {time.time() - start_time:.2f} seconds!")
        print("=" * 80)
        
    except Exception as e:
        print("\n[X] PIPELINE RUN FAILED WITH ERROR:")
        print(str(e))
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
