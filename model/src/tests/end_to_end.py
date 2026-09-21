import pandas as pd

from src.server.inference import (
    predict_current_risk,
    predict_scenario,
    predict_behavioral_risk
)


DATASET = (
    "scenario_training_dataset_with_xgb.csv"
)


def main():

    print()
    print("=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    df = pd.read_csv(
        DATASET
    )

    #
    # Take first user with
    # at least 8 days
    #

    selected_user = None

    for user, g in df.groupby(
        "user"
    ):

        if len(g) >= 8:

            selected_user = user
            break

    if selected_user is None:

        raise ValueError(
            "No user with >= 8 rows found"
        )

    print(
        "Selected User:",
        selected_user
    )

    user_df = (

        df[
            df["user"]
            == selected_user
        ]

        .sort_values(
            "date"
        )

        .head(8)

    )

    daily_sequence = []

    print()
    print("=" * 80)
    print("RUNNING IF + XGB")
    print("=" * 80)

    for idx, row in enumerate(

        user_df.itertuples()

    ):

        features = {}

        for col in user_df.columns:

            if col in [

                "user",
                "date",
                "label",

                "rf_normal_prob",
                "rf_s1_prob",
                "rf_s2_prob",
                "rf_s3_prob",

                "logon_risk",
                "file_risk",
                "device_risk",
                "http_risk",
                "overall_risk",

                "daily_risk_delta",
                "daily_risk_rolling_mean_7d",
                "daily_risk_rolling_std_7d"

            ]:

                continue

            value = getattr(
                row,
                col
            )

            try:

                features[col] = float(
                    value
                )

            except Exception:

                pass

        payload = {

            "features":
                features

        }

        risk_result = (
            predict_current_risk(
                payload
            )
        )
        #
        # IF outputs
        #

        features["logon_risk"] = (
            risk_result["domain_scores"]["logon"]
        )

        features["file_risk"] = (
            risk_result["domain_scores"]["file"]
        )

        features["device_risk"] = (
            risk_result["domain_scores"]["device"]
        )

        features["http_risk"] = (
            risk_result["domain_scores"]["http"]
        )

        features["overall_risk"] = (
            risk_result["overall_score"]
        )

        #
        # TEMPORARY DUMMY VALUES
        # FOR E2E TEST ONLY
        #

        features["daily_risk_delta"] = 0.0

        features[
            "daily_risk_rolling_mean_7d"
        ] = risk_result[
            "overall_score"
        ]

        features[
            "daily_risk_rolling_std_7d"
        ] = 0.0
        scenario_result = (
            predict_scenario(
                payload
            )
        )

        print()
        print(
            f"Day {idx + 1}"
        )

        print(
            "Risk:",
            risk_result[
                "overall_score"
            ]
        )

        print(
            "Scenario:",
            scenario_result[
                "scenario"
            ]
        )

        daily_sequence.append({

            "overall_risk":

                risk_result[
                    "overall_score"
                ],

            "rf_s1_prob":

                scenario_result[
                    "rf_s1_prob"
                ],

            "rf_s2_prob":

                scenario_result[
                    "rf_s2_prob"
                ],

            "rf_s3_prob":

                scenario_result[
                    "rf_s3_prob"
                ]

        })

    print()
    print("=" * 80)
    print("RUNNING RVFL")
    print("=" * 80)

    rvfl_payload = {

        "payload_id":
            "E2E-TEST",

        "username":
            selected_user,

        "hostname":
            "TEST-PC",

        "daily_sequence":
            daily_sequence

    }

    rvfl_result = (

        predict_behavioral_risk(
            rvfl_payload
        )

    )

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print(
        rvfl_result
    )


if __name__ == "__main__":

    main()