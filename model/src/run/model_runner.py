import torch

from sklearn.linear_model import Ridge

from src.red_revfl_orchestrator import (
    RedRVFLOrchestrator
)


def train_model(
        X_train,
        y_train,
        config
):

    X_train_tensor = torch.tensor(
        X_train,
        dtype=torch.float32
    )

    input_features = (
        X_train.shape[2]
    )

    model = RedRVFLOrchestrator(
        input_features=input_features,
        hidden_size=config["hidden_size"],
        num_layers=config["num_layers"]
    )

    feature_matrices = (
        model.extract_features(
            X_train_tensor
        )
    )

    ridge_models = []

    for D in feature_matrices:

        ridge = Ridge(
            alpha=config["ridge_alpha"],
            solver="lsqr"
        )
        ridge.fit(
            D,
            y_train
        )

        ridge_models.append(
            ridge
        )

    return (
        model,
        ridge_models
    )


def predict(
        model,
        ridge_models,
        X
):

    X_tensor = torch.tensor(
        X,
        dtype=torch.float32
    )

    predictions = model.predict(
        X_tensor,
        ridge_models
    )

    return predictions