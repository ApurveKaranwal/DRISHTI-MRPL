"""Pytest configuration and environment bootstrap for DRISHTI-MRPL test suite."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
MODELS_DIR = ROOT / "models"

for path_dir in [ROOT, AGENTS_DIR, MODELS_DIR]:
    path_str = str(path_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
