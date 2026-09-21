import numpy as np

from sklearn.ensemble import IsolationForest

from .base import AnomalyDetector


class IFDetector(AnomalyDetector):

    def __init__(
        self,
        contamination=0.05,
        random_state=42
    ):

        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1
        )

    def fit(self, X):

        self.model.fit(X)

    def score(self, X):

        """
        Higher = more anomalous
        """

        return -self.model.score_samples(X)

    def predict(self, X):

        return self.model.predict(X)