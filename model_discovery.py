"""DRISHTI-MRPL Model Discovery.

Answers one question: "What models are installed in Ollama that the
registry doesn't know about yet?"

This module never decides capabilities or roles, and never writes to the
registry. It only detects and tracks review state (pending / dismissed) so
the same new model isn't re-prompted every scan. Confirmation and writing
belong to model_router.register_model(), called after the user approves
a suggestion from model_capability_detector.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from model_router import get_model_router

logger = logging.getLogger("MRPL.ModelDiscovery")

STATE_PATH = Path(__file__).resolve().parent / "model_discovery_state.json"


class ModelDiscovery:
    """Tracks which installed-but-unregistered models still need user review."""

    def __init__(self, state_file: Path | str | None = None) -> None:
        self.state_file = Path(state_file) if state_file else STATE_PATH
        self._lock = threading.RLock()
        self._state: dict[str, Any] = self._load_state()

    # -------------------------------------------------------------------
    # State IO (tracks dismissed models so we don't nag the user forever)
    # -------------------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.is_file():
            return {"dismissed": []}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("dismissed", [])
                return data
        except Exception as err:
            logger.warning(f"Could not read discovery state, resetting: {err}")
            return {"dismissed": []}

    def _save_state(self) -> None:
        try:
            temp_path = self.state_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
            temp_path.replace(self.state_file)
        except Exception as err:
            logger.error(f"Failed to persist discovery state: {err}")

    # -------------------------------------------------------------------
    # Detection
    # -------------------------------------------------------------------

    def find_unregistered_models(self, force_refresh: bool = True) -> list[str]:
        """
        Returns installed Ollama model IDs that are not in the registry and
        have not been dismissed by the user.
        """
        with self._lock:
            router = get_model_router()
            installed = router.get_installed_ollama_models(force_refresh=force_refresh)
            registered_dict = router.get_full_registry_status().get("models", {})
            registered_keys = set(registered_dict.keys())
            dismissed = set(self._state.get("dismissed", []))

            registered_lower = {k.lower() for k in registered_keys}
            registered_bases = {k.split(":")[0].lower() for k in registered_keys}
            dismissed_lower = {k.lower() for k in dismissed}

            unregistered = []
            for m in installed:
                m_lower = m.lower()
                if m_lower in registered_lower or m in registered_keys:
                    continue
                if m_lower in dismissed_lower or m in dismissed:
                    continue
                # If model is tag :latest, check if base model is already registered
                base = m_lower.split(":")[0]
                tag = m_lower.split(":")[1] if ":" in m_lower else ""
                if tag == "latest" and base in registered_bases:
                    continue
                unregistered.append(m)

            return sorted(unregistered)

    def dismiss(self, model_id: str) -> None:
        """User chose 'not now' / 'ignore' for a detected model."""
        with self._lock:
            dismissed = self._state.get("dismissed", [])
            if not any(m.lower() == model_id.lower() for m in dismissed):
                dismissed.append(model_id)
                self._state["dismissed"] = dismissed
                self._save_state()
                logger.info(f"Model '{model_id}' dismissed from discovery prompts.")

    def clear_dismissed(self, model_id: str | None = None) -> None:
        """
        Un-dismiss a model (or all models) so it can be picked up again on
        the next scan. Useful if the user wants to reconsider a model they
        previously skipped.
        """
        with self._lock:
            if model_id is None:
                self._state["dismissed"] = []
            else:
                target_lower = model_id.lower()
                self._state["dismissed"] = [
                    m for m in self._state.get("dismissed", []) if m.lower() != target_lower
                ]
            self._save_state()


_discovery_instance: ModelDiscovery | None = None
_discovery_lock = threading.Lock()


def get_model_discovery() -> ModelDiscovery:
    """Convenience accessor for a process-wide ModelDiscovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        with _discovery_lock:
            if _discovery_instance is None:
                _discovery_instance = ModelDiscovery()
    return _discovery_instance
