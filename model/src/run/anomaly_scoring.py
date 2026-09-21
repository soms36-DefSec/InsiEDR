import numpy as np
import pandas as pd


def prediction_error(
        predictions,
        actuals
):

    return np.mean(
        np.square(
            predictions - actuals
        ),
        axis=1
    )


def rolling_risk(
        error_scores,
        window=7
):

    return (
        pd.Series(error_scores)
        .rolling(
            window=window,
            min_periods=1
        )
        .mean()
        .values
    )


def risk_delta(
        risk_scores
):

    delta = np.diff(
        risk_scores,
        prepend=risk_scores[0]
    )

    return delta