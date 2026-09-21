from __future__ import annotations

"""
server/detectors/base.py
-------------------------
Abstract Base Class for all InsiEDR Threat Detectors.

Architecture & Extension Guide:
===============================
Every threat detector plugin in InsiEDR implements the `Detector` contract.
Detectors are evaluated sequentially or concurrently by the `DetectorRegistry`
during telemetry processing in `ModelBridge`.

Output Contract:
----------------
Each detector's `detect()` method must return a dictionary conforming to:
{
    "detector_name": str,                  # Unique identifier of the detector
    "score": float,                        # Anomaly/severity score (0.0 to 100.0)
    "confidence": float,                   # Confidence in this detection (0.0 to 1.0)
    "is_anomaly": bool,                    # True if behavior crosses the anomalous threshold
    "feature_contributions": dict,         # Map of feature names to contribution weights/Z-scores
    "reason": str,                         # Human-readable analyst explanation for the SOC dashboard
}
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class Detector(ABC):
    """Abstract base class for all InsiEDR threat detectors.
    
    Subclasses must define `name` and implement `detect()`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this detector plugin (e.g., 'tamper_detector', 'zscore')."""
        pass

    @property
    def version(self) -> str:
        """Semantic version of this detector logic/model."""
        return "1.0.0"

    @property
    def is_enabled(self) -> bool:
        """Dynamic toggle. Override to disable detector under specific configurations."""
        return True

    @abstractmethod
    def detect(
        self,
        payload_id: str,
        agent_id: str,
        username: str,
        features: Dict[str, float],
        baseline: Any,
        storage: Any = None,
    ) -> Dict[str, Any]:
        """Evaluate normalized features against the user/entity baseline.

        Parameters:
            payload_id: Unique identifier of the telemetry ingestion event.
            agent_id: Windows endpoint agent identifier.
            username: Target user being evaluated.
            features: Dictionary of normalized numerical features extracted from the payload.
            baseline: UserBaseline snapshot (historical means, stds, sample count).
            storage: Optional reference to PostgresStorage for querying historical time series.

        Returns:
            Dict conforming to the standard detector result contract.
        """
        pass

    @staticmethod
    def format_result(
        detector_name: str,
        score: float = 0.0,
        confidence: float = 1.0,
        is_anomaly: bool = False,
        feature_contributions: Dict[str, Any] | None = None,
        reason: str = "Normal behavior.",
    ) -> Dict[str, Any]:
        """Convenience helper to ensure uniform result structure across all detector plugins."""
        return {
            "detector_name": detector_name,
            "score": max(0.0, min(100.0, float(score))),
            "confidence": max(0.0, min(1.0, float(confidence))),
            "is_anomaly": bool(is_anomaly),
            "feature_contributions": feature_contributions or {},
            "reason": reason,
        }


# Backward compatibility alias
BaseDetector = Detector
