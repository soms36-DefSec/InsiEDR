import json
import joblib
import pandas as pd
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix
)

from sklearn.model_selection import (
    GroupShuffleSplit
)


DATASET_FILE = (
    "scenario_training_dataset.csv"
)

MODEL_FILE = (
    "models/scenario_xgb.pkl"
)

FEATURES_FILE = (
    "models/scenario_xgb_features.json"
)

OUTPUT_FILE = (
    "scenario_training_dataset_with_xgb.csv"
)


def load_dataset():

    df = pd.read_csv(
        DATASET_FILE
    )

    df["date"] = pd.to_datetime(
        df["date"]
    )

    return df


def prepare_features(df):

    feature_columns = [

        c

        for c in df.columns

        if c not in [

            "user",
            "date",
            "label"

        ]

    ]

    X = df[
        feature_columns
    ]

    y = df[
        "label"
    ]

    groups = df[
        "user"
    ]

    return (

        X,
        y,
        groups,
        feature_columns

    )


def split_dataset(
        X,
        y,
        groups
):

    splitter = (
        GroupShuffleSplit(

            n_splits=1,

            test_size=0.2,

            random_state=42

        )
    )

    train_idx, test_idx = next(

        splitter.split(

            X,
            y,

            groups=groups

        )

    )

    return (

        X.iloc[
            train_idx
        ],

        X.iloc[
            test_idx
        ],

        y.iloc[
            train_idx
        ],

        y.iloc[
            test_idx
        ]

    )


def train_model(
        X_train,
        y_train
):

    print()
    print("Applying SMOTE...")

    # CHANGED: Apply SMOTE only to classes 1 and 3 (scaling to match class 0 count),
    # leaving class 2 at its original count to improve model precision.
    class_counts = y_train.value_counts()
    class_0_count = class_counts[0]
    smote = SMOTE(
        sampling_strategy={1: class_0_count, 3: class_0_count},
        random_state=42,
        k_neighbors=3
    )

    X_train_smote, y_train_smote = (

        smote.fit_resample(
            X_train,
            y_train
        )

    )

    print()
    print("Class distribution after SMOTE:")

    print(
        pd.Series(
            y_train_smote
        )
        .value_counts()
        .sort_index()
    )

    print()
    print("Training XGBoost...")

    model = XGBClassifier(

        objective="multi:softprob",

        num_class=4,

        n_estimators=500,

        max_depth=6,

        learning_rate=0.05,

        subsample=0.8,

        colsample_bytree=0.8,

        random_state=42,

        n_jobs=-1,

        eval_metric="mlogloss"

    )

    model.fit(

        X_train_smote,

        y_train_smote

    )

    return model

def evaluate_model(
        model,
        X_test,
        y_test
):

    predictions = (
        model.predict(
            X_test
        )
    )

    print()
    print("=" * 80)
    print("CLASSIFICATION REPORT")
    print("=" * 80)
    print()

    print(

        classification_report(

            y_test,

            predictions,

            digits=4

        )

    )

    print()
    print("=" * 80)
    print("CONFUSION MATRIX")
    print("=" * 80)
    print()

    print(

        confusion_matrix(

            y_test,

            predictions

        )

    )

    print()


def print_feature_importance(
        model,
        feature_columns
):

    importance_df = pd.DataFrame({

        "feature":
            feature_columns,

        "importance":
            getattr(
                model,
                "feature_importances_",
                [0] * len(feature_columns)
            )

    })

    importance_df = (

        importance_df

        .sort_values(

            "importance",

            ascending=False

        )

    )

    print()
    print("=" * 80)
    print("TOP 20 FEATURES")
    print("=" * 80)
    print()

    print(
        importance_df.head(20)
    )

    print()


def save_model(
        model,
        feature_columns
):

    joblib.dump(

        model,

        MODEL_FILE

    )

    with open(

        FEATURES_FILE,

        "w"

    ) as f:

        json.dump(

            feature_columns,

            f,

            indent=4

        )

    print()
    print(
        "Saved model:",
        MODEL_FILE
    )

    print(
        "Saved features:",
        FEATURES_FILE
    )

    print()


def generate_rf_features(
        model,
        df,
        feature_columns
):

    probabilities = (

        model.predict_proba(

            df[
                feature_columns
            ]

        )

    )

    class_labels = (

        model.classes_
    )

    class_map = {

        0: "normal",

        1: "s1",

        2: "s2",

        3: "s3"

    }

    for idx, cls in enumerate(
            class_labels
    ):

        column_name = (

            f"rf_"

            f"{class_map[cls]}"

            f"_prob"

        )

        df[
            column_name
        ] = probabilities[
            :,
            idx
        ]

    return df


def save_enriched_dataset(
        df
):

    df.to_csv(

        OUTPUT_FILE,

        index=False

    )

    print()
    print(
        "Saved enriched dataset:"
    )

    print(
        OUTPUT_FILE
    )

    print()


def main():

    print(
        "\nLoading dataset..."
    )

    df = (
        load_dataset()
    )

    print(
        "Rows:",
        len(df)
    )

    (
        X,
        y,
        groups,
        feature_columns

    ) = prepare_features(
        df
    )

    print(
        "Features:",
        len(feature_columns)
    )

    (
        X_train,
        X_test,

        y_train,
        y_test

    ) = split_dataset(

        X,
        y,
        groups

    )

    print()
    print(
        "Train Rows:",
        len(X_train)
    )

    print(
        "Test Rows:",
        len(X_test)
    )

    print()

    print(
        "Training RF..."
    )
    print()
    print("Original training distribution:")
    print(
        y_train
        .value_counts()
        .sort_index()
    )
    model = train_model(
        X_train,
        y_train,
    )

    evaluate_model(

        model,

        X_test,

        y_test

    )

    print_feature_importance(

        model,

        feature_columns

    )

    save_model(

        model,

        feature_columns

    )

    print(
        "Generating probability features..."
    )

    enriched_df = (
        generate_rf_features(

            model,

            df,

            feature_columns

        )
    )

    save_enriched_dataset(
        enriched_df
    )

    print()
    print(
        "Done."
    )


if __name__ == "__main__":
    main()