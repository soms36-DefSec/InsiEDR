import pandas as pd


FEATURE_FILE = "if_enriched_features.csv"

INSIDERS_FILE = (
    "data/CERT/r4.2/answers/answers/"
    "insiders.csv"
)

OUTPUT_FILE = (
    "scenario_training_dataset.csv"
)


SCENARIO_MAP = {

    "1": 1,
    "2": 2,
    "3": 3

}


def load_features():

    df = pd.read_csv(
        FEATURE_FILE
    )

    df["date"] = pd.to_datetime(
        df["date"]
    ).dt.normalize()

    return df


def load_insiders():

    insiders = pd.read_csv(
        INSIDERS_FILE
    )

    insiders = insiders[
        insiders["dataset"] == 4.2
    ].copy()

    insiders["start"] = pd.to_datetime(
        insiders["start"]
    ).dt.normalize()

    insiders["end"] = pd.to_datetime(
        insiders["end"]
    ).dt.normalize()

    insiders["scenario"] = (

        insiders["scenario"]

        .astype(str)

        .str.strip()

    )

    return insiders


def create_labels(
        feature_df,
        insiders_df
):

    feature_df = feature_df.copy()

    feature_df["label"] = 0

    for _, insider in insiders_df.iterrows():

        scenario_label = (

            SCENARIO_MAP.get(
                insider["scenario"],
                0
            )

        )

        mask = (

            (feature_df["user"]
             == insider["user"])

            &

            (
                feature_df["date"]
                >= insider["start"]
            )

            &

            (
                feature_df["date"]
                <= insider["end"]
            )

        )

        feature_df.loc[
            mask,
            "label"
        ] = scenario_label

    return feature_df


def print_statistics(df):

    print()
    print("=" * 80)
    print("LABEL DISTRIBUTION")
    print("=" * 80)
    print()

    print(
        df["label"]
        .value_counts()
        .sort_index()
    )

    print()

    print(
        df["label"]
        .value_counts(
            normalize=True
        )
        .sort_index()
    )

    print()


def print_sample_labels(df):

    print()
    print("=" * 80)
    print("SAMPLE LABELED ROWS")
    print("=" * 80)
    print()

    labeled_rows = df[
        df["label"] != 0
    ]

    print(

        labeled_rows[
            [
                "user",
                "date",
                "label"
            ]
        ]

        .head(20)

    )

    print()


def main():

    print(
        "\nLoading features..."
    )

    feature_df = (
        load_features()
    )

    print(
        "Rows:",
        len(feature_df)
    )

    print(
        "\nLoading insider labels..."
    )

    insiders_df = (
        load_insiders()
    )

    print(
        "Insider events:",
        len(insiders_df)
    )

    print(
        "\nGenerating labels..."
    )

    dataset = create_labels(

        feature_df,

        insiders_df

    )

    print_statistics(
        dataset
    )

    print_sample_labels(
        dataset
    )

    dataset.to_csv(

        OUTPUT_FILE,

        index=False

    )

    print(
        "\nSaved:"
    )

    print(
        OUTPUT_FILE
    )

    print(
        "\nDone."
    )
    print(
    dataset.groupby("label")["user"]
    .nunique()
)

if __name__ == "__main__":
    main()