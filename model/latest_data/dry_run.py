import os
import sys
import shutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from latest_data_prep import preprocess_logs
from latest_feature_extractor import run_feature_extraction

def main():
    print("=" * 80)
    print("RUNNING DRY RUN FOR STEPS 1 & 2")
    print("=" * 80)
    
    input_logs_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\INPUT_LOGS"
    dry_run_logs_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\raw_logs_dry"
    dry_run_features_path = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\if_enriched_features_dry.csv"
    feature_columns_json = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\models\feature_columns_IF.json"
    
    # Slice of 20 users U0001 to U0020
    test_users = [f"U{i:04d}" for i in range(1, 21)]
    
    try:
        # Step 1: Preprocess logs for slice of users
        preprocess_logs(input_logs_dir, dry_run_logs_dir, limit_users=test_users)
        
        # Step 2: Extract features
        df = run_feature_extraction(dry_run_logs_dir, dry_run_features_path, feature_columns_json)
        
        print("\n" + "=" * 80)
        print("DRY RUN SUCCESSFUL!")
        print("=" * 80)
        print(f"Feature DataFrame Shape: {df.shape}")
        print("\nSample Columns:")
        print(list(df.columns[:10]))
        print("\nSample Rows (First 5):")
        print(df.head(5).to_string(index=False))
        
    except Exception as e:
        print(f"\n❌ Error during dry run: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up dry run files
        if os.path.exists(dry_run_logs_dir):
            shutil.rmtree(dry_run_logs_dir)
            print(f"\nCleaned up dry run raw logs directory '{dry_run_logs_dir}'.")

if __name__ == "__main__":
    main()
