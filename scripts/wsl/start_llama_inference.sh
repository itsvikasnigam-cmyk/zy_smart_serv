#!/usr/bin/env bash
# Chat Y: WSL llama.cpp inference stub (hardware track — optional).
# Does not replace Ollama on Windows :11435 (stable Gate 2 fallback).
#
# Usage (inside WSL, after building llama.cpp):
#   export LLAMA_SERVER_BIN=~/llama.cpp/build/bin/llama-server
#   export LLAMA_MODEL_PATH=~/models/your-model.gguf
#   ./scripts/wsl/start_llama_inference.sh owner 8082
#   ./scripts/wsl/start_llama_inference.sh sales 8083
#
# Ports 8082/8083 are OpenAI-compatible /v1 bases for future ai_engine routing.

set -euo pipefail

ROLE="${1:-owner}"
PORT="${2:-8082}"
BIN="${LLAMA_SERVER_BIN:-}"
MODEL="${LLAMA_MODEL_PATH:-}"

if [[ -z "$BIN" || -z "$MODEL" ]]; then
  echo "SKIP: set LLAMA_SERVER_BIN and LLAMA_MODEL_PATH before starting WSL inference."
  echo "  ROLE=$ROLE PORT=$PORT"
  exit 0
fi

if [[ ! -x "$BIN" ]]; then
  echo "ERROR: LLAMA_SERVER_BIN not executable: $BIN" >&2
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  echo "ERROR: LLAMA_MODEL_PATH not found: $MODEL" >&2
  exit 1
fi

echo "Starting llama-server role=$ROLE port=$PORT model=$MODEL"
exec "$BIN" \
  --host 127.0.0.1 \
  --port "$PORT" \
  -m "$MODEL" \
  --ctx-size 4096 \
  -ngl 99
