import pandas as pd

from src.run.feature_to_sequence import (
    create_sequences
)


df = pd.read_csv(
    "if_enriched_features.csv"
)

exclude = [

    "user",
    "date"

]

feature_columns = [

    c
    for c in df.columns
    if c not in exclude

]

X, y, metadata = (

    create_sequences(
        df,
        feature_columns,
        sequence_length=7
    )

)

print()

print(
    "X shape:",
    X.shape
)

print(
    "y shape:",
    y.shape
)

print()

print(
    "Feature Count:",
    X.shape[2]
)

print(
    "Sequence Length:",
    X.shape[1]
)

print()

print(
    metadata[0]
)