# src/server/features/extractors/logon.py

import pandas as pd
from scipy.stats import entropy


def extract_logon_features(logon_df):

    print("Preparing logon dataframe...")

    df = logon_df.copy()

    df["day"] = df["date"].dt.date
    df["hour"] = df["date"].dt.hour

    df["after_hours"] = (
        (df["hour"] < 7)
        |
        (df["hour"] >= 18)
    ).astype(int)

    print("Computing aggregates...")

    grouped = df.groupby(
        ["user", "day"]
    )

    result = grouped.agg(

        logon_count=(
            "activity",
            lambda x:
                (x == "Logon").sum()
        ),

        logoff_count=(
            "activity",
            lambda x:
                (x == "Logoff").sum()
        ),

        unique_pc_count=(
            "pc",
            "nunique"
        ),

        daily_unique_pc_count=(
            "pc",
            "nunique"
        )

    ).reset_index()

    print(
        "Computing after-hours metrics..."
    )

    after_hours = (

        df[
            df["activity"] == "Logon"
        ]

        .groupby(
            ["user", "day"]
        )["after_hours"]

        .sum()

        .reset_index(
            name="after_hours_logon"
        )

    )

    result = result.merge(

        after_hours,

        on=["user", "day"],

        how="left"

    )

    result[
        "after_hours_logon"
    ] = result[
        "after_hours_logon"
    ].fillna(0)

    result[
        "daily_after_hours_logon_ratio"
    ] = (

        result[
            "after_hours_logon"
        ]

        /

        result[
            "logon_count"
        ].clip(lower=1)

    )

    print(
        "Computing first logon..."
    )

    first_logon = (

        df[
            df["activity"] == "Logon"
        ]

        .groupby(
            ["user", "day"]
        )["hour"]

        .min()

        .reset_index(
            name="first_logon_time"
        )

    )

    result = result.merge(

        first_logon,

        on=["user", "day"],

        how="left"

    )

    print(
        "Computing last logoff..."
    )

    last_logoff = (

        df[
            df["activity"] == "Logoff"
        ]

        .groupby(
            ["user", "day"]
        )["hour"]

        .max()

        .reset_index(
            name="last_logoff_time"
        )

    )

    result = result.merge(

        last_logoff,

        on=["user", "day"],

        how="left"

    )

    print(
        "Computing weekend flag..."
    )

    result[
        "weekend_logon"
    ] = (
        pd.to_datetime(
            result["day"]
        )
        .dt.weekday
        >= 5
    ).astype(int)

    print(
        "Computing PC entropy..."
    )

    entropy_rows = []

    for idx, (
        (user, day),
        g
    ) in enumerate(

        df.groupby(
            ["user", "day"]
        )

    ):

        if idx % 50000 == 0:

            print(
                f"Entropy groups: {idx}"
            )

        counts = (
            g["pc"]
            .value_counts()
            .values
        )

        entropy_rows.append({

            "user": user,

            "day": day,

            "daily_pc_access_entropy":
                entropy(counts)

        })

    entropy_df = pd.DataFrame(
        entropy_rows
    )

    result = result.merge(

        entropy_df,

        on=["user", "day"],

        how="left"

    )

    result = result.rename(
        columns={
            "day": "date"
        }
    )

    result = result.fillna(0)

    try:
        import os
        import json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", "models", "feature_columns_IF.json"))
        with open(json_path, "r") as f:
            allowed_features = set(json.load(f))
        keep_cols = ["user", "date"] + [col for col in result.columns if col in allowed_features]
        seen = set()
        keep_cols = [x for x in keep_cols if not (x in seen or seen.add(x))]
        result = result[keep_cols]
    except Exception as e:
        print(f"Warning: Could not filter logon features using feature_columns_IF.json: {e}")

    print(
        "Logon feature extraction complete"
    )

    return result