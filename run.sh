#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
OLLAMA_LOG="/tmp/supportpilot-ollama.log"
UI="${1:-gradio}"

cd "$PROJECT_DIR"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  "$VENV_PYTHON" -m pip install -r requirements.txt
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it from https://ollama.com/download"
  exit 1
fi

if ! ollama list >/dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve >"$OLLAMA_LOG" 2>&1 &
  OLLAMA_PID=$!
  trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

  for _ in {1..30}; do
    if ollama list >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! ollama list | awk 'NR > 1 {print $1}' | grep -Eq '^gemma4(:|$)'; then
  echo "Downloading Gemma 4 (first run only)..."
  ollama pull gemma4
fi

case "$UI" in
  gradio)
    exec "$VENV_PYTHON" app_gradio.py
    ;;
  streamlit)
    exec "$VENV_PYTHON" -m streamlit run app_streamlit.py
    ;;
  *)
    echo "Usage: ./run.sh [gradio|streamlit]"
    exit 2
    ;;
esac
