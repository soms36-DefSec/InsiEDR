from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import MinMaxScaler


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _add_model_path(model_inference_dir: Path) -> None:
    for path in (model_inference_dir, model_inference_dir / "src"):
        text = str(path.resolve())
        if text not in sys.path:
            sys.path.insert(0, text)


def _load_feature_columns(models_dir: Path, df: pd.DataFrame) -> list[str]:
    columns_path = models_dir / "feature_columns.json"
    if columns_path.exists():
        return json.loads(columns_path.read_text(encoding="utf-8"))
    return [column for column in df.columns if column not in {"user", "date"}]


def _prepare_dataframe(csv_path: Path, feature_columns: list[str]) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"user", "date"}
    missing_required = required - set(df.columns)
    if missing_required:
        raise ValueError(f"feature CSV must contain columns: {sorted(missing_required)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["user", "date"]).sort_values(["user", "date"]).reset_index(drop=True)

    for column in feature_columns:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    return df[["user", "date", *feature_columns]]


def _existing(columns: list[str], candidates: list[str]) -> list[str]:
    available = set(columns)
    return [column for column in candidates if column in available]


def _train_domain_if(df: pd.DataFrame, feature_columns: list[str], contamination: float):
    from src.server.anomaly.domain_models import DomainIsolationForest
    from src.server.features.feature_schema import DEVICE_FEATURES, FILE_FEATURES, HTTP_FEATURES, LOGON_FEATURES

    groups = {
        "logon": _existing(feature_columns, LOGON_FEATURES),
        "file": _existing(feature_columns, FILE_FEATURES),
        "device": _existing(feature_columns, DEVICE_FEATURES),
        "http": _existing(feature_columns, HTTP_FEATURES),
    }
    missing_groups = [name for name, columns in groups.items() if not columns]
    if missing_groups:
        raise ValueError(f"cannot train domain IF; no feature columns for groups: {missing_groups}")

    domain_if = DomainIsolationForest(contamination=contamination)
    domain_if.fit(
        df[groups["logon"]].to_numpy(dtype=np.float32),
        df[groups["file"]].to_numpy(dtype=np.float32),
        df[groups["device"]].to_numpy(dtype=np.float32),
        df[groups["http"]].to_numpy(dtype=np.float32),
    )
    return domain_if


def _build_sequences(df: pd.DataFrame, feature_columns: list[str], sequence_length: int):
    X_rows = []
    y_rows = []
    for _, user_df in df.groupby("user", sort=False):
        user_df = user_df.sort_values("date")
        values = user_df[feature_columns].to_numpy(dtype=np.float32)
        if len(values) < sequence_length + 1:
            continue
        for start in range(0, len(values) - sequence_length):
            end = start + sequence_length
            X_rows.append(values[start:end])
            y_rows.append(values[end])
    if not X_rows:
        raise ValueError(
            f"not enough per-user history to train RVFL; need at least {sequence_length + 1} days for one user"
        )
    return np.asarray(X_rows, dtype=np.float32), np.asarray(y_rows, dtype=np.float32)


def _train_rvfl(X: np.ndarray, y: np.ndarray, hidden_size: int, num_layers: int, ridge_alpha: float):
    from src.red_revfl_orchestrator import RedRVFLOrchestrator

    import torch

    model = RedRVFLOrchestrator(
        input_features=X.shape[2],
        hidden_size=hidden_size,
        num_layers=num_layers,
    )
    matrices = model.extract_features(torch.tensor(X, dtype=torch.float32))
    ridge_models = []
    for matrix in matrices:
        ridge = Ridge(alpha=ridge_alpha, solver="cholesky")
        ridge.fit(matrix, y)
        ridge_models.append(ridge)
    return ridge_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Train model-inference artifacts from an enriched daily feature CSV.")
    parser.add_argument("--features-csv", required=True, help="Path to if_enriched_features.csv or equivalent.")
    parser.add_argument("--model-inference-dir", default="model-inference", help="Path to model-inference directory.")
    parser.add_argument("--sequence-length", type=int, default=15)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=3)
    parser.add_argument("--ridge-alpha", type=float, default=0.01)
    parser.add_argument("--contamination", type=float, default=0.05)
    args = parser.parse_args()

    root = _repo_root()
    model_inference_dir = (root / args.model_inference_dir).resolve()
    models_dir = model_inference_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    _add_model_path(model_inference_dir)

    csv_path = Path(args.features_csv).expanduser()
    if not csv_path.is_absolute():
        csv_path = (Path.cwd() / csv_path).resolve()

    raw_df = pd.read_csv(csv_path, nrows=5)
    feature_columns = _load_feature_columns(models_dir, raw_df)
    df = _prepare_dataframe(csv_path, feature_columns)

    domain_if = _train_domain_if(df, feature_columns, args.contamination)
    joblib.dump(domain_if, models_dir / "domain_isolation_forest.pkl")

    scaler = MinMaxScaler()
    scaled = df.copy()
    scaled[feature_columns] = scaler.fit_transform(df[feature_columns])
    joblib.dump(scaler, models_dir / "feature_scaler.pkl")

    X, y = _build_sequences(scaled, feature_columns, args.sequence_length)
    ridge_models = _train_rvfl(X, y, args.hidden_size, args.num_layers, args.ridge_alpha)
    joblib.dump(ridge_models, models_dir / "ridge_models.pkl")

    (models_dir / "feature_columns.json").write_text(json.dumps(feature_columns, indent=4), encoding="utf-8")
    (models_dir / "rvfl_metadata.json").write_text(
        json.dumps(
            {
                "input_features": len(feature_columns),
                "hidden_size": args.hidden_size,
                "num_layers": args.num_layers,
                "sequence_length": args.sequence_length,
            },
            indent=4,
        ),
        encoding="utf-8",
    )

    print(f"Saved model artifacts to: {models_dir}")
    print(f"Rows: {len(df)}")
    print(f"Features: {len(feature_columns)}")
    print(f"RVFL sequences: {len(X)}")


if __name__ == "__main__":
    main()
