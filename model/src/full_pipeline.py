import time

from src.run.test_isolation_forest import (
    main as run_isolation_forest
)


def main():

    print("\n" + "=" * 80)
    print("STAGE 1")
    print("CERT -> IF ENRICHED FEATURES")
    print("=" * 80)

    start = time.time()

    run_isolation_forest()

    print(
        f"\nStage 1 Complete "
        f"({time.time() - start:.2f}s)"
    )

    print("\n" + "=" * 80)
    print("STAGE 2")
    print("REDRVFL")
    print("=" * 80)

    start = time.time()

    import runpy

    runpy.run_module(
        "src.run.run_experiment",
        run_name="__main__"
    )

    print(
        f"\nStage 2 Complete "
        f"({time.time() - start:.2f}s)"
    )

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)

    print(
        "\nOutputs:"
    )

    print(
        "if_enriched_features.csv"
    )

    print(
        "top_anomalies.csv"
    )

    print(
        "prediction_errors.csv"
    )


if __name__ == "__main__":
    main()