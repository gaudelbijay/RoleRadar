#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
UI="${1:-}"

cd "$PROJECT_DIR"

show_help() {
  cat <<'HELP'
Job Search launcher

Usage:
  ./run.sh gradio               Launch Gradio (http://127.0.0.1:7860)
  ./run.sh streamlit            Launch Streamlit (http://localhost:8501)
  ./run.sh cli [options] QUERY  Run the command-line search
  ./run.sh help                 Show this help
HELP
}

if [[ -z "$UI" || "$UI" == "help" || "$UI" == "--help" || "$UI" == "-h" ]]; then
  show_help
  exit 0
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
  "$VENV_PYTHON" -m pip install -r requirements.txt
fi

case "$UI" in
  gradio)
    echo "Launching Gradio (use the actual local URL printed below)"
    exec "$VENV_PYTHON" app_gradio.py
    ;;
  streamlit)
    echo "Launching Streamlit (use the actual local URL printed below)"
    exec "$VENV_PYTHON" -m streamlit run app_streamlit.py
    ;;
  cli)
    shift
    exec "$VENV_PYTHON" cli.py "$@"
    ;;
  *)
    echo "Unknown interface: $UI" >&2
    show_help >&2
    exit 2
    ;;
esac
