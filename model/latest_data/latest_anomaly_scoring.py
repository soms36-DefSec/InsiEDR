import os
import sys
import joblib
import numpy as np
import pandas as pd

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.server.anomaly.domain_models import DomainIsolationForest
from src.server.anomaly.rolling_features import add_risk_trend_features, build_daily_risk_dataframe
from src.server.features.feature_schema import (
    LOGON_FEATURES,
    FILE_FEATURES,
    DEVICE_FEATURES,
    HTTP_FEATURES
)

def existing_columns(df, col_list):
    return [c for c in col_list if c in df.columns]

def train_anomaly_models(features_csv_path, output_features_path, models_dir):
    """
    Loads features, trains domain Isolation Forest models, computes risk scores,
    recalibrates overall_risk relative to the maximum observed raw score,
    adds rolling trend features, and saves the outputs.
    """
    print(f"Loading features from '{features_csv_path}'...")
    feature_df = pd.read_csv(features_csv_path)
    feature_df["date"] = pd.to_datetime(feature_df["date"])
    
    # Slice features by domain
    logon_features = existing_columns(feature_df, LOGON_FEATURES)
    file_features = existing_columns(feature_df, FILE_FEATURES)
    device_features = existing_columns(feature_df, DEVICE_FEATURES)
    http_features = existing_columns(feature_df, HTTP_FEATURES)
    
    logon_X = feature_df[logon_features].fillna(0).values
    file_X = feature_df[file_features].fillna(0).values
    device_X = feature_df[device_features].fillna(0).values
    http_X = feature_df[http_features].fillna(0).values
    
    print("Training Domain Isolation Forests (contamination=0.05)...")
    domain_if = DomainIsolationForest(contamination=0.05)
    domain_if.fit(logon_X, file_X, device_X, http_X)
    
    # Save the trained model
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, "domain_isolation_forest.pkl")
    joblib.dump(domain_if, model_path)
    print(f"Saved domain Isolation Forest model to '{model_path}'")
    
    # Score features
    print("Scoring logon, file, device, http domains...")
    scores = domain_if.score(logon_X, file_X, device_X, http_X)
    
    # Build daily risk dataframe
    risk_df = build_daily_risk_dataframe(
        feature_df,
        scores["logon"],
        scores["file"],
        scores["device"],
        scores["http"]
    )
    
    # Compute raw overall risk (mean of raw domain scores)
    raw_overall_risk = risk_df["overall_risk"].copy()
    max_raw_overall_risk = raw_overall_risk.max()
    print(f"Raw Overall Risk - Min: {raw_overall_risk.min():.4f}, Max: {max_raw_overall_risk:.4f}, Mean: {raw_overall_risk.mean():.4f}")
    
    # Rescale overall risk so that max observed raw score = 1.0
    if max_raw_overall_risk > 0:
        rescaled_overall_risk = np.minimum(raw_overall_risk / max_raw_overall_risk, 1.0)
    else:
        rescaled_overall_risk = raw_overall_risk
        
    print(f"Rescaled Overall Risk (scaled by 1/{max_raw_overall_risk:.4f}) - Min: {rescaled_overall_risk.min():.4f}, Max: {rescaled_overall_risk.max():.4f}, Mean: {rescaled_overall_risk.mean():.4f}")
    
    # Save both raw and rescaled distributions
    risk_df["overall_risk"] = rescaled_overall_risk
    risk_df["raw_overall_risk"] = raw_overall_risk
    
    # Merge with original features
    # Drop existing risk/overall columns if any to prevent duplicates before merge
    drop_cols = [c for c in risk_df.columns if c in feature_df.columns and c not in ["user", "date"]]
    feature_df = feature_df.drop(columns=drop_cols)
    
    merged_df = feature_df.merge(risk_df, on=["user", "date"])
    
    # Add rolling risk trend features
    merged_df = add_risk_trend_features(merged_df)
    
    # Save enriched features
    merged_df.to_csv(output_features_path, index=False)
    print(f"Saved enriched features with anomaly scores to '{output_features_path}' (Shape: {merged_df.shape})")
    
    # Print threshold stats
    high_count = (merged_df["overall_risk"] >= 0.80).sum()
    med_count = ((merged_df["overall_risk"] >= 0.50) & (merged_df["overall_risk"] < 0.80)).sum()
    low_count = (merged_df["overall_risk"] < 0.50).sum()
    total = len(merged_df)
    print("\nRescaled Overall Risk distribution:")
    print(f"  HIGH (>= 0.80): {high_count} ({high_count/total*100:.2f}%)")
    print(f"  MEDIUM (>= 0.50): {med_count} ({med_count/total*100:.2f}%)")
    print(f"  LOW (< 0.50): {low_count} ({low_count/total*100:.2f}%)")
    
    return max_raw_overall_risk

if __name__ == "__main__":
    features_csv = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\if_enriched_features.csv"
    output_features = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\if_enriched_features.csv"
    models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"
    train_anomaly_models(features_csv, output_features, models_dir)
