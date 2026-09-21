from __future__ import annotations

from typing import Any, Dict
from server.features.base import BaseFeatureExtractor


class LanlEDRExtractor(BaseFeatureExtractor):
    """
    Extracts short-term EDR authentication metrics from raw telemetry payloads.
    Ensures safe extraction and handles missingness explicitly without artificial zero-fabrication.
    """

    @property
    def name(self) -> str:
        return "lanl_edr"
    
    EXPECTED_FEATURES = [
        "edr_auth_event_count_window",
        "edr_failed_auth_ratio_window",
        "edr_auth_events_per_minute_window",
        "edr_failed_auth_events_per_minute_window",
        "edr_unique_logon_type_count_window",
    ]

    def extract(self, payload: Dict[str, Any]) -> Dict[str, float]:
        features = {}
        
        # Locate the short_term_edr_feature collector payload
        edr_payload = None
        for collector in payload.get("collectors", []):
            if collector.get("collector") == "short-Term_EDR_Feature" and collector.get("status") == "success":
                edr_payload = collector.get("payload", {})
                break
                
        if not edr_payload:
            # Collector failed or missing: we DO NOT fabricate values (handled by BaselineEngine tracking missingness)
            # We return empty dict so they don't get populated with 0.0s artificially
            return features
            
        for feature_name in self.EXPECTED_FEATURES:
            if feature_name in edr_payload:
                try:
                    features[feature_name] = float(edr_payload[feature_name])
                except (ValueError, TypeError):
                    pass
                    
        return features
