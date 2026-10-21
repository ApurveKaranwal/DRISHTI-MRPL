"""DRISHTI-MRPL Multi-Agent Core & Deterministic Execution Workers."""

from __future__ import annotations

import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _AGENTS_DIR.parent
_MODELS_DIR = _ROOT_DIR / "models"

for _p in [str(_ROOT_DIR), str(_AGENTS_DIR), str(_MODELS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from .Supervisor_agent import SupervisorAgent
from .Data_agent import DataAnalysisWorker
from .Sandbox_agent import CodeSandboxWorker
from .Document_agent import RetrievalWorker
from .Vision_agent import VisionWorker
from .Template_agent import DeliverablesWorker
from .Document_modifier import DocumentModifierWorker
from .Sovereign_monitor import SovereignNetworkAuditor

__all__ = [
    "SupervisorAgent",
    "DataAnalysisWorker",
    "CodeSandboxWorker",
    "RetrievalWorker",
    "VisionWorker",
    "DeliverablesWorker",
    "DocumentModifierWorker",
    "SovereignNetworkAuditor",
]
