# Installation

[Documentation index](document.md)

## Prerequisites

- Python 3.11 or newer is recommended by the project design
- `pip`
- [Ollama](https://ollama.com/) installed locally

## Set up a virtual environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The required packages are:

- `gradio`
- `streamlit`

## Install Gemma

```bash
ollama pull gemma4
```

Ollama normally serves its API at `http://localhost:11434`. Start the Ollama
application or service before running DeepResearch.

## Verify the installation

Run the offline demo:

```bash
DEMO_MODE=1 python cli.py "Research the home robotics landscape"
```

The command should show four demo agents and create a report and audit file in
`reports/`.
