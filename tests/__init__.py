"""Unit and integration test package for DRISHTI-MRPL."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for d in [ROOT, ROOT / "agents", ROOT / "models"]:
    d_str = str(d)
    if d_str not in sys.path:
        sys.path.insert(0, d_str)
