import os
import pandas as pd
import numpy as np

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
latest_data_dir = os.path.join(project_root, "latest_data")
features_csv_path = os.path.join(latest_data_dir, "if_enriched_features.csv")
output_csv_path = os.path.join(os.path.dirname(__file__), "outputs", "domain_and_overall_risks.csv")

print(f"Loading {features_csv_path}...")
df = pd.read_csv(features_csv_path)

# Calculate raw overall score using the formula
print("Calculating overall score using the new formula...")
df["calculated_raw_score"] = (
    0.17367798 * df["file_risk"] +
    0.61447200 * df["http_risk"] +
    0.18687011 * df["logon_risk"] + 
    0.02497992 * df["device_risk"]
)

# Optional: Scale it between 0 and 1
max_raw = df["calculated_raw_score"].max()
df["overall_risk_score"] = np.minimum(df["calculated_raw_score"] / max_raw, 1.0)

# Select only the specific columns requested
columns_to_keep = [
    "user", 
    "date", 
    "file_risk", 
    "http_risk", 
    "logon_risk", 
    "device_risk", 
    "calculated_raw_score",
    "overall_risk_score"
]

final_df = df[columns_to_keep]

print(f"Saving extracted columns to {output_csv_path}...")
final_df.to_csv(output_csv_path, index=False)
print("Done!")
