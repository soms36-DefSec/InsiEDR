from abc import ABC, abstractmethod
import pandas as pd


class FeatureExtractor(ABC):

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def feature_names(self):
        pass