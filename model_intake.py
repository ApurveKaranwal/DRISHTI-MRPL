"""DRISHTI-MRPL Model Intake.

Wires model_discovery + model_capability_detector into the
"New Model Detected -> predicted capabilities -> user confirms -> registered"
flow. This is the module a frontend/API layer should call — it's the only
place that turns a prediction into an actual registry write.

    from model_intake import scan_for_new_models, confirm_model

    pending = scan_for_new_models()
    # -> render each entry as the "New Model Detected" card

    confirm_model("llama3.1:8b", roles=["general"])
    # -> writes to registry via ModelRouter.register_model, clears from
    #    the discovery queue
"""

from __future__ import annotations

import logging
from typing import Any

from model_capability_detector import CAPABILITY_ROLE_MAP, detect_capabilities
from model_discovery import get_model_discovery
from model_router import get_model_router

logger = logging.getLogger("MRPL.ModelIntake")

VALID_ROLES = {"general", "reasoning", "code", "vision", "supervisor"}


def scan_for_new_models() -> list[dict[str, Any]]:
    """
    Returns one UI-ready payload per installed-but-unregistered model:

        {
          "model_id": "llama3.1:8b",
          "capabilities": ["text"],                 # confidently detected (✓)
          "uncertain_capabilities": ["reasoning"],   # unclear (?)
          "not_detected": ["vision", "code"],        # explicitly absent (✗)
          "suggested_roles": ["general"],
          "available_roles": ["general", "reasoning", "code", "vision", "supervisor"],
          "parameter_size": "8B",
          "quantization": "Q4_0",
        }

    Safe to call on a timer/poll — dismissed models are excluded, and
    already-registered models never reappear.
    """
    discovery = get_model_discovery()
    unregistered = discovery.find_unregistered_models()

    results: list[dict[str, Any]] = []
    for model_id in unregistered:
        prediction = detect_capabilities(model_id).to_dict()
        not_detected = [
            c for c in CAPABILITY_ROLE_MAP
            if prediction["capability_confidence"].get(c) == "none"
        ]
        results.append({
            "model_id": model_id,
            "capabilities": prediction["capabilities"],
            "uncertain_capabilities": prediction["uncertain_capabilities"],
            "not_detected": not_detected,
            "suggested_roles": prediction["suggested_roles"],
            "available_roles": sorted(VALID_ROLES),
            "parameter_size": prediction["parameter_size"],
            "quantization": prediction["quantization"],
        })
    return results


def confirm_model(
    model_id: str,
    roles: list[str],
    capabilities: list[str] | None = None,
    description: str = "",
    set_as_active_for_roles: bool = False,
) -> tuple[bool, str]:
    """
    User confirmed (possibly edited) roles for a detected model. Registers
    it and removes it from the pending discovery queue.

    `capabilities` defaults to re-running detection if not supplied, so
    callers can pass just the user's role checkboxes.
    """
    roles = [r for r in roles if r in VALID_ROLES]
    if not roles:
        return False, "At least one valid role must be selected."

    if capabilities is None:
        capabilities = detect_capabilities(model_id).to_dict()["capabilities"] or ["text"]

    router = get_model_router()
    ok, message = router.register_model(
        model_id=model_id,
        roles=roles,
        capabilities=capabilities,
        description=description or f"User-registered model {model_id}",
        set_as_active_for_roles=set_as_active_for_roles,
    )

    if ok:
        get_model_discovery().clear_dismissed(model_id)  # in case it was previously dismissed
        logger.info(f"Model '{model_id}' confirmed and registered with roles {roles}.")

    return ok, message


def dismiss_model(model_id: str) -> None:
    """User chose 'not now' on a detected model — stop prompting for it."""
    get_model_discovery().dismiss(model_id)
