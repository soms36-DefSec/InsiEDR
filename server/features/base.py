"""
server/features/base.py
-----------------------
Abstract Base Class for all InsiEDR Feature Extractor Plugins.

Architecture & Extension Guide:
===============================
Feature extractors parse incoming telemetry payloads from various collectors
(Windows Event Logs, file integrity monitors, network sockets, USB device monitors)
and output normalized numerical metrics for the ML inference pipeline.

Adding a New Feature Extractor:
-------------------------------
1. Inherit from `BaseFeatureExtractor`.
2. Implement `name`, `expected_features`, and `extract(payload)`.
3. Register using `@register_feature_extractor` in `server/features/registry.py`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseFeatureExtractor(ABC):
    """Contract for modular telemetry feature extractors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this feature extractor plugin."""
        pass

    @property
    def expected_features(self) -> List[str]:
        """List of feature column names emitted by this extractor."""
        return []

    @property
    def is_enabled(self) -> bool:
        """Dynamic toggle. Override to conditionally disable extractor."""
        return True

    @abstractmethod
    def extract(self, payload: Dict[str, Any]) -> Dict[str, float]:
        """Extract and normalize numerical metrics from the decrypted agent payload.

        Parameters:
            payload: Full decrypted telemetry payload containing collector results.

        Returns:
            Dict[str, float] mapping feature names to their extracted float values.
        """
        pass
