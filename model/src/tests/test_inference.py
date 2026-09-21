from src.server.features.feature_schema import (
    LOGON_FEATURES,
    FILE_FEATURES,
    DEVICE_FEATURES,
    HTTP_FEATURES
)
from src.server.inference import predict_current_risk
features = {}

for feature in (
    LOGON_FEATURES
    + FILE_FEATURES
    + DEVICE_FEATURES
    + HTTP_FEATURES
):
    features[feature] = 0.0

payload = {
    "features": features
}
risk_result = predict_current_risk(
    {
        "features": features
    }
)

print(risk_result)
from src.server.inference import (
    predict_behavioral_risk
)

payload = {

    "payload_id":
        "TEST-001",

    "username":
        "test_user",

    "hostname":
        "test_pc",

    "daily_sequence": [

        {
            "overall_risk": 0.10,
            "rf_s1_prob": 0.05,
            "rf_s2_prob": 0.02,
            "rf_s3_prob": 0.01
        },

        {
            "overall_risk": 0.12,
            "rf_s1_prob": 0.04,
            "rf_s2_prob": 0.03,
            "rf_s3_prob": 0.01
        },

        {
            "overall_risk": 0.11,
            "rf_s1_prob": 0.03,
            "rf_s2_prob": 0.02,
            "rf_s3_prob": 0.01
        },

        {
            "overall_risk": 0.15,
            "rf_s1_prob": 0.08,
            "rf_s2_prob": 0.04,
            "rf_s3_prob": 0.02
        },

        {
            "overall_risk": 0.14,
            "rf_s1_prob": 0.06,
            "rf_s2_prob": 0.03,
            "rf_s3_prob": 0.02
        },

        {
            "overall_risk": 0.18,
            "rf_s1_prob": 0.10,
            "rf_s2_prob": 0.05,
            "rf_s3_prob": 0.02
        },

        {
            "overall_risk": 0.20,
            "rf_s1_prob": 0.15,
            "rf_s2_prob": 0.08,
            "rf_s3_prob": 0.03
        },

        {
            "overall_risk": 0.90,
            "rf_s1_prob": 0.92,
            "rf_s2_prob": 0.03,
            "rf_s3_prob": 0.01
        }

    ]

}

result = predict_behavioral_risk(
    payload
)

print(result)
import pandas as pd

from src.server.inference import (
    predict_scenario
)


DATASET = (
    "scenario_training_dataset_with_xgb.csv"
)


df = pd.read_csv(
    DATASET
)

row = df.iloc[0]


exclude = {

    "user",
    "date",
    "label",

    "rf_normal_prob",
    "rf_s1_prob",
    "rf_s2_prob",
    "rf_s3_prob"

}


features = {

    col: float(row[col])

    for col in df.columns

    if col not in exclude

}


payload = {

    "features":
        features

}


print()
print("=" * 80)
print("XGB TEST")
print("=" * 80)

result = predict_scenario(
    payload
)

print(result)