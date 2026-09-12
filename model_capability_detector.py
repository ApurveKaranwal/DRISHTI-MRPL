"""DRISHTI-MRPL Model Capability Detector.

Answers: "What does this model appear capable of?"

Prediction, never a decision. Every output here is a *suggestion* meant to
pre-fill a confirmation UI — model_router.register_model() is only ever
called after a human confirms (see model_intake.py).

Signal priority (highest confidence first):
  1. Ollama /api/show metadata: `details.families`, `model_info`
     (architecture, vision projector presence), `template` (image slots).
  2. Model name heuristics (e.g. "vl", "coder", "r1") — used only when
     metadata is unavailable or ambiguous, and always marked lower confidence.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import requests

logger = logging.getLogger("MRPL.ModelCapabilityDetector")

Confidence = Literal["high", "low", "none"]

# Capabilities we know how to predict, and the roles they map to.
CAPABILITY_ROLE_MAP: dict[str, list[str]] = {
    "vision": ["vision"],
    "code": ["code"],
    "reasoning": ["reasoning", "supervisor", "general"],
    "text": ["general"],
}

# Name-fragment heuristics, used only as a fallback signal.
_NAME_PATTERNS: dict[str, list[str]] = {
    "vision": ["vl", "vision", "llava", "moondream", "bakllava"],
    "code": ["coder", "code", "codellama", "starcoder"],
    "reasoning": ["r1", "reason", "think", "o1"],
}

# Architecture/family strings from Ollama's `details.families` /
# `model_info` that indicate a vision-capable (multimodal) model.
_VISION_FAMILY_HINTS = ["clip", "vision", "mllama", "llava", "vl"]


@dataclass
class CapabilityPrediction:
    model_id: str
    capability_confidence: dict[str, Confidence] = field(default_factory=dict)
    suggested_roles: list[str] = field(default_factory=list)
    parameter_size: str | None = None
    quantization: str | None = None
    signals_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # capabilities the UI should render as confidently present (✓)
        confirmed = [c for c, conf in self.capability_confidence.items() if conf == "high"]
        # capabilities worth showing as "?" (uncertain, user should decide)
        uncertain = [c for c, conf in self.capability_confidence.items() if conf == "low"]
        return {
            "model_id": self.model_id,
            "capabilities": confirmed,
            "uncertain_capabilities": uncertain,
            "capability_confidence": self.capability_confidence,
            "suggested_roles": self.suggested_roles,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
            "signals_used": self.signals_used,
        }


def _query_ollama_show(model_id: str, timeout: float = 4.0) -> dict[str, Any] | None:
    """Calls Ollama's /api/show for model metadata. Returns None on any failure."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        resp = requests.post(f"{ollama_url}/api/show", json={"name": model_id}, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"/api/show for '{model_id}' returned {resp.status_code}.")
    except Exception as err:
        logger.warning(f"/api/show for '{model_id}' failed: {err}")
    return None


def _name_hints(model_id: str) -> dict[str, Confidence]:
    """Low-confidence signal derived purely from the model's name."""
    name = model_id.lower()
    hints: dict[str, Confidence] = {}
    for capability, patterns in _NAME_PATTERNS.items():
        if any(re.search(rf"(^|[-_:]){p}([-_:0-9.]|$)", name) for p in patterns):
            hints[capability] = "low"
    return hints


def _metadata_hints(show_data: dict[str, Any]) -> tuple[dict[str, Confidence], list[str]]:
    """High-confidence signals derived from Ollama /api/show metadata."""
    hints: dict[str, Confidence] = {}
    signals: list[str] = []

    details = show_data.get("details", {}) or {}
    families = [f.lower() for f in (details.get("families") or [])]
    family = str(details.get("family", "")).lower()
    model_info = show_data.get("model_info", {}) or {}

    all_family_strings = families + [family] + [str(k).lower() for k in model_info.keys()]

    if any(hint in fam for fam in all_family_strings for hint in _VISION_FAMILY_HINTS):
        hints["vision"] = "high"
        signals.append("vision projector/family detected in model metadata")

    template = str(show_data.get("template", "")).lower()
    if "image" in template or "<image" in template or "{{ .Images" in show_data.get("template", ""):
        hints["vision"] = "high"
        signals.append("template accepts image slots")

    # Any successfully-loaded model can produce text.
    if show_data:
        hints.setdefault("text", "high")
        signals.append("model loaded successfully via Ollama")

    return hints, signals


def detect_capabilities(model_id: str) -> CapabilityPrediction:
    """
    Builds a capability/role prediction for `model_id`.

    Always returns a prediction (falls back to name heuristics only, marked
    low-confidence, if Ollama metadata can't be fetched) — this function
    never raises for an unreachable Ollama instance.
    """
    prediction = CapabilityPrediction(model_id=model_id)
    show_data = _query_ollama_show(model_id)

    combined: dict[str, Confidence] = {}

    if show_data:
        meta_hints, signals = _metadata_hints(show_data)
        combined.update(meta_hints)
        prediction.signals_used.extend(signals)

        details = show_data.get("details", {}) or {}
        prediction.parameter_size = details.get("parameter_size")
        prediction.quantization = details.get("quantization_level")
    else:
        prediction.signals_used.append("Ollama /api/show unavailable — using name heuristics only")

    # Name heuristics fill in gaps but never downgrade a high-confidence
    # metadata signal.
    for capability, conf in _name_hints(model_id).items():
        combined.setdefault(capability, conf)
        if conf == "low":
            prediction.signals_used.append(f"name pattern suggests '{capability}'")

    # Anything with no positive signal at all is an explicit "none" (✗),
    # not just absent, so the UI can render it.
    for capability in CAPABILITY_ROLE_MAP:
        combined.setdefault(capability, "none")

    prediction.capability_confidence = combined

    # Role suggestion: only from capabilities we're at least "low" confident
    # about, ranked so vision/code (narrow, high-signal) win over generic
    # reasoning/general roles when both are present.
    roles: list[str] = []
    for capability in ("vision", "code", "reasoning", "text"):
        if combined.get(capability) in ("high", "low"):
            for role in CAPABILITY_ROLE_MAP[capability]:
                if role not in roles:
                    roles.append(role)

    # A model predicted as vision or code shouldn't also default into
    # "general" — that muddies the router. Only text/reasoning models get
    # the general/supervisor suggestions.
    if "vision" in roles or "code" in roles:
        roles = [r for r in roles if r not in ("general", "supervisor")] or roles[:1]

    prediction.suggested_roles = roles or ["general"]
    return prediction
