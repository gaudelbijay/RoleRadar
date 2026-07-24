# Installation

[Documentation index](document.md)

## Requirements

- Python 3.11 or newer
- Internet access for public job sources
- macOS, Linux, or another environment capable of running the Bash launcher

No paid API key or Ollama model is required for the live job-search path.

## Install

```bash
cd /path/to/jobSearch
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Launch Gradio

```bash
./run.sh gradio
```

Open `http://127.0.0.1:7862` if the browser does not open automatically. If that
port is occupied, Gradio may choose the next available port and print it in the
terminal.

## Launch Streamlit

```bash
./run.sh streamlit
```

Open `http://localhost:8501` if the browser does not open automatically.

Keep the launch terminal open. Press the Control and C keys together to stop
the server. Do not type the literal text `Ctrl+C` as a command.
