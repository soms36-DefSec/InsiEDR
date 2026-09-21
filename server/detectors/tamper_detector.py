from typing import Any, Dict

from server.detectors.base import Detector


class TamperDetector(Detector):
    """
    Detects forceful agent termination or tampering attempts.
    The EndpointAgent fires a synthetic payload with 'manual_agent_stop_flag'
    when it intercepts an OS-level forced termination signal (CTRL+C, SIGTERM, Task Manager).
    """

    @property
    def name(self) -> str:
        return "tamper_detector"

    def detect(
        self,
        payload_id: str,
        agent_id: str,
        username: str,
        features: Dict[str, float],
        baseline: Any,
        storage: Any = None,
    ) -> Dict[str, Any]:
        
        # Check for explicit tamper flags sent by the agent lifecycle collector
        tamper_flag = features.get("manual_agent_stop_flag")
        
        if tamper_flag:
            return {
                "detector_name": self.name,
                "score": 100.0,
                "confidence": 1.0,
                "is_anomaly": True,
                "feature_contributions": {"manual_agent_stop_flag": tamper_flag},
                "reason": "CRITICAL: Endpoint Agent was forcefully terminated by the user (Tamper Alert)."
            }

        return {
            "detector_name": self.name,
            "score": 0.0,
            "confidence": 1.0,
            "is_anomaly": False,
            "feature_contributions": {},
            "reason": "No tampering detected."
        }
