import numpy as np
import torch
from src.architecture import RandomLSTM
from src.architecture import build_feature_matrix
from src.architecture import build_layer_input


class RedRVFLOrchestrator:
    """
    Orchestrates the RedRVFL architecture.

    Responsibilities:
    - Manage multiple RandomLSTM layers
    - Construct feature matrices
    - Interface with external ridge regression training
    """

    def __init__(self, input_features, hidden_size, num_layers):

        self.input_features = input_features
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.layers = []

        for i in range(num_layers):
            torch.manual_seed(1234 + i)
            if i == 0:
                input_size = input_features
            else:
                input_size = input_features + hidden_size

            lstm = RandomLSTM(input_size, hidden_size)

            self.layers.append(lstm)

    def extract_features(self, X_tensor):
        """
        Extract feature matrices for all layers.

        Returns
        -------
        feature_matrices : list
            list of D matrices used for ridge regression
        """

        feature_matrices = []

        xtensor_current = X_tensor

        for i in range(self.num_layers):

            lstm = self.layers[i]

            hidden = lstm(xtensor_current)

            D = build_feature_matrix(X_tensor, hidden)

            feature_matrices.append(D)

            if i < self.num_layers - 1:

                xtensor_current = build_layer_input(hidden, X_tensor)

        return feature_matrices

    def predict(self, X_tensor, ridge_models):
        """
        Generate predictions using trained ridge models.

        ridge_models must correspond to each layer.
        """

        predictions = []

        feature_matrices = self.extract_features(X_tensor)

        for i, ridge_model in enumerate(ridge_models):

            D = feature_matrices[i]

            pred = ridge_model.predict(D)

            predictions.append(pred)

        predictions = np.array(predictions)
        final_prediction = np.median(predictions, axis=0)

        return final_prediction