@echo off
REM ==============================================================================
REM MRPL Sovereign AI Workbench - 1-Click Operations Launcher (Windows)
REM ==============================================================================

echo.
echo ==============================================================================
echo [MRPL SOVEREIGN WORKBENCH] Launching Industrial Operations Dashboard...
echo Mode: 100% Air-Gapped / Zero External WAN Traffic
echo ==============================================================================
echo.

REM Start browser after 2 seconds
start "" http://localhost:8000

REM Run FastAPI server with python
python server.py

pause
