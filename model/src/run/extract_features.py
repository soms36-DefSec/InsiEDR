# src/run/test_features.py

from src.server.features.cert_behavioural import (
    CERTBehavioralExtractor
)

extractor = CERTBehavioralExtractor(
    "data/CERT/r4.2/r4.2"
)

df = extractor.extract()

print(df.shape)
print(df.head())
print(df.columns.tolist())
print(
    "Date Range:"
)

print(
    df["date"].min()
)

print(
    df["date"].max()
)

