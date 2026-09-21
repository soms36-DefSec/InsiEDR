from __future__ import annotations

from typing import Any, Dict

from server.config import config
from server.detectors.base import Detector


class ZScoreDetector(Detector):
    def __init__(self, sensitivity_multiplier: float = 1.0):
        self.sensitivity_multiplier = sensitivity_multiplier
        self.threshold = config.zscore_calibration_threshold * self.sensitivity_multiplier

    @property
    def name(self) -> str:
        return "zscore"

    def detect(self, payload_id: str, agent_id: str, username: str, features: Dict[str, float], baseline: Any, storage: Any = None) -> Dict[str, Any]:
        result = {
            "detector_name": self.name,
            "score": 0.0,
            "confidence": 0.0,
            "is_anomaly": False,
            "feature_contributions": {},
            "reason": "Normal feature distribution."
        }

        if not baseline:
            result["reason"] = "No baseline available."
            return result
            
        confidence = min(baseline.sample_count / 14.0, 1.0) if baseline.sample_count > 0 else 0.1
        result["confidence"] = confidence

        max_z = 0.0
        top_feature = ""
        
        for feature_name, current_val in features.items():
            # Skip non-numeric or boolean-like features, or very small categorical ones
            if feature_name.endswith("_status") or feature_name.endswith("_flag"):
                continue
                
            mean = baseline.feature_means.get(feature_name, 0.0)
            std = max(baseline.feature_stds.get(feature_name, 10.0), 10.0, abs(mean) * 0.25)
            
            z = (current_val - mean) / std
            
            # Directional Z-Score: We only care about UPWARD spikes for risk scoring.
            # A massive drop to 0 (AFK anomaly) results in a negative Z-score and is safely ignored.
            if z > self.threshold:
                result["feature_contributions"][feature_name] = z
                if z > max_z:
                    max_z = z
                    top_feature = feature_name
                    
        if max_z > self.threshold:
            result["is_anomaly"] = True
            result["score"] = min(max_z * 5.0, 100.0)
            result["reason"] = f"Significant statistical spike in feature {top_feature} (Z-score: {max_z:.2f})."
            
        return result
