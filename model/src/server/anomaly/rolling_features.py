import pandas as pd
import numpy as np


def build_daily_risk_dataframe(
        feature_df,
        logon_scores,
        file_scores,
        device_scores,
        http_scores
):

    risk_df = feature_df[
        ["user", "date"]
    ].copy()

    risk_df["logon_risk"] = (
        logon_scores
    )

    risk_df["file_risk"] = (
        file_scores
    )

    risk_df["device_risk"] = (
        device_scores
    )

    risk_df["http_risk"] = (
        http_scores
    )

    #
    # Simple aggregate feature
    # NOT a decision score
    #

    risk_df["overall_risk"] = (

        risk_df[

            [
                "logon_risk",
                "file_risk",
                "device_risk",
                "http_risk"
            ]

        ]

        .mean(axis=1)

    )

    return risk_df


def add_risk_trend_features(
        df
):

    df = df.sort_values(

        [
            "user",
            "date"
        ]

    ).copy()

    #
    # Day-to-day change
    #

    df["daily_risk_delta"] = (

        df.groupby("user")[

            "overall_risk"

        ]

        .diff()

        .fillna(0)

    )

    #
    # 7-day rolling mean
    #

    df["daily_risk_rolling_mean_7d"] = (

        df.groupby("user")[

            "overall_risk"

        ]

        .transform(

            lambda x:

            x.rolling(

                window=7,
                min_periods=1

            ).mean()

        )

    )

    #
    # 7-day rolling std
    #

    df["daily_risk_rolling_std_7d"] = (

        df.groupby("user")[

            "overall_risk"

        ]

        .transform(

            lambda x:

            x.rolling(

                window=7,
                min_periods=1

            ).std()

        )

        .fillna(0)

    )

    return df