#!/usr/bin/env bash
# ==============================================================================
# MRPL Sovereign AI Workbench - 1-Click Operations Launcher (Apple M2 / Linux)
# ==============================================================================

echo ""
echo "=============================================================================="
echo "[MRPL SOVEREIGN WORKBENCH] Launching Industrial Operations Dashboard..."
echo "Mode: 100% Air-Gapped / Zero External WAN Traffic"
echo "=============================================================================="
echo ""

# Find script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if present
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Open browser if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    (sleep 2 && open http://localhost:8000) &
elif command -v xdg-open &> /dev/null; then
    (sleep 2 && xdg-open http://localhost:8000) &
fi

python3 server.py

