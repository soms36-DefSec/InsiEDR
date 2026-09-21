from abc import ABC, abstractmethod
import numpy as np


class AnomalyDetector(ABC):

    @abstractmethod
    def fit(self, X):
        pass

    @abstractmethod
    def score(self, X):
        pass

    @abstractmethod
    def predict(self, X):
        pass