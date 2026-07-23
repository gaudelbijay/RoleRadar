#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
UI="${1:-gradio}"

cd "$PROJECT_DIR"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  "$VENV_PYTHON" -m pip install -r requirements.txt
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
