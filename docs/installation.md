# Installation

[Documentation index](document.md)

## Requirements

- Python 3.11 or newer
- Internet access for public job sources
- macOS, Linux, or another environment capable of running the Bash launcher

No paid API key or Ollama model is required for search, filtering, or ranking.

## Install

```bash
cd /path/to/RoleRadar
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Optional semantic ranking

BM25 is installed by default. To evaluate local Sentence Transformer ranking, install the separate neural dependencies:

```bash
python -m pip install -r requirements-semantic.txt
JOBSEARCH_RANKER=semantic ./run.sh gradio
# Or combine semantic and BM25 rankings with RRF:
JOBSEARCH_RANKER=hybrid ./run.sh gradio
# Or rerank at most 50 retrieved candidates with a local CrossEncoder:
JOBSEARCH_RANKER=rerank ./run.sh gradio
```

The first semantic search downloads the compact model. No API key is required, and embeddings are not persisted.

## Optional Gemma summaries

Install Ollama separately, then download the default local summary model:

```bash
ollama pull gemma3:4b
```

Start Ollama and enable **Improve top job summaries with Gemma (Ollama)** in a
dashboard, or pass `--gemma-summaries` to the CLI. The option is off by default;
search continues with deterministic summaries when Ollama is absent or a model
response fails evidence validation.

## Launch Gradio

```bash
./run.sh gradio
```

Open `http://127.0.0.1:7864` if the browser does not open automatically. If that
port is occupied, Gradio may choose the next available port and print it in the
terminal.

## Launch Streamlit

```bash
./run.sh streamlit
```

Open `http://localhost:8501` if the browser does not open automatically.

Keep the launch terminal open. Press the Control and C keys together to stop
the server. Do not type the literal text `Ctrl+C` as a command.
