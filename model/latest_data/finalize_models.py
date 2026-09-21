import os
import shutil
import json

models_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\models"

# 1. Rename rvfl_ridge_models.pkl to ridge_models.pkl
src_ridge = os.path.join(models_dir, "rvfl_ridge_models.pkl")
dst_ridge = os.path.join(models_dir, "ridge_models.pkl")
if os.path.exists(src_ridge):
    shutil.copy(src_ridge, dst_ridge)
    print(f"Copied {src_ridge} to {dst_ridge}")

# 2. Create rvfl_metadata.json
metadata = {
    "input_features": 1,
    "hidden_size": 128,
    "num_layers": 5,
    "sequence_length": 7
}
with open(os.path.join(models_dir, "rvfl_metadata.json"), "w") as f:
    json.dump(metadata, f, indent=4)
print("Created rvfl_metadata.json")

# 3. Copy feature_columns_IF.json from models/
shutil.copy(
    r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\models\feature_columns_IF.json",
    os.path.join(models_dir, "feature_columns_IF.json")
)
print("Copied feature_columns_IF.json")
