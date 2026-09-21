import pandas as pd
import os

TEST_INSIDERS_FILE = (
    "test_insiders.csv"
)

TOP_USERS_FILE = (
    "top_users.csv"
)

def load_test_insiders():

    if not os.path.exists(
        TEST_INSIDERS_FILE
    ):

        raise FileNotFoundError(

            f"{TEST_INSIDERS_FILE} not found.\n"

            "Run run_experiment.py first "
            "to generate test_insiders.csv"

        )

    df = pd.read_csv(
        TEST_INSIDERS_FILE
    )

    return set(

        df["user"]

        .astype(str)

    )


def evaluate_method(
        users,
        insiders,
        score_column
):

    ranked = users.sort_values(

        score_column,

        ascending=False

    )

    print()
    print("=" * 80)
    print(score_column.upper())
    print("=" * 80)
    print()

    print(
        "Test Insider Count:",
        len(insiders)
    )

    print()

    print(

        ranked[
            [
                "user",
                score_column
            ]
        ].head(20)

    )

    print()

    for k in [

        5,
        10,
        25,
        50,
        100

    ]:

        top_users = set(

            ranked

            .head(k)["user"]

            .astype(str)

        )

        detected = (

            insiders
            &
            top_users

        )

        false_positives = (

            top_users
            -
            insiders

        )

        recall = (

            len(detected)

            /

            len(insiders)

        )

        precision = (

            len(detected)

            /

            len(top_users)

        )

        if (
            precision + recall
        ) > 0:

            f1 = (

                2

                * precision

                * recall

                /

                (
                    precision
                    +
                    recall
                )

            )

        else:

            f1 = 0

        print(
            f"Top-{k}"
        )

        print(
            "Detected:",
            len(detected)
        )

        print(
            "Recall:",
            round(
                recall,
                4
            )
        )

        print(
            "Precision:",
            round(
                precision,
                4
            )
        )

        print(
            "F1:",
            round(
                f1,
                4
            )
        )

        print()

        print(
            "Detected Insiders:"
        )

        print(
            sorted(
                detected
            )
        )

        print()

        print(
            "Missing Insiders:"
        )

        print(

            sorted(

                insiders

                -

                detected

            )

        )

        print()

        print(
            "False Positives:"
        )

        print(
            sorted(
                false_positives
            )
        )

        print()
        print("-" * 80)
        print()


def main():

    insiders = (
        load_test_insiders()
    )

    # CHANGED: Sort by score_v2 by default as it is now the default scoring function, replacing score_v1
    users = pd.read_csv(
        TOP_USERS_FILE
    ).sort_values("score_v2", ascending=False).reset_index(drop=True)

    candidate_scores = [

        c

        for c in users.columns

        if c.startswith(

            "score"

        )

    ]

    # Ensure score_v2 is the first candidate score evaluated
    if "score_v2" in candidate_scores:
        candidate_scores.remove("score_v2")
        candidate_scores.insert(0, "score_v2")

    print()
    print("=" * 80)
    print(
        "TEST INSIDERS"
    )
    print("=" * 80)

    print(
        len(insiders)
    )

    print(
        sorted(insiders)
    )

    print()

    print("=" * 80)
    print(
        "AVAILABLE METHODS"
    )
    print("=" * 80)

    print(
        candidate_scores
    )

    for score_column in candidate_scores:

        evaluate_method(

            users,

            insiders,

            score_column

        )


if __name__ == "__main__":
    main()