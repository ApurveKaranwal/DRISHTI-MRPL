"""DRISHTI-MRPL Sovereign Model Router, Discovery, and Intake Subsystem."""

from __future__ import annotations

import sys
from pathlib import Path

_MODELS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _MODELS_DIR.parent
_AGENTS_DIR = _ROOT_DIR / "agents"

for _p in [str(_ROOT_DIR), str(_MODELS_DIR), str(_AGENTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from .model_router import ModelRouter, get_model_router
from .model_discovery import ModelDiscovery, get_model_discovery
from .model_capability_detector import detect_capabilities, CapabilityPrediction
from .model_intake import scan_for_new_models, confirm_model

__all__ = [
    "ModelRouter",
    "get_model_router",
    "ModelDiscovery",
    "get_model_discovery",
    "detect_capabilities",
    "CapabilityPrediction",
    "scan_for_new_models",
    "confirm_model",
]
