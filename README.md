# DeepResearch — Multi-Agent Deep Research System

Coordinator agent → parallel local Gemma sub-agents → synthesized report.
Full design in `PROJECT.md`.

## Install

```bash
pip install -r requirements.txt
```

## Run (pick one)

```bash
# One-command launcher (starts Ollama if needed)
./run.sh                  # Gradio
./run.sh streamlit        # Streamlit

# 1. Gradio UI (recommended)
ollama pull gemma4
python app_gradio.py            # opens at http://127.0.0.1:7860

# 2. Streamlit UI
streamlit run app_streamlit.py

# 3. Terminal
python cli.py "Research silicon-based semiconductor companies: 5-year performance, collaborations, risks"
```

Ollama serves Gemma locally, so no paid API key is required. Set
`DEMO_MODE=1` to run the pipeline with deterministic mocked research.

## How it works

1. **Coordinator** decomposes your query into 3–5 independent subtasks.
2. **Sub-agents** (one per subtask) run **in parallel**, each using Gemma
   through the local Ollama API to write analyzed findings.
3. Sub-agents submit findings envelopes (text + status + timing) back to the
   coordinator.
4. **Coordinator synthesizes** the final report: executive summary, sections,
   cross-cutting comparative analysis and limitations.
5. Report (`.md`) and audit trail (`.json`) are saved to `reports/`.

## Tuning (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `MAX_PARALLEL_AGENTS` | 4 | Sub-agents running concurrently |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Local Ollama server |
| `COORDINATOR_MODEL` / `SUBAGENT_MODEL` | gemma4 | Ollama models used |
| `DEMO_MODE` | unset | Set to `1` for deterministic mock mode |

## Grounding limitation

Ollama does not include a web-search provider. The current local agents use
Gemma's existing knowledge and produce no source URLs. Add a separate search
and retrieval layer before relying on the project for current factual research.

## Note on investment queries

For queries about stocks/securities, the system produces factual research
(performance history, partnerships, risks, comparison frameworks) — it does
not give buy/sell recommendations. Reports on such topics are informational,
not financial advice.
