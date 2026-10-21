#!/usr/bin/env bash
# ==============================================================================
# DRISHTI-MRPL Sovereign AI Workbench - Setup Models Shortcut
# Delegates to scripts/setup_models.sh
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/setup_models.sh" "$@"
