from src.server.features.cert_behavioural import (
    CERTBehavioralExtractor
)

from src.server.anomaly.domain_models import (
    DomainIsolationForest
)

from src.server.anomaly.rolling_features import (
    add_risk_trend_features,
    build_daily_risk_dataframe
)

from src.server.features.feature_schema import (
    LOGON_FEATURES,
    FILE_FEATURES,
    DEVICE_FEATURES,
    HTTP_FEATURES
)


CERT_PATH = r"data/CERT/r4.2/r4.2"
import os
import joblib

def existing_columns(
        feature_df,
        feature_list
):

    return [
        c
        for c in feature_list
        if c in feature_df.columns
    ]


def main():

    print(
        "\nLoading CERT features..."
    )

    extractor = (
        CERTBehavioralExtractor(
            CERT_PATH
        )
    )

    feature_df = (
        extractor.extract()
    )

    print(
        "\nFeature dataframe shape:"
    )

    print(
        feature_df.shape
    )

    logon_features = (
        existing_columns(
            feature_df,
            LOGON_FEATURES
        )
    )

    file_features = (
        existing_columns(
            feature_df,
            FILE_FEATURES
        )
    )

    device_features = (
        existing_columns(
            feature_df,
            DEVICE_FEATURES
        )
    )

    http_features = (
        existing_columns(
            feature_df,
            HTTP_FEATURES
        )
    )

    print(
        "\nBuilding IF matrices..."
    )

    logon_X = (
        feature_df[
            logon_features
        ]
        .fillna(0)
        .values
    )

    file_X = (
        feature_df[
            file_features
        ]
        .fillna(0)
        .values
    )

    device_X = (
        feature_df[
            device_features
        ]
        .fillna(0)
        .values
    )

    http_X = (
        feature_df[
            http_features
        ]
        .fillna(0)
        .values
    )

    print(
        "Training Isolation Forests..."
    )

    domain_if = (
        DomainIsolationForest(
            contamination=0.05
        )
    )

    domain_if.fit(
        logon_X,
        file_X,
        device_X,
        http_X
    )
    

    os.makedirs(
        "models",
        exist_ok=True
    )

    joblib.dump(
        domain_if,
        "models/domain_isolation_forest.pkl"
    )

    print(
        "\nSaved: models/domain_isolation_forest.pkl"
    )
    print(
        "Scoring..."
    )

    scores = domain_if.score(
        logon_X,
        file_X,
        device_X,
        http_X
    )

    print(
        "\nSample scores"
    )

    print(
        "Logon:",
        scores["logon"][:10]
    )

    print(
        "File:",
        scores["file"][:10]
    )

    print(
        "Device:",
        scores["device"][:10]
    )

    print(
        "HTTP:",
        scores["http"][:10]
    )

    risk_df = (
        build_daily_risk_dataframe(
            feature_df,
            scores["logon"],
            scores["file"],
            scores["device"],
            scores["http"]
        )
    )

    print(
        "\nRisk dataframe shape:"
    )

    print(
        risk_df.shape
    )

    print(
        "\nRisk dataframe head:"
    )

    print(
        risk_df.head()
    )

    merged_df = (
        feature_df.merge(
            risk_df,
            on=["user", "date"]
        )
    )

    merged_df = add_risk_trend_features(
        merged_df
    )
    print(
        "\nMerged dataframe shape:"
    )

    print(
        merged_df.shape
    )

    print(
        "\nFinal columns:"
    )

    print(
        merged_df.columns.tolist()
    )

    merged_df.to_csv(
        "if_enriched_features.csv",
        index=False
    )

    print(
        "\nSaved:"
    )

    print(
        "if_enriched_features.csv"
    )
    for col in merged_df.columns:
        if col not in ["user","date"]:
            print(
                col,
                merged_df[col].nunique()
            )

if __name__ == "__main__":
    main()