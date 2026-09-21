from __future__ import annotations

from typing import Any, Dict

from server.config import config
from server.detectors.base import Detector


class AuthBurstDetector(Detector):
    @property
    def name(self) -> str:
        return "auth_burst"

    def detect(self, payload_id: str, agent_id: str, username: str, features: Dict[str, float], baseline: Any, storage: Any = None) -> Dict[str, Any]:
        result = {
            "detector_name": self.name,
            "score": 0.0,
            "confidence": 0.0,
            "is_anomaly": False,
            "feature_contributions": {},
            "reason": "Normal authentication activity."
        }

        # If no baseline is available, we cannot confidently detect a burst.
        if not baseline:
            result["reason"] = "No baseline available."
            return result

        # Cold start confidence derived from baseline sample count
        confidence = min(baseline.sample_count / 14.0, 1.0) if baseline.sample_count > 0 else 0.1
        result["confidence"] = confidence

        # Extract actual short-term EDR features instead of generic logon_count
        events_per_minute = features.get("edr_auth_events_per_minute_window", 0.0)
        failed_ratio = features.get("edr_failed_auth_ratio_window", 0.0)

        baseline_rate_mean = baseline.feature_means.get("edr_auth_events_per_minute_window", 0.0)
        baseline_rate_std = max(baseline.feature_stds.get("edr_auth_events_per_minute_window", 10.0), 10.0)

        baseline_ratio_mean = baseline.feature_means.get("edr_failed_auth_ratio_window", 0.0)
        baseline_ratio_std = max(baseline.feature_stds.get("edr_failed_auth_ratio_window", 0.30), 0.30)

        # Calculate Z-Scores for bursts using the specific EDR telemetry
        rate_z = (events_per_minute - baseline_rate_mean) / baseline_rate_std
        ratio_z = (failed_ratio - baseline_ratio_mean) / baseline_ratio_std

        calibrated_threshold = max(config.zscore_calibration_threshold, 8.0)

        # Require genuine high volume + high deviation (e.g. active brute-force password spraying)
        is_rate_burst = (rate_z > calibrated_threshold and events_per_minute >= 50.0)
        is_fail_burst = (ratio_z > calibrated_threshold and failed_ratio >= 0.70)

        if is_rate_burst or is_fail_burst:
            result["is_anomaly"] = True

            # Score is scaled smoothly to prevent artificial spikes
            edr_auth_burst_score = min(max(rate_z, ratio_z) * 5.0, 100.0)
            result["score"] = edr_auth_burst_score

            result["feature_contributions"] = {
                "edr_auth_events_per_minute_window": rate_z,
                "edr_failed_auth_ratio_window": ratio_z
            }

            if is_fail_burst and is_rate_burst:
                result["reason"] = f"Critical brute-force authentication attack detected (Events: {events_per_minute:.0f}/min, Failed: {failed_ratio*100:.0f}%)."
            elif is_fail_burst:
                result["reason"] = f"Massive failed authentication spike detected (Failed Ratio: {failed_ratio*100:.0f}%)."
            else:
                result["reason"] = f"Extreme authentication velocity detected ({events_per_minute:.0f} events/min)."

        return result
