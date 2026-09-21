import requests
import json
from pprint import pprint

BASE_URL = "http://127.0.0.1:8000"

def test_risk():
    print("--- Testing Risk Endpoint ---")
    payload = {
        "file_risk": 0.5,
        "device_risk": 0.1,
        "http_risk": 0.8,
        "logon_risk": 0.3
    }
    response = requests.post(f"{BASE_URL}/inference/risk", json=payload)
    pprint(response.json())
    print("\n")

def test_xgboost():
    print("--- Testing XGBoost Endpoint ---")
    # Sample subset of features, others will default to 0 in Pandas if they were missing, 
    # but the API requires all features to be present to prevent accidental miss-specification.
    
    # We must provide all 40 features
    features = [
        "logon_count", "logoff_count", "unique_pc_count", "daily_unique_pc_count",
        "after_hours_logon", "daily_after_hours_logon_ratio", "first_logon_time",
        "last_logoff_time", "weekend_logon", "daily_pc_access_entropy",
        "file_access_count", "daily_unique_filename_count", "daily_new_filename_count",
        "daily_file_access_entropy", "usb_connect_count", "usb_disconnect_count",
        "after_hours_usb_usage", "daily_device_connect_count", "daily_device_usage_flag",
        "first_usb_usage_time", "http_count", "daily_http_request_count",
        "unique_url_count", "suspicious_url_count", "file_sharing_site_visits",
        "job_search_site_visits", "http_after_hours", "daily_unique_domain_count",
        "daily_new_domain_count", "daily_domain_access_entropy", "daily_external_domain_ratio",
        "logon_risk", "file_risk", "device_risk", "http_risk", "overall_risk",
        "raw_overall_risk", "daily_risk_delta", "daily_risk_rolling_mean_7d",
        "daily_risk_rolling_std_7d"
    ]
    
    payload = {
        "features": {f: 0.5 for f in features}
    }
    
    response = requests.post(f"{BASE_URL}/inference/xgboost", json=payload)
    pprint(response.json())
    print("\n")

def test_behavioral():
    print("--- Testing Behavioral Endpoint ---")
    payload = {
        "rvfl_risk_sequence": [0.1, 0.2, 0.15, 0.3, 0.5, 0.6, 0.8]
    }
    response = requests.post(f"{BASE_URL}/inference/behavioral", json=payload)
    pprint(response.json())
    print("\n")

if __name__ == "__main__":
    try:
        test_risk()
        test_xgboost()
        test_behavioral()
    except Exception as e:
        print(f"Error connecting to server: {e}")
