import os
import sys
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.app import create_app

def tune_zscore_multiplier():
    app = create_app()
    
    with app.app_context():
        storage = app.extensions.get("insiedr_storage")
        if not storage:
            print("[-] Error: Failed to connect to PostgreSQL. Is INSIEDR_DATABASE_DSN set?")
            return

        print("[*] Connecting to PostgreSQL to extract historical variance...")
        
        # We will calculate the absolute Z-Score for every numerical feature collected
        # by comparing it to the baseline active at the time it was collected.
        query = """
            WITH latest_baselines AS (
                SELECT username, metadata_json
                FROM (
                    SELECT username, metadata_json,
                           ROW_NUMBER() OVER(PARTITION BY username ORDER BY window_end DESC) as rnk
                    FROM baseline_snapshots
                    WHERE feature_name = '__aggregate__' AND sample_count > 5
                ) sub
                WHERE rnk = 1
            )
            SELECT nf.feature_value_numeric AS val, nf.feature_name, lb.metadata_json 
            FROM normalized_features nf
            JOIN latest_baselines lb 
              ON nf.username = lb.username 
            WHERE nf.feature_value_numeric IS NOT NULL;
        """

        try:
            with storage.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
        except Exception as e:
            print(f"[-] Database query failed: {e}")
            return

        if not rows:
            print("[-] No valid historical data found. Have you run the simulation script yet?")
            print("    Run: python scripts/simulate_telemetry.py first to generate the variance.")
            return

        print(f"[+] Extracted {len(rows)} valid feature data points across all agents.")

        # Calculate exact Z-scores for every data point
        z_scores = []
        for val, feature_name, metadata in rows:
            feature_means = metadata.get("feature_means", {})
            feature_stds = metadata.get("feature_stds", {})
            
            mean = feature_means.get(feature_name, 0.0)
            std = feature_stds.get(feature_name, 1.0)
            
            std_safe = max(std, 1.0) # ZScoreDetector natively enforces a minimum std of 1.0
            z = abs((val - mean) / std_safe)
            z_scores.append(z)

        # We want to mathematically find the cutoff where 99.5% of normal variance is ignored,
        # reserving anomalies for the top 0.5% of extreme spikes.
        target_percentile = 99.5
        p995_zscore = np.percentile(z_scores, target_percentile)
        
        # The detector uses: threshold = 3.0 * sensitivity_multiplier
        # Therefore: multiplier = target_z / 3.0
        optimal_multiplier = p995_zscore / 3.0

        print("\n" + "="*50)
        print(" Z-SCORE CALIBRATION RESULTS ")
        print("="*50)
        print(f"Total Samples Analyzed : {len(z_scores)}")
        print(f"Highest Z-Score Seen   : {max(z_scores):.2f}")
        print(f"Target {target_percentile}th Z-Score : {p995_zscore:.2f}")
        print("-" * 50)
        print(f"[*] RECOMMENDED SENSITIVITY MULTIPLIER: {optimal_multiplier:.3f}")
        print("-" * 50)
        
        print("\nTo apply this to the production detector, update server/config.py or pass it explicitly:")
        print(f"    ZScoreDetector(sensitivity_multiplier={optimal_multiplier:.3f})")

if __name__ == "__main__":
    try:
        import numpy
    except ImportError:
        print("[-] Missing required dependency 'numpy'. Please install it:")
        print("    pip install numpy")
        sys.exit(1)
        
    tune_zscore_multiplier()
