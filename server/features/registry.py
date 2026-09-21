"""
server/features/registry.py
---------------------------
Central Registry for InsiEDR Feature Extractor Plugins.

Architecture & Extension Guide:
===============================
Extracts domain-specific features across diverse operating system telemetry collectors.
New telemetry collectors (e.g. Linux auditd, cloud audit logs, container events)
can register extractors dynamically without modifying the central `model_bridge.py`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Type
from server.features.base import BaseFeatureExtractor

logger = logging.getLogger("insiedr.features.registry")


class FeatureExtractorRegistry:
    """Manages the discovery, registration, and batch execution of feature extractors."""

    def __init__(self) -> None:
        self._extractors: Dict[str, BaseFeatureExtractor] = {}

    def register(self, extractor: BaseFeatureExtractor | Type[BaseFeatureExtractor]) -> BaseFeatureExtractor:
        """Register a feature extractor instance or class."""
        instance = extractor() if isinstance(extractor, type) else extractor
        if not isinstance(instance, BaseFeatureExtractor):
            raise TypeError(f"Extractor '{type(instance).__name__}' must inherit from BaseFeatureExtractor.")
        
        self._extractors[instance.name] = instance
        logger.info(f"Registered feature extractor plugin: '{instance.name}'")
        return instance

    def get_all(self, enabled_only: bool = True) -> List[BaseFeatureExtractor]:
        """Return all registered extractors, optionally filtering to enabled ones only."""
        if not self._extractors:
            self.initialize_defaults()
        if enabled_only:
            return [e for e in self._extractors.values() if e.is_enabled]
        return list(self._extractors.values())

    def initialize_defaults(self) -> None:
        """Populate registry with standard built-in feature extractors."""
        self._extractors.clear()
        try:
            from server.features.lanl_edr import LanlEDRExtractor
            self.register(LanlEDRExtractor())
        except Exception as exc:
            logger.warning(f"Could not load LanlEDRExtractor: {exc}")

        logger.info(f"FeatureExtractorRegistry initialized with {len(self._extractors)} extractors.")

    def extract_all(self, payload: Dict[str, Any]) -> Dict[str, float]:
        """Run all active extractors against the payload and merge extracted features."""
        combined_features: Dict[str, float] = {}
        for extractor in self.get_all(enabled_only=True):
            try:
                extracted = extractor.extract(payload)
                if isinstance(extracted, dict):
                    combined_features.update(extracted)
            except Exception as exc:
                logger.error(f"Feature extractor '{extractor.name}' failed: {exc}", exc_info=True)
        return combined_features


# Global singleton registry instance
feature_registry = FeatureExtractorRegistry()


def register_feature_extractor(cls: Type[BaseFeatureExtractor]) -> Type[BaseFeatureExtractor]:
    """Decorator to register a feature extractor plugin automatically."""
    feature_registry.register(cls)
    return cls
