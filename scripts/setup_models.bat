@echo off
REM ==============================================================================
REM MRPL Sovereign AI Workbench - Open-Weight Models Setup Script (Windows / HP Victus)
REM Tailored for NVIDIA RTX 3050 (6GB VRAM) / Mid-Range GPU Servers
REM ==============================================================================

echo.
echo ==============================================================================
echo [MRPL SOVEREIGN AI] Setting up lightweight open-weight models via Ollama...
echo Target: NVIDIA RTX 3050 6GB / System RAM (VRAM budget: <= 5GB per model)
echo ==============================================================================
echo.

where ollama >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ollama is not installed or not in PATH!
    echo Please install Ollama from https://ollama.com/download and restart this script.
    pause
    exit /b 1
)

echo [1/4] Pulling Coding Model: Qwen 2.5 Coder 7B (Q4_K_M ~4.5GB VRAM)...
ollama pull qwen2.5-coder:7b
if %ERRORLEVEL% neq 0 (
    echo [FALLBACK] Pulling lightweight 3B coding model...
    ollama pull qwen2.5-coder:3b
)

echo.
echo [2/4] Pulling Reasoning Model: DeepSeek-R1-Distill-Qwen 7B (Q4_K_M ~4.7GB VRAM)...
ollama pull deepseek-r1-distill-qwen:7b
if %ERRORLEVEL% neq 0 (
    echo [FALLBACK] Pulling lightweight 1.5B reasoning model...
    ollama pull deepseek-r1-distill-qwen:1.5b
)

echo.
echo [3/4] Pulling General & PSU Note Drafting Model: Qwen 2.5 7B (Q4_K_M ~4.5GB VRAM)...
ollama pull qwen2.5:7b

echo.
echo [4/4] Pulling Multimodal Vision Model: Qwen2-VL 2B (Ultra-lightweight ~1.8GB VRAM)...
ollama pull qwen2-vl:2b

echo.
echo ==============================================================================
echo [MRPL SOVEREIGN AI] All open-weight models successfully installed!
echo Current models in Ollama:
ollama list
echo ==============================================================================
echo Ready to launch MRPL Sovereign AI Workbench.
pause
