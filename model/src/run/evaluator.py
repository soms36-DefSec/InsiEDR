import numpy as np
import pandas as pd


def compute_prediction_error(
        y_true,
        y_pred
):

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)

    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)

    return np.mean(

        np.square(
            y_true - y_pred
        ),

        axis=1

    )


def rank_anomalies(
        errors,
        metadata,
        top_k=100
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

    df = pd.DataFrame(
        rows
    )

    df = df.sort_values(
        "error",
        ascending=False
    )

    return df.head(top_k)


def summarize_errors(
        errors
):

    return {

        "mean":
            float(
                np.mean(errors)
            ),

        "std":
            float(
                np.std(errors)
            ),

        "max":
            float(
                np.max(errors)
            ),

        "min":
            float(
                np.min(errors)
            )
    }