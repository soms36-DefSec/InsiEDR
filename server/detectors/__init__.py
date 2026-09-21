"""
server/detectors/__init__.py
----------------------------
Package exports for InsiEDR Threat Detector Plugins.
"""
from server.detectors.base import Detector, BaseDetector
from server.detectors.registry import detector_registry, register_detector

__all__ = [
    "Detector",
    "BaseDetector",
    "detector_registry",
    "register_detector",
]
