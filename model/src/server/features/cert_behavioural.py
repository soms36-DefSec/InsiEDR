# src/server/features/cert_behavioural.py

import os

import pandas as pd

from .extractors.logon import (
    extract_logon_features
)

from .extractors.device import (
    extract_device_features
)

from .extractors.file import (
    extract_file_features
)

from .extractors.http import (
    extract_http_features
)

from .extractors.EDR import (
    extract_edr_features
)


class CERTBehavioralExtractor:

    def __init__(self, dataset_path):

        self.dataset_path = dataset_path

        self.logon_df = None
        self.device_df = None
        self.file_df = None

    def load_data(self):

        print(
            "Loading logon.csv..."
        )

        self.logon_df = pd.read_csv(

            os.path.join(
                self.dataset_path,
                "logon.csv"
            )

        )

        print(
            "logon shape:",
            self.logon_df.shape
        )

        print(
            "Loading file.csv..."
        )

        self.file_df = pd.read_csv(

            os.path.join(
                self.dataset_path,
                "file.csv"
            )

        )

        print(
            "file shape:",
            self.file_df.shape
        )

        print(
            "Loading device.csv..."
        )

        self.device_df = pd.read_csv(

            os.path.join(
                self.dataset_path,
                "device.csv"
            )

        )

        print(
            "device shape:",
            self.device_df.shape
        )

        print(
            "Renaming columns (timestamp->date, user_id->user)..."
        )

        # Rename raw log columns to match extractor expectations
        rename_map = {"timestamp": "date", "user_id": "user"}
        if "timestamp" in self.logon_df.columns:
            self.logon_df = self.logon_df.rename(columns=rename_map)
        if "timestamp" in self.file_df.columns:
            self.file_df = self.file_df.rename(columns=rename_map)
        if "timestamp" in self.device_df.columns:
            self.device_df = self.device_df.rename(columns=rename_map)

        print(
            "Converting timestamps..."
        )

        self.logon_df["date"] = pd.to_datetime(
            self.logon_df["date"]
        )

        self.file_df["date"] = pd.to_datetime(
            self.file_df["date"]
        )

        self.device_df["date"] = pd.to_datetime(
            self.device_df["date"]
        )

        print(
            "Finished loading CERT data"
        )

    def extract(self):

        self.load_data()

        logon_features = (
            extract_logon_features(
                self.logon_df
            )
        )

        device_features = (
            extract_device_features(
                self.device_df
            )
        )

        file_features = (
            extract_file_features(
                self.file_df
            )
        )

        http_features = (
            extract_http_features(
                self.dataset_path
            )
        )

        edr_features = (
            extract_edr_features()
        )

        print(
            "Merging feature tables..."
        )

        feature_tables = [

            device_features,

            file_features,

            http_features,

            edr_features

        ]

        df = logon_features

        for feature_df in feature_tables:

            if len(feature_df) == 0:

                continue

            df = df.merge(

                feature_df,

                on=[
                    "user",
                    "date"
                ],

                how="outer"

            )

        df = df.fillna(0)

        df = df.sort_values(

            [
                "user",
                "date"
            ]

        )

        df = df.reset_index(
            drop=True
        )

        print()
        print(
            "Final feature dataframe:"
        )

        print(
            df.shape
        )

        print()

        print(
            df.head()
        )

        return df