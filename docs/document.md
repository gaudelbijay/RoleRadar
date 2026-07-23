# DeepResearch Documentation

DeepResearch is a multi-agent research prototype. It decomposes an open-ended
question into independent analysis tasks, runs local Gemma agents in parallel,
and synthesizes their findings into a Markdown report with an audit trail.

## Documentation map

| Document | Description |
|---|---|
| [Project overview](overview.md) | Purpose, capabilities, use cases, and limitations |
| [Architecture](architecture.md) | Components, execution flow, and design decisions |
| [Installation](installation.md) | Requirements and local setup |
| [Usage](usage.md) | Gradio, Streamlit, and command-line instructions |
| [Configuration](configuration.md) | Environment variables, models, and budgets |
| [Reports and auditing](reports-and-auditing.md) | Generated artifacts and their formats |
| [Development guide](development.md) | Repository layout, extension points, and testing guidance |

## Project-level documents

- [README](../README.md) — quick start and basic usage
- [Project proposal and technical design](../PROJECT.md) — original detailed
  proposal, roadmap, risks, and success metrics
- [License](../LICENSE) — MIT license

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app_gradio.py
```

Install Ollama and download Gemma before starting an interface:

```bash
ollama pull gemma4
python app_gradio.py
```

Set `DEMO_MODE=1` to use deterministic mock responses without Ollama.
