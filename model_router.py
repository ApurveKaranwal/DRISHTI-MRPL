"""DRISHTI-MRPL Sovereign Model Router.

Manages dynamic model selection, role-to-model mapping, fallback routing,
and model registry persistence without changing deterministic worker pipelines.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("MRPL.ModelRouter")

REGISTRY_PATH = Path(__file__).resolve().parent / "model_registry.json"


class ModelRouter:
    """Thread-safe router for resolving active models by operational role."""

    _instance: ModelRouter | None = None
    _lock = threading.Lock()

    def __init__(self, registry_file: Path | str | None = None) -> None:
        self.registry_file = Path(registry_file) if registry_file else REGISTRY_PATH
        self._file_lock = threading.RLock()
        self._installed_cache: list[str] = []
        self._installed_cache_time: float = 0.0
        self._cache_ttl_seconds: float = 5.0  # cache Ollama tags for 5 seconds
        self._registry_data: dict[str, Any] = {}
        self.load_registry()

    @classmethod
    def get_instance(cls, registry_file: Path | str | None = None) -> ModelRouter:
        """Singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(registry_file)
        return cls._instance

    # -----------------------------------------------------------------------
    # Registry IO
    # -----------------------------------------------------------------------

    def load_registry(self) -> dict[str, Any]:
        """Reads registry data from disk with thread-safety."""
        with self._file_lock:
            if not self.registry_file.is_file():
                logger.warning(
                    f"Model registry file {self.registry_file} not found. Creating default."
                )
                self._registry_data = self._create_default_registry()
                self._save_registry_unlocked()
            else:
                try:
                    with open(self.registry_file, "r", encoding="utf-8") as f:
                        self._registry_data = json.load(f)
                except Exception as err:
                    logger.error(f"Error loading model registry: {err}. Falling back to default registry.")
                    if not self._registry_data:
                        self._registry_data = self._create_default_registry()
            return self._registry_data

    def _save_registry_unlocked(self) -> bool:
        try:
            temp_path = self.registry_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._registry_data, f, indent=2)
            temp_path.replace(self.registry_file)
            return True
        except Exception as err:
            logger.error(f"Failed to persist model registry: {err}")
            return False

    def save_registry(self) -> bool:
        """Flushes registry data to disk."""
        with self._file_lock:
            return self._save_registry_unlocked()

    def _create_default_registry(self) -> dict[str, Any]:
        return {
            "active_selection": {
                "supervisor": "qwen3:8b-finetuned",
                "general": "qwen3:8b-finetuned",
                "reasoning": "deepseek-r1:1.5b",
                "vision": "qwen3-vl:8b",
                "code": "qwen2.5:7b",
            },
            "models": {
                "qwen3:8b": {
                    "capabilities": ["text", "reasoning", "code"],
                    "roles": ["supervisor", "general", "reasoning", "code"],
                    "vram_estimate_gb": 4.8,
                    "context_window": 8192,
                    "temperature": 0.1,
                    "description": "Primary PSU supervisor for planning, memorandum drafting, process coding, and grounded synthesis.",
                },
                "qwen3:8b-finetuned": {
                    "capabilities": ["text", "reasoning", "code"],
                    "roles": ["supervisor", "general", "reasoning", "code"],
                    "vram_estimate_gb": 4.8,
                    "context_window": 40960,
                    "temperature": 0.1,
                    "description": "Locally fine-tuned PSU sovereign model for MRPL operations, planning, memorandum synthesis, and engineering code.",
                },
                "qwen3-vl:8b": {
                    "capabilities": ["text", "vision"],
                    "roles": ["vision"],
                    "vram_estimate_gb": 4.8,
                    "context_window": 4096,
                    "temperature": 0.0,
                    "description": "Multimodal visual inspection model for P&IDs and ultrasonic scans.",
                },
                "qwen2.5vl:7b": {
                    "capabilities": ["vision", "text"],
                    "roles": ["vision"],
                    "vram_estimate_gb": 4.0,
                    "context_window": 4096,
                    "temperature": 0.0,
                    "description": "High-efficiency multimodal vision model for P&IDs and equipment inspection.",
                },
                "qwen2.5:7b": {
                    "capabilities": ["text", "reasoning", "code"],
                    "roles": ["supervisor", "general", "code"],
                    "vram_estimate_gb": 4.5,
                    "context_window": 4096,
                    "temperature": 0.1,
                    "description": "Structured prose generator and Python code engine for PSU memorandum drafting and technical calculations.",
                },
                "deepseek-r1:1.5b": {
                    "capabilities": ["text", "reasoning"],
                    "roles": ["reasoning"],
                    "vram_estimate_gb": 1.5,
                    "context_window": 4096,
                    "temperature": 0.2,
                    "description": "Chain-of-thought model for root-cause analysis.",
                },
                "deepseek-r1:7b": {
                    "capabilities": ["text", "reasoning"],
                    "roles": ["general", "reasoning", "supervisor"],
                    "vram_estimate_gb": 4.0,
                    "context_window": 4096,
                    "temperature": 0.1,
                    "description": "7B parameter deep reasoning engine for complex troubleshooting and failure mode analyses.",
                },
            },
            "fallbacks": {
                "supervisor": "qwen3:8b",
                "general": "qwen3:8b",
                "reasoning": "deepseek-r1:1.5b",
                "vision": "qwen2.5vl:7b",
                "code": "qwen2.5:7b",
            },
        }

    # -----------------------------------------------------------------------
    # Ollama Detection / Health
    # -----------------------------------------------------------------------

    def get_installed_ollama_models(self, force_refresh: bool = False) -> list[str]:
        """Queries local Ollama /api/tags to list installed model names."""
        with self._file_lock:
            now = time.time()
            if not force_refresh and (now - self._installed_cache_time < self._cache_ttl_seconds):
                return list(self._installed_cache)

        ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        new_cache = []
        try:
            resp = requests.get(f"{ollama_url}/api/tags", timeout=1.0)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                new_cache = [m for m in models if m]
        except Exception:
            new_cache = []

        with self._file_lock:
            self._installed_cache = new_cache
            self._installed_cache_time = time.time()
            return list(self._installed_cache)

    def is_model_installed(self, model_id: str) -> bool:
        """Checks if a target model is installed in local Ollama."""
        installed = self.get_installed_ollama_models()
        if not installed:
            return False
        if model_id in installed:
            return True
        model_id_lower = model_id.lower()
        if any(m.lower() == model_id_lower for m in installed):
            return True
        prefix = model_id_lower.split(":")[0]
        return any(m.split(":")[0].lower() == prefix for m in installed)

    # -----------------------------------------------------------------------
    # Model Routing Resolution
    # -----------------------------------------------------------------------

    def get_model(self, role: str, default: str | None = None, check_installed: bool = False) -> str:
        """
        Resolves the active model ID for a specific role.

        If check_installed is True and the active model is not installed,
        it automatically attempts to return an installed fallback supporting that role.
        """
        with self._file_lock:
            active_map = self._registry_data.get("active_selection", {})
            model_id = active_map.get(role)

            if not model_id:
                fallbacks = self._registry_data.get("fallbacks", {})
                model_id = fallbacks.get(role, default or "qwen3:8b")

            if check_installed:
                installed = self.get_installed_ollama_models()
                # If Ollama is running and has models, verify model presence
                if installed and not self.is_model_installed(model_id):
                    # Try finding another installed model registered for this role
                    candidates = self.get_available_models_for_role(role)
                    for cand in candidates:
                        cid = cand["model_id"]
                        if self.is_model_installed(cid):
                            logger.info(f"Role '{role}' selected '{model_id}' is missing; routing to installed '{cid}'.")
                            return cid

                    # Check fallback
                    fallback = self._registry_data.get("fallbacks", {}).get(role)
                    if fallback and self.is_model_installed(fallback):
                        return fallback

            return model_id

    def get_model_config(self, role: str) -> dict[str, Any]:
        """Returns hyperparameters (temperature, context window, options) for a role."""
        with self._file_lock:
            model_id = self.get_model(role)
            models = self._registry_data.get("models", {})
            cfg = models.get(model_id, {})
            return {
                "model_id": model_id,
                "temperature": cfg.get("temperature", 0.1),
                "context_window": cfg.get("context_window", 4096),
                "vram_estimate_gb": cfg.get("vram_estimate_gb", 4.0),
                "description": cfg.get("description", ""),
                "capabilities": list(cfg.get("capabilities", [])),
            }

    def get_available_models_for_role(self, role: str) -> list[dict[str, Any]]:
        """Returns all models registered that support the given role."""
        with self._file_lock:
            results = []
            models = self._registry_data.get("models", {})
            for mid, mdata in models.items():
                roles = mdata.get("roles", [])
                if role in roles:
                    entry = dict(mdata)
                    entry["capabilities"] = list(mdata.get("capabilities", []))
                    entry["roles"] = list(mdata.get("roles", []))
                    entry["model_id"] = mid
                    entry["is_active"] = (self._registry_data.get("active_selection", {}).get(role) == mid)
                    results.append(entry)
            return results

    def set_active_model(self, role: str, model_id: str) -> tuple[bool, str]:
        """
        Switches the active model for a role.
        Validates whether the model is registered and supports the role.
        """
        with self._file_lock:
            models = self._registry_data.get("models", {})
            if model_id not in models:
                return False, f"Model '{model_id}' is not in the registry. Register it first."

            mdata = models[model_id]
            allowed_roles = mdata.get("roles", [])
            if role not in allowed_roles:
                return False, f"Model '{model_id}' only supports roles: {allowed_roles}, not '{role}'."

            if "active_selection" not in self._registry_data:
                self._registry_data["active_selection"] = {}

            self._registry_data["active_selection"][role] = model_id
            if not self._save_registry_unlocked():
                return False, f"Failed to persist active model for role '{role}' to disk."
            logger.info(f"Active model for role '{role}' updated to '{model_id}'.")
            return True, f"Active model for role '{role}' set to '{model_id}'."

    def register_model(
        self,
        model_id: str,
        roles: list[str],
        capabilities: list[str],
        description: str = "",
        vram_estimate_gb: float = 4.0,
        context_window: int = 4096,
        temperature: float = 0.1,
        set_as_active_for_roles: bool = False,
    ) -> tuple[bool, str]:
        """Registers a new model in the registry and optionally sets it active."""
        with self._file_lock:
            # Normalize and alias roles for dynamic router mapping
            normalized_roles = set()
            role_aliases = {
                "supervisor": {"supervisor", "general"},
                "general": {"general", "supervisor"},
                "analyst": {"reasoning", "analyst"},
                "reasoning": {"reasoning", "analyst"},
                "coder": {"code", "coder"},
                "code": {"code", "coder"},
                "vision": {"vision"},
            }
            for r in roles:
                r_lower = r.lower().strip()
                normalized_roles.update(role_aliases.get(r_lower, {r_lower}))

            stored_roles = sorted(list(normalized_roles))

            self._registry_data["models"][model_id] = {
                "capabilities": list(capabilities),
                "roles": stored_roles,
                "vram_estimate_gb": float(vram_estimate_gb),
                "context_window": int(context_window),
                "temperature": float(temperature),
                "description": description or f"Registered model {model_id}",
            }

            if set_as_active_for_roles:
                if "active_selection" not in self._registry_data:
                    self._registry_data["active_selection"] = {}
                for r in stored_roles:
                    self._registry_data["active_selection"][r] = model_id

            if not self._save_registry_unlocked():
                return False, f"Failed to persist model '{model_id}' registration to disk."
            logger.info(f"Model '{model_id}' registered successfully with roles: {roles}.")
            return True, f"Model '{model_id}' registered successfully."

    def get_full_registry_status(self) -> dict[str, Any]:
        """Returns the full registry merged with live Ollama installation status."""
        with self._file_lock:
            installed = self.get_installed_ollama_models()
            models_status = {}
            for mid, mdata in self._registry_data.get("models", {}).items():
                status = dict(mdata)
                status["is_installed"] = self.is_model_installed(mid)
                models_status[mid] = status

            return {
                "active_selection": dict(self._registry_data.get("active_selection", {})),
                "fallbacks": dict(self._registry_data.get("fallbacks", {})),
                "models": models_status,
                "installed_in_ollama": installed,
            }


def get_model_router() -> ModelRouter:
    """Convenience accessor for the ModelRouter singleton."""
    return ModelRouter.get_instance()
