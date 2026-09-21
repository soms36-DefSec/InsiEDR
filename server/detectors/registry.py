"""
server/detectors/registry.py
----------------------------
Central Registry for InsiEDR Threat Detector Plugins.

Architecture & Extension Guide:
===============================
This registry decouples detector implementation from the inference execution loop.
Any new detector plugin simply inherits from `server.detectors.base.Detector`
and registers itself via `detector_registry.register(detector_instance)` or
the `@register_detector` decorator.

Usage Example:
--------------
    from server.detectors.base import Detector
    from server.detectors.registry import register_detector

    @register_detector
    class MyCustomLLMDetector(Detector):
        @property
        def name(self) -> str:
            return "custom_llm_detector"

        def detect(self, payload_id, agent_id, username, features, baseline, storage=None):
            return self.format_result(
                detector_name=self.name,
                score=85.0,
                is_anomaly=True,
                reason="Unusual shell invocation correlated with external IP."
            )
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type
from server.detectors.base import Detector

logger = logging.getLogger("insiedr.detectors.registry")


class DetectorRegistry:
    """Manages the lifecycle, discovery, and execution of threat detector plugins."""

    def __init__(self) -> None:
        self._detectors: Dict[str, Detector] = {}

    def register(self, detector: Detector | Type[Detector]) -> Detector:
        """Register a detector instance or class. If a class is provided, it is instantiated."""
        instance = detector() if isinstance(detector, type) else detector
        if not isinstance(instance, Detector):
            raise TypeError(f"Detector '{type(instance).__name__}' must inherit from Detector.")
        
        self._detectors[instance.name] = instance
        logger.info(f"Registered threat detector plugin: '{instance.name}' (v{instance.version})")
        return instance

    def unregister(self, name: str) -> Detector | None:
        """Remove a detector by name."""
        return self._detectors.pop(name, None)

    def get(self, name: str) -> Detector | None:
        """Get a registered detector by name."""
        return self._detectors.get(name)

    def get_all(self, enabled_only: bool = True) -> List[Detector]:
        """Return all registered detectors, optionally filtering to enabled ones only."""
        if not self._detectors:
            self.initialize_defaults()
        if enabled_only:
            return [d for d in self._detectors.values() if d.is_enabled]
        return list(self._detectors.values())

    def initialize_defaults(self) -> None:
        """Populate registry with standard built-in InsiEDR detectors."""
        self._detectors.clear()

        # 1. Tamper Detector: monitors forced agent termination / tampering signals
        try:
            from server.detectors.tamper_detector import TamperDetector
            self.register(TamperDetector())
        except Exception as exc:
            logger.warning(f"Could not load TamperDetector: {exc}")

        # 2. Authentication Burst Detector: brute-force / velocity anomalies
        try:
            from server.detectors.auth_burst_detector import AuthBurstDetector
            self.register(AuthBurstDetector())
        except Exception as exc:
            logger.warning(f"Could not load AuthBurstDetector: {exc}")

        # 3. Z-Score Detector: dynamic deviation from historical EMA baseline
        try:
            from server.detectors.zscore_detector import ZScoreDetector
            self.register(ZScoreDetector())
        except Exception as exc:
            logger.warning(f"Could not load ZScoreDetector: {exc}")

        # 4. Advanced Pipeline Detector: G-Model Domain IF + XGBoost + RedRVFL
        try:
            from server.detectors.advanced_pipeline_detector import AdvancedPipelineDetector
            self.register(AdvancedPipelineDetector())
        except Exception as exc:
            logger.warning(f"Could not load AdvancedPipelineDetector: {exc}")

        logger.info(f"DetectorRegistry initialized with {len(self._detectors)} default detectors.")

    def run_all(
        self,
        payload_id: str,
        agent_id: str,
        username: str,
        features: Dict[str, float],
        baseline: Any,
        storage: Any = None,
    ) -> List[Dict[str, Any]]:
        """Execute all active detectors sequentially and return their standardized outputs."""
        results: List[Dict[str, Any]] = []
        for detector in self.get_all(enabled_only=True):
            try:
                res = detector.detect(
                    payload_id=payload_id,
                    agent_id=agent_id,
                    username=username,
                    features=features,
                    baseline=baseline,
                    storage=storage,
                )
                results.append(res)
            except Exception as exc:
                logger.error(f"Detector '{detector.name}' failed during execution: {exc}", exc_info=True)
                results.append(
                    detector.format_result(
                        detector_name=detector.name,
                        score=0.0,
                        confidence=0.0,
                        is_anomaly=False,
                        reason=f"Detector execution error: {exc}",
                    )
                )
        return results


# Global singleton registry instance
detector_registry = DetectorRegistry()


def register_detector(cls: Type[Detector]) -> Type[Detector]:
    """Decorator to register a detector plugin class automatically."""
    detector_registry.register(cls)
    return cls
