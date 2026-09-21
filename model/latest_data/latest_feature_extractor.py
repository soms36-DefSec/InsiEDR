import os
import json
import pandas as pd
import sys

# Ensure project root is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.server.features.cert_behavioural import CERTBehavioralExtractor
from src.server.features.extractors.http import extract_http_features

def run_feature_extraction(raw_logs_dir, output_features_path, feature_columns_json_path):
    """
    Runs feature extraction using the original extractors on raw_logs_dir,
    merges features, filters by allowed columns, and saves to output_features_path.
    """
    print(f"Extracting features from raw logs at '{raw_logs_dir}'...")
    
    # 1. Logon, File, Device features
    extractor = CERTBehavioralExtractor(raw_logs_dir)
    features_df = extractor.extract()
    
    print(f"Features extracted from Logon, File, Device (Shape: {features_df.shape})")
    
    # 2. HTTP features (Note: CERTBehavioralExtractor.extract() already calls extract_http_features internally!)
    # Wait, let's verify if cert_behavioural.py calls extract_http_features internally:
    # Yes, we saw:
    #   http_features = extract_http_features(self.dataset_path)
    #   feature_tables = [device_features, file_features, http_features, edr_features]
    # And it merges them together!
    # So CERTBehavioralExtractor.extract() already extracts all logon, device, file, and http features!
    # Let's verify that CERTBehavioralExtractor.extract() returns a merged dataframe with all features.
    # Yes, it merges logon_features, device_features, file_features, http_features, and edr_features.
    
    # 3. Load allowed feature columns
    if not os.path.exists(feature_columns_json_path):
        raise FileNotFoundError(f"Feature columns schema file '{feature_columns_json_path}' not found!")
        
    with open(feature_columns_json_path, 'r') as f:
        allowed_features = json.load(f)
        
    print(f"Loaded feature schema with {len(allowed_features)} allowed features.")
    
    # Ensure 'user' and 'date' are preserved
    keep_cols = ['user', 'date'] + [col for col in allowed_features if col in features_df.columns]
    
    # Check for missing expected columns and print warning
    missing_cols = [col for col in allowed_features if col not in features_df.columns]
    if missing_cols:
        print(f"Warning: {len(missing_cols)} expected features not found in extraction: {missing_cols}")
        
    # Filter the features
    filtered_df = features_df[keep_cols].copy()
    
    # Save to CSV
    os.makedirs(os.path.dirname(output_features_path), exist_ok=True)
    filtered_df.to_csv(output_features_path, index=False)
    print(f"Saved filtered features to '{output_features_path}' (Shape: {filtered_df.shape})")
    return filtered_df

if __name__ == "__main__":
    raw_logs_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\raw_logs"
    output_features_path = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\if_enriched_features.csv"
    feature_columns_json = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\models\feature_columns_IF.json"
    run_feature_extraction(raw_logs_dir, output_features_path, feature_columns_json)
