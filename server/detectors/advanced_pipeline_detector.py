"""
AdvancedPipelineDetector — Thin adapter that wires the G-model's InferenceEngine
into the server's Phase 2 Detector pipeline.

HOW IT WORKS (no code is copied or moved):
  1. At init, InsiEDR-G-model-latest-dataset/src/ is added to sys.path.
  2. InferenceEngine is imported DIRECTLY from that directory.
  3. All .pkl artifacts are loaded from InsiEDR-G-model-latest-dataset/latest_data/models/
  4. On each detect() call, the full 3-stage G-model pipeline runs:
       Domain IF → XGBoost 6-class → RedRVFL sequence drift
  5. The result is translated into the server's standard detector dict format.

Nothing in InsiEDR-G-model-latest-dataset is touched, copied, or moved.
"""

from __future__ import annotations

import os
import sys
import logging
import datetime
from pathlib import Path
from typing import Any, Dict

from server.detectors.base import Detector
from server.config import config

logger = logging.getLogger("advanced_pipeline_detector")

# Minimum days of RVFL history required before RedRVFL scoring activates.
# Below this threshold, the detector gracefully falls back to IF+XGBoost score only.
_MIN_RVFL_HISTORY_DAYS = 8


def _ensure_g_model_on_path() -> None:
    g_model_root = str(Path(config.model_inference_dir).resolve())
    g_model_src = str(Path(config.model_inference_dir).resolve() / "src")
    if g_model_root not in sys.path:
        sys.path.insert(0, g_model_root)
    if g_model_src not in sys.path:
        sys.path.insert(0, g_model_src)

class AdvancedPipelineDetector(Detector):
    """
    Runs the full G-model 3-stage inference pipeline in-place:
      Stage 1 — 4x Domain Isolation Forests  → domain risk scores
      Stage 2 — XGBoost 6-class classifier   → scenario probabilities
      Stage 3 — RedRVFL 5-layer sequence     → temporal drift error → final score

    Replaces IsolationForestDetector and RandomForestDetector.
    All model code and artifacts are loaded from InsiEDR-G-model-latest-dataset
    without copying or moving anything.
    """

    @property
    def name(self) -> str:
        return "advanced_pipeline"

    def __init__(self) -> None:
        super().__init__()
        self._engine = None
        self._load_error: str | None = None
        self._try_load_engine()

    def _try_load_engine(self) -> None:
        """
        Lazy-loads the G-model InferenceEngine from InsiEDR-G-model-latest-dataset/src/
        in-place. If loading fails (e.g. torch not installed), sets a degraded state.
        """
        try:
            _ensure_g_model_on_path()
            # Import InferenceEngine directly from the G-model's src/server/inference.py
            # This is NOT a copy — Python is importing from the G-model directory on-disk.
            from src.server.inference import InferenceEngine  # type: ignore[import]

            models_dir = str(Path(config.g_model_models_dir).resolve())
            logger.info(f"[AdvancedPipeline] Loading G-model artifacts from: {models_dir}")
            self._engine = InferenceEngine(models_dir=models_dir)
            logger.info("[AdvancedPipeline] G-model InferenceEngine loaded successfully.")
        except Exception as exc:
            self._load_error = str(exc)
            logger.error(f"[AdvancedPipeline] Failed to load G-model: {exc}")

    def _build_daily_sequence(self, username: str, features: Dict[str, float], storage: Any, agent_id: str | None = None) -> list[dict]:
        """
        Builds the daily_sequence list required by InferenceEngine.predict_user_risk().

        Fetches up to 7 previous days of stored daily features from the DB,
        appends today's live features as the latest entry. This is how the
        G-model's 7-day temporal window is reconstructed in real-time.
        """
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        sequence = []

        # Pull historical daily feature snapshots from storage (newest first)
        history_loader = getattr(storage, "list_daily_feature_vectors", None)
        if callable(history_loader):
            try:
                rows = history_loader(username=username, hostname=agent_id, limit=_MIN_RVFL_HISTORY_DAYS)
                for row in reversed(rows):  # oldest → newest
                    day_features = row.get("features") or {}
                    if day_features:
                        # Zero-pad any missing historical features using today's comprehensive feature list
                        padded_features = {k: 0.0 for k in features.keys()}
                        padded_features.update({k: float(v or 0.0) for k, v in day_features.items()})
                        sequence.append({
                            "date": str(row.get("date", "")),
                            "features": padded_features,
                        })
            except Exception as exc:
                logger.warning(f"[AdvancedPipeline] Could not load history for {username}: {exc}")

        # Append today's live features
        sequence.append({
            "date": today,
            "features": {k: float(v) for k, v in features.items()},
        })
        return sequence

    def detect(
        self,
        payload_id: str,
        agent_id: str,
        username: str,
        features: Dict[str, float],
        baseline: Any,
        storage: Any = None,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {
            "detector_name": self.name,
            "score": 0.0,
            "confidence": 0.0,
            "is_anomaly": False,
            "feature_contributions": {},
            "reason": "G-model not loaded.",
        }

        # --- Confidence based on how long this user has been observed ---
        confidence = min(baseline.sample_count / 14.0, 1.0) if baseline and baseline.sample_count > 0 else 0.3
        result["confidence"] = confidence

        if self._engine is None:
            result["reason"] = f"G-model unavailable: {self._load_error}"
            result["confidence"] = 0.0
            return result

        try:
            # Build the daily sequence from DB history + today's live features
            daily_sequence = self._build_daily_sequence(username, features, storage, agent_id) if storage else [
                {"date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
                 "features": {k: float(v) for k, v in features.items()}}
            ]

            if len(daily_sequence) < _MIN_RVFL_HISTORY_DAYS:
                # --- Graceful degradation: not enough history for RedRVFL ---
                # Fall back to IF-only single-day scoring via predict_current_risk()
                if_result = self._engine.predict_current_risk({"features": features})
                overall = if_result.get("overall_score", 0.0)
                risk_score = overall * 100.0
                result.update({
                    "score": round(risk_score, 4),
                    "confidence": confidence * 0.5,   # lower confidence: no temporal context yet
                    "is_anomaly": if_result.get("risk_level") in ("HIGH", "MEDIUM"),
                    "feature_contributions": {
                        "domain_scores": if_result.get("domain_scores", {}),
                        "overall_risk": overall,
                        "mode": "if_only_fallback",
                        "days_in_sequence": len(daily_sequence),
                        "days_needed_for_rvfl": _MIN_RVFL_HISTORY_DAYS,
                    },
                    "reason": (
                        f"G-Model [IF only, building history {len(daily_sequence)}/{_MIN_RVFL_HISTORY_DAYS} days]: "
                        f"Risk={if_result.get('risk_level')} ({overall:.4f})"
                    ),
                })
                return result

            # --- Full 3-stage pipeline: IF → XGBoost → RedRVFL ---
            payload = {
                "payload_id": payload_id,
                "username": username,
                "hostname": agent_id,   # hostname used as agent identifier
                "daily_sequence": daily_sequence,
            }

            g_result = self._engine.predict_user_risk(payload)

            risk_score = float(g_result.get("risk_score", 0.0))
            risk_level = str(g_result.get("risk_level", "LOW")).upper()
            rvfl_error = float(
                g_result.get("detectors", {}).get("red_rvfl", {}).get("rvfl_error", 0.0)
            )
            xgb_result = g_result.get("detectors", {}).get("xgboost", {})
            if_result_full = g_result.get("detectors", {}).get("isolation_forest", {})
            predicted_scenario = xgb_result.get("scenario", "unknown")
            scenario_conf = round(xgb_result.get("confidence", 0.0), 4)

            result.update({
                "score": round(risk_score, 4),
                "confidence": confidence,
                "is_anomaly": risk_level in ("HIGH", "MEDIUM"),
                "feature_contributions": {
                    "domain_scores": if_result_full.get("domain_scores", {}),
                    "overall_risk": if_result_full.get("overall_score", 0.0),
                    "predicted_scenario": predicted_scenario,
                    "scenario_confidence": scenario_conf,
                    "scenario_probs": {k: v for k, v in xgb_result.items() if k.endswith("_prob")},
                    "rvfl_error": rvfl_error,
                    "days_in_sequence": len(daily_sequence),
                    "mode": "full_pipeline",
                },
                "reason": (
                    f"G-Model: scenario={predicted_scenario} (conf={scenario_conf:.2f}), "
                    f"RVFL drift={rvfl_error:.5f}, risk={risk_level} ({risk_score:.1f}/100)"
                ),
            })

        except Exception as exc:
            logger.error(f"[AdvancedPipeline] Inference failed for {username}: {exc}")
            result["reason"] = f"G-model inference error: {exc}"
            result["confidence"] = 0.0

        return result
