# src/server/features/extractors/file.py

from collections import defaultdict

import pandas as pd
from scipy.stats import entropy


def extract_file_features(file_df):

    print(
        "Extracting file features..."
    )

    df = file_df.copy()

    df["day"] = (
        df["date"]
        .dt.date
    )

    df["hour"] = (
        df["date"]
        .dt.hour
    )

    rows = []

    seen_files = defaultdict(set)

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
                f"File groups: {idx}"
            )

        filenames = set(
            g["filename"]
        )

        new_files = (
            filenames
            -
            seen_files[user]
        )

        filename_counts = (
            g["filename"]
            .value_counts()
        )

        after_hours_count = (

            (
                g["hour"] < 7
            )

            |

            (
                g["hour"] >= 18
            )

        ).sum()

        weekend_count = (

            g["date"]

            .dt.weekday

            >= 5

        ).sum()

        repeat_count = (

            len(g)

            -

            len(filenames)

        )

        rows.append({

            "user":
                user,

            "date":
                day,

            "file_access_count":
                len(g),

            "daily_unique_filename_count":
                len(filenames),

            "daily_new_filename_count":
                len(new_files),

            "daily_file_access_entropy":
                entropy(
                    filename_counts.values
                ),

            "after_hours_file_access":
                after_hours_count,

            "weekend_file_access":
                weekend_count,

            "daily_repeat_file_access_count":
                repeat_count,

            "daily_repeat_file_ratio":
                repeat_count
                /
                max(
                    len(g),
                    1
                ),

            "first_file_access_time":
                g["hour"].min(),

            "last_file_access_time":
                g["hour"].max()

        })

        seen_files[user].update(
            filenames
        )

    print(
        "File feature extraction complete"
    )

    result = pd.DataFrame(rows)
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
        print(f"Warning: Could not filter file features using feature_columns_IF.json: {e}")

    return result