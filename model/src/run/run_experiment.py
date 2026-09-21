import time
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from src.run.config import get_all_configs
import os
import joblib
from src.run.data_loader import (
    load_feature_dataset,
    build_sequences,
    split_data
)

from src.run.model_runner import (
    train_model,
    predict
)

from src.run.evaluator import (
    compute_prediction_error,
    rank_anomalies,
    summarize_errors
)


DATASET_PATH = "scenario_training_dataset_with_xgb.csv"


def build_user_rankings(
        errors,
        metadata
):

    rows = []

    for err, meta in zip(
        errors,
        metadata
    ):

        rows.append({

            "user":
                meta["user"],

            "date":
                meta["target_date"],

            "error":
                float(err)

        })

    anomaly_df = pd.DataFrame(
        rows
    )

    user_scores = (

        anomaly_df

        .groupby("user")

        .agg(

            max_error=(
                "error",
                "max"
            ),

            mean_error=(
                "error",
                "mean"
            ),

            anomaly_days=(
                "error",
                "count"
            )

        )

        .reset_index()

    )

    #
    # Current method
    #
    user_scores["score_v1"] = (

        user_scores["max_error"]

        *

        np.log1p(
            user_scores["anomaly_days"]
        )

    )

    #
    # Severity × Persistence × Consistency
    #
    user_scores["score_v2"] = (

        user_scores["max_error"]

        *

        user_scores["mean_error"]

        *

        np.sqrt(
            user_scores["anomaly_days"]
        )

    )

    #
    # Pure persistence
    #
    user_scores["score_v3"] = (

        user_scores["mean_error"]

        *

        user_scores["anomaly_days"]

    )

    #
    # Balanced version
    #
    user_scores["score_v4"] = (

        (

            0.4
            * user_scores["max_error"]

        )

        +

        (

            0.6
            * user_scores["mean_error"]

        )

    ) * np.log1p(

        user_scores["anomaly_days"]

    )

    #
    # Keep current ranking as default
    #
    # CHANGED: Sort by score_v2 by default instead of score_v1 as it provides better recall
    user_scores = user_scores.sort_values(

        "score_v2",

        ascending=False

    ).reset_index(
        drop=True
    )

    return (
        anomaly_df,
        user_scores
    )

if __name__ == "__main__":

    configs = get_all_configs()

    for config_id, config in enumerate(configs):

        print("\n" + "=" * 80)
        print(
            f"CONFIG {config_id}"
        )
        print(config)
        print("=" * 80)

        print(
            "\nLoading feature dataset..."
        )

        df = load_feature_dataset(
            DATASET_PATH
        )

        print(
            "Original Shape:",
            df.shape
        )

        print(
            "\nReducing feature space for RVFL..."
        )

        #
        # Create a single scenario score
        #

        df["scenario_risk"] = (

            df[
                [
                    "rf_s1_prob",
                    "rf_s2_prob",
                    "rf_s3_prob"
                ]
            ]

            .max(axis=1)

        )

        #
        # Create final RVFL signal
        #

        df["rvfl_risk"] = (

            0.3 * df["overall_risk"]

            +

            0.7 * df["scenario_risk"]

        )

        #
        # Keep only the single signal
        #

        df = df[
            [
                "user",
                "date",
                "rvfl_risk"
            ]
        ]

        feature_columns = [
            "rvfl_risk"
        ]

        print(
            "Using fused RVFL signal"
        )

        print(
            "Feature Count:",
            len(feature_columns)
        )

        print(
            feature_columns
        )

        print(
            "Shape:",
            df.shape
        )
        print(
            "\nBuilding sequences..."
        )

        (
            X,
            y,
            metadata,
            feature_columns
        ) = build_sequences(
            df,
            sequence_length=config[
                "sequence_length"
            ]
        )

        print(
            "X shape:",
            X.shape
        )

        print(
            "y shape:",
            y.shape
        )

        (
            X_train,
            y_train,

            X_val,
            y_val,

            X_test,
            y_test,

            metadata_train,
            metadata_val,
            metadata_test

        ) = split_data(
            X,
            y,
            metadata
        )
        print(
            "\nScaling train/val/test..."
        )

        #
        # Feature scaler
        #
        feature_scaler = MinMaxScaler()

        feature_scaler.fit(

            X_train.reshape(
                -1,
                X_train.shape[2]
            )

        )

        X_train = (

            feature_scaler.transform(

                X_train.reshape(
                    -1,
                    X_train.shape[2]
                )

            )

            .reshape(
                X_train.shape
            )

        )

        X_val = (

            feature_scaler.transform(

                X_val.reshape(
                    -1,
                    X_val.shape[2]
                )

            )

            .reshape(
                X_val.shape
            )

        )

        X_test = (

            feature_scaler.transform(

                X_test.reshape(
                    -1,
                    X_test.shape[2]
                )

            )

            .reshape(
                X_test.shape
            )

        )

        #
        # Target scaler
        #
        target_scaler = MinMaxScaler()

        target_scaler.fit(
            y_train
        )

        y_train = (
            target_scaler.transform(
                y_train
            )
        )

        y_val = (
            target_scaler.transform(
                y_val
            )
        )

        y_test = (
            target_scaler.transform(
                y_test
            )
        )

        os.makedirs(
            "models",
            exist_ok=True
        )

        joblib.dump(

            feature_scaler,

            "models/feature_scaler.pkl"

        )

        joblib.dump(

            target_scaler,

            "models/target_scaler.pkl"

        )

        print(
            "Saved feature_scaler.pkl"
        )

        print(
            "Saved target_scaler.pkl"
        )
        print(
            "\nTrain Min:",
            X_train.min()
        )

        print(
            "Train Max:",
            X_train.max()
        )

        print(
            "Test Min:",
            X_test.min()
        )

        print(
            "Test Max:",
            X_test.max()
        )
        train_users = {
            m["user"]
            for m in metadata_train
        }

        test_users = {
            m["user"]
            for m in metadata_test
        }

        overlap = train_users & test_users

        print("\nTRAIN USERS:", len(train_users))
        print("TEST USERS:", len(test_users))
        print("OVERLAP:", len(overlap))

        if len(overlap) > 0:

            print("\nFIRST 20 OVERLAPPING USERS:")
            print(sorted(list(overlap))[:20])
        test_users = {

            m["user"]

            for m in metadata_test

        }

        print(
            "\nUsers in test set:",
            len(test_users)
        )

        import pandas as pd

        insiders = pd.read_csv(
            "data/CERT/r4.2/answers/answers/insiders.csv"
        )

        insider_users = set(

            insiders[
                insiders["dataset"] == 4.2
            ]["user"]

        )

        test_insiders = (

            insider_users
            &
            test_users

        )

        print(
            "Total insiders:",
            len(insider_users)
        )

        print(
            "Insiders in test:",
            len(test_insiders)
        )

        print(
            sorted(test_insiders)
        )
        print(
            "\nTraining samples:",
            len(X_train)
        )

        print(
            "Validation samples:",
            len(X_val)
        )

        print(
            "Test samples:",
            len(X_test)
        )

        start = time.time()

        model, ridge_models = train_model(
            X_train,
            y_train,
            config
        )
        import os
        import json
        import joblib

        os.makedirs(
            "models",
            exist_ok=True
        )

        joblib.dump(
            ridge_models,
            "models/ridge_models.pkl"
        )

        with open(
            "models/rvfl_metadata.json",
            "w"
        ) as f:

            json.dump({

                "input_features":
                    X_train.shape[2],

                "hidden_size":
                    config["hidden_size"],

                "num_layers":
                    config["num_layers"],

                "sequence_length":
                    config["sequence_length"]

            }, f, indent=4)

        with open(
            "models/feature_columns.json",
            "w"
        ) as f:

            json.dump(
                feature_columns,
                f,
                indent=4
            )
        training_time = (
            time.time() - start
        )

        print(
            f"\nTraining Time: "
            f"{training_time:.2f}s"
        )

        print(
            "\nGenerating predictions..."
        )

        predictions = predict(
            model,
            ridge_models,
            X_test
        )

        print(
            "Prediction shape:",
            predictions.shape
        )

        print(
            "\nComputing prediction error..."
        )
        print("y_test shape:", y_test.shape)
        print("predictions shape:", predictions.shape)
        errors = (
            compute_prediction_error(
                y_test,
                predictions
            )
        )

        stats = (
            summarize_errors(
                errors
            )
        )

        print(
            "\nError Statistics"
        )

        print(
            stats
        )

        print(
            "\nBuilding anomaly rankings..."
        )

        top_anomalies = (
            rank_anomalies(
                errors,
                metadata_test,
                top_k=5000
            )
        )

        anomaly_df, user_scores = (
            build_user_rankings(
                errors,
                metadata_test
            )
        )

        print(
            "\nTop 20 Day-Level Anomalies"
        )

        print(
            top_anomalies.head(20)
        )

        print(
            "\nTop 20 User Rankings"
        )

        print(
            user_scores.head(20)
        )

        top_anomalies.to_csv(

            "top_anomalies.csv",

            index=False

        )

        anomaly_df.to_csv(

            "all_anomaly_days.csv",

            index=False

        )

        user_scores.to_csv(

            "top_users.csv",

            index=False

        )

        pd.DataFrame({

            "error": errors

        }).to_csv(

            "prediction_errors.csv",

            index=False

        )

        print(
            "\nSaved:"
        )

        print(
            "top_anomalies.csv"
        )

        print(
            "all_anomaly_days.csv"
        )

        print(
            "top_users.csv"
        )

        print(
            "prediction_errors.csv"
        )
    pd.DataFrame(
    {
        "user": sorted(test_insiders)
    }
    ).to_csv(
        "test_insiders.csv",
        index=False
    )
    print(
        "\nExperiment Complete."
    )