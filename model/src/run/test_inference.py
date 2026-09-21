import json
import warnings
import pandas as pd
import numpy as np
# CHANGED: Import predict_user_risk which is now implemented in inference.py
from src.server.inference import predict_user_risk



def test_inference_pipeline():
    print("Loading test features from CSV...")
    df = pd.read_csv("if_enriched_features.csv")
    
    # CHANGED: Load sequence length from metadata to determine minimum history length dynamically
    with open("models/rvfl_metadata.json", "r") as f:
        rvfl_meta = json.load(f)
    seq_len = rvfl_meta["sequence_length"]
    required_len = seq_len + 1

    # Find a user with at least required_len days of data
    user_counts = df["user"].value_counts()
    eligible_users = user_counts[user_counts >= required_len].index
    if len(eligible_users) == 0:
        raise ValueError(f"No user found with at least {required_len} days of data in CSV.")
        
    test_user = eligible_users[0]
    print(f"Selected test user: {test_user} (has {user_counts[test_user]} days)")
    
    user_df = df[df["user"] == test_user].sort_values("date").head(required_len)
    
    # CHANGED: Load correct features list models/feature_columns_IF.json instead of models/feature_columns.json (which was overwritten by RVFL features)
    with open("models/feature_columns_IF.json", "r") as f:
        feature_columns = json.load(f)
        
    # Build payload
    daily_sequence = []
    for _, row in user_df.iterrows():
        features_dict = {}
        for col in feature_columns:
            features_dict[col] = float(row[col]) if not pd.isna(row[col]) else 0.0
            
        daily_sequence.append({
            "date": str(row["date"]),
            "features": features_dict
        })
        
    payload = {
        "payload_id": "test-uuid-0001",
        "username": test_user,
        "hostname": "PC-TEST",
        "daily_sequence": daily_sequence
    }
    
    print("\n--- TEST 1: Standard Prediction (16 days) ---")
    # CHANGED: Call predict_user_risk which is now implemented in inference.py
    result = predict_user_risk(payload)
    print("Risk Assessment Result:")
    print(json.dumps(result, indent=2))
    
    # Assertions
    assert "risk_score" in result
    assert "risk_level" in result
    assert "detectors" in result
    assert "recommended_action" in result
    assert result["risk_level"] in ["HIGH", "MEDIUM", "LOW"]
    assert 0.0 <= result["risk_score"] <= 100.0
    print("TEST 1 PASSED!")

    print("\n--- TEST 2: Sequence Length Too Short Validation ---")
    short_payload = payload.copy()
    # CHANGED: Slice sequence to required_len - 1 to dynamically trigger the sequence length error
    short_payload["daily_sequence"] = daily_sequence[:required_len - 1]
    try:
        # CHANGED: Call predict_user_risk which is now implemented in inference.py
        predict_user_risk(short_payload)
        print("TEST 2 FAILED: Expected ValueError for short sequence, but no exception was raised.")
        assert False
    except ValueError as e:
        print(f"TEST 2 PASSED: Successfully caught ValueError: {e}")

    print("\n--- TEST 3: Missing Feature Validation ---")
    missing_payload = json.loads(json.dumps(payload)) # deep copy
    # Remove a required feature from the first day
    first_feature = feature_columns[0]
    del missing_payload["daily_sequence"][0]["features"][first_feature]
    try:
        # CHANGED: Call predict_user_risk which is now implemented in inference.py
        predict_user_risk(missing_payload)
        print("TEST 3 FAILED: Expected ValueError for missing feature, but no exception was raised.")
        assert False
    except ValueError as e:
        print(f"TEST 3 PASSED: Successfully caught ValueError: {e}")

    print("\n--- TEST 4: Unexpected Feature Warning ---")
    unexpected_payload = json.loads(json.dumps(payload)) # deep copy
    # Add an unexpected feature to the first day
    unexpected_payload["daily_sequence"][0]["features"]["unexpected_behavior_score"] = 99.9
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # CHANGED: Call predict_user_risk which is now implemented in inference.py
        predict_user_risk(unexpected_payload)
        warning_messages = [str(warn.message) for warn in w if issubclass(warn.category, UserWarning)]
        if warning_messages:
            print(f"TEST 4 PASSED: Caught expected UserWarning: {warning_messages[0]}")
        else:
            print("TEST 4 FAILED: Expected UserWarning for unexpected feature, but none was raised.")
            assert False

if __name__ == "__main__":
    test_inference_pipeline()
