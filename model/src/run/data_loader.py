import pandas as pd
import numpy as np
import joblib
import os
from src.run.feature_to_sequence import (
    create_sequences
)


from sklearn.preprocessing import MinMaxScaler

def load_feature_dataset(path):

    df = pd.read_csv(path)
    print("\nACTUALLY LOADED:")
    print(path) 

    print("\nRAW COLUMN COUNT:")
    print(len(df.columns))

    print("\nRAW LAST 10 COLUMNS:")
    print(df.columns.tolist()[-10:])
    df["date"] = pd.to_datetime(
        df["date"]
    )
    if "label" in df.columns:
        df = df.drop(
            columns=["label"]
        )
    feature_columns = [

        c

        for c in df.columns

        if c not in [

            "user",
            "date"

        ]

    ]


    print(
        f"Feature Count: {len(feature_columns)}"
    )

    print(
        feature_columns[-10:]
    )
    print(
        "Saved: models/feature_scaler.pkl"
    )

    return df


def get_feature_columns(df):

    return [

        c

        for c in df.columns

        if c not in [

            "user",
            "date"

        ]

    ]


def build_sequences(
        df,
        sequence_length=7
):

    feature_columns = (
        get_feature_columns(df)
    )

    X, y, metadata = (
        create_sequences(
            df,
            feature_columns,
            sequence_length
        )
    )

    return (
        X,
        y,
        metadata,
        feature_columns
    )


def split_data(
        X,
        y,
        metadata
):

    n = len(X)

    train_end = int(
        n * 0.7
    )

    val_end = int(
        n * 0.8
    )

    X_train = X[:train_end]
    y_train = y[:train_end]

    X_val = X[
        train_end:val_end
    ]

    y_val = y[
        train_end:val_end
    ]

    X_test = X[val_end:]
    y_test = y[val_end:]

    metadata_train = (
        metadata[:train_end]
    )

    metadata_val = (
        metadata[
            train_end:val_end
        ]
    )

    metadata_test = (
        metadata[val_end:]
    )

    return (

        X_train,
        y_train,

        X_val,
        y_val,

        X_test,
        y_test,

        metadata_train,
        metadata_val,
        metadata_test
    )