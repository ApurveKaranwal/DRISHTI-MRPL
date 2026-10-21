#!/usr/bin/env bash
# ==============================================================================
# MRPL Sovereign AI Workbench - Open-Weight Models Setup Script (Apple Silicon M2 / Linux)
# Tailored for Apple M2 16GB Unified Memory
# ==============================================================================

set -e

echo ""
echo "=============================================================================="
echo "[MRPL SOVEREIGN AI] Setting up lightweight open-weight models via Ollama..."
echo "Target: Apple M2 (16GB Unified Memory) / Linux GPU"
echo "=============================================================================="
echo ""

if ! command -v ollama &> /dev/null; then
    echo "[ERROR] Ollama is not installed or not in PATH!"
    echo "Please install Ollama from https://ollama.com/download and rerun this script."
    exit 1
fi

echo "[1/4] Pulling Coding Model: Qwen 2.5 Coder 7B..."
ollama pull qwen2.5-coder:7b || ollama pull qwen2.5-coder:3b

echo ""
echo "[2/4] Pulling Reasoning Model: DeepSeek-R1 7B / 1.5B..."
ollama pull deepseek-r1:7b || ollama pull deepseek-r1:1.5b

echo ""
echo "[3/4] Pulling General & PSU Note Drafting Model: Qwen 2.5 7B..."
ollama pull qwen2.5:7b

echo ""
echo "[4/4] Pulling Multimodal Vision Model: Qwen2-VL 2B..."
ollama pull qwen2-vl:2b

echo ""
echo "=============================================================================="
echo "[MRPL SOVEREIGN AI] All models successfully installed!"
echo "Current models in Ollama:"
ollama list
echo "=============================================================================="
echo "Ready to launch MRPL Sovereign AI Workbench."
