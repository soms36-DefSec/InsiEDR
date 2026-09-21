import os
import sys
import psycopg2
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.simulate_agent import generate_30_days_dataset
from scripts.ingest_simulated_dataset import ingest_dataset

DB_DSN = 'postgresql://postgres:1973@localhost:5432/InsiEDR'
SERVER_URL = "http://127.0.0.1:5000"

def truncate_db():
    print("Truncating database tables...")
    conn = psycopg2.connect(DB_DSN)
    with conn.cursor() as cursor:
        cursor.execute("TRUNCATE raw_payloads, normalized_features, collector_results, risk_events, model_outputs CASCADE;")
    conn.commit()
    conn.close()

def re_evaluate_database():
    print("Re-evaluating all risk events using newly trained Machine Learning models...")
    from server.storage.postgres_storage import PostgresStorage
    from server.detectors.random_forest_detector import RandomForestDetector
    from server.detectors.isolation_forest_detector import IsolationForestDetector
    from server.risk.aggregator import RiskAggregator

    storage = PostgresStorage(DB_DSN)
    rf = RandomForestDetector()
    if_detector = IsolationForestDetector()
    aggregator = RiskAggregator(storage)
    
    # Reload models from disk
    print("Re-evaluating all risk events using newly trained Machine Learning models...")
    
    conn = psycopg2.connect(DB_DSN)
    with conn.cursor() as cursor:
        # 3. Evaluate existing risk events and update them
        cursor.execute("SELECT payload_id, agent_id, username, created_at FROM risk_events")
        events = cursor.fetchall()
        for event in events:
            payload_id, agent_id, username, created_at = event
            
            # Fetch features for payload
            cursor.execute("""
                SELECT feature_name, feature_value 
                FROM normalized_features 
                WHERE payload_id = %s
            """, (payload_id,))
            features = {f[0]: float(f[1]) for f in cursor.fetchall()}
            
            if not features:
                continue

            # Dummy baseline since we don't have rolling baselines easily accessible here
            class DummyBaseline:
                sample_count = 30
            
            rf_res = rf.detect(payload_id, agent_id, username, features, DummyBaseline())
            if_res = if_detector.detect(payload_id, agent_id, username, features, DummyBaseline())
            
            final_risk = aggregator.aggregate_detectors([rf_res, if_res])
            
            cursor.execute("""
                UPDATE risk_events
                SET risk_score = %s, risk_level = %s, summary = %s, correlated_signals_json = %s
                WHERE payload_id = %s
            """, (
                float(final_risk["risk_score"]),
                final_risk["risk_level"],
                final_risk["summary"],
                json.dumps(final_risk["correlated_signals_json"]),
                payload_id
            ))
            
    conn.commit()
    
    # Force fix timeline just in case ingestion dropped it
    with conn.cursor() as cursor:
        cursor.execute("UPDATE risk_events SET created_at = raw_payloads.payload_collected_at FROM raw_payloads WHERE raw_payloads.payload_id = risk_events.payload_id;")
    conn.commit()
    
    conn.close()
    print("Database re-evaluation complete!")

def print_severity_distribution():
    conn = psycopg2.connect(DB_DSN)
    with conn.cursor() as cursor:
        cursor.execute("SELECT risk_level, COUNT(*) FROM risk_events GROUP BY risk_level;")
        print("\n--- SEVERITY DISTRIBUTION ---")
        for row in cursor.fetchall():
            print(f"{row[0].upper()}: {row[1]}")
            
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM risk_events;")
        min_date, max_date = cursor.fetchall()[0]
        print(f"\n--- TIMELINE ---")
        print(f"Data Spans: {min_date} to {max_date}")
    conn.close()

if __name__ == "__main__":
    dataset_path = os.path.join(os.path.dirname(__file__), "simulated_dataset.json")
    
    # 1. Truncate
    truncate_db()
    
    # 2. Generate Data
    generate_30_days_dataset(dataset_path)
    
    # 3. Ingest Data
    ingest_dataset(dataset_path)
    
    # 4. Train Models
    print("Hitting /api/model/recalibrate to train ML models...")
    res = requests.post(f"{SERVER_URL}/api/model/recalibrate", json={"days": 30}).json()
    print(f"Training Results: {res}")
    
    # 5. Re-evaluate
    re_evaluate_database()
    
    # 6. Report
    print_severity_distribution()
