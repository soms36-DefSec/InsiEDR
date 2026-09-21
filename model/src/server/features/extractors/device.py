# src/server/features/extractors/device.py

import pandas as pd


def is_after_hours(timestamp):

    return int(

        timestamp.hour < 7

        or

        timestamp.hour >= 18

    )


def extract_device_features(device_df):

    print(
        "Extracting device features..."
    )

    df = device_df.copy()

    df["day"] = (
        df["date"]
        .dt.date
    )

    rows = []

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
                f"Device groups: {idx}"
            )

        connects = g[
            g["activity"]
            == "Connect"
        ]

        disconnects = g[
            g["activity"]
            == "Disconnect"
        ]

        first_connect = 0

        if len(connects) > 0:

            first_connect = (

                connects["date"]

                .dt.hour

                .min()

            )

        last_disconnect = 0

        if len(disconnects) > 0:

            last_disconnect = (

                disconnects["date"]

                .dt.hour

                .max()

            )

        rows.append({

            "user":
                user,

            "date":
                day,

            "usb_connect_count":
                len(connects),

            "usb_disconnect_count":
                len(disconnects),

            "after_hours_usb_usage":
                sum(

                    is_after_hours(x)

                    for x in g["date"]

                ),

            "daily_device_connect_count":
                len(connects),

            "daily_device_usage_flag":
                int(len(g) > 0),

            "first_usb_usage_time":
                first_connect,

            "last_usb_usage_time":
                last_disconnect

        })

    print(
        "Device feature extraction complete"
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
        print(f"Warning: Could not filter device features using feature_columns_IF.json: {e}")

    return result