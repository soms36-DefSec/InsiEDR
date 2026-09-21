import numpy as np
from src.run.config import get_all_configs

def create_sequences(
        df,
        feature_columns,
        sequence_length=get_all_configs()[0]["sequence_length"]
):

    X = []
    y = []

    metadata = []

    users = df["user"].unique()

    for user in users:

        user_df = (
            df[
                df["user"] == user
            ]
            .sort_values(
                "date"
            )
            .reset_index(
                drop=True
            )
        )

        feature_matrix = (
            user_df[
                feature_columns
            ]
            .values
        )

        dates = (
            user_df["date"]
            .values
        )

        if (
            len(feature_matrix)
            <= sequence_length
        ):
            continue

        for i in range(
            sequence_length,
            len(feature_matrix)
        ):

            X.append(

                feature_matrix[
                    i-sequence_length:i
                ]

            )

            y.append(

                feature_matrix[i]

            )

            metadata.append({

                "user":
                    user,

                "target_date":
                    str(
                        dates[i]
                    )

            })

    return (

        np.array(
            X,
            dtype=np.float32
        ),

        np.array(
            y,
            dtype=np.float32
        ),

        metadata
    )