# Configuration

[Documentation index](document.md)

Configuration is centralized in `config.py`.

## Environment variables

| Variable | Default | Purpose |
|---|---:|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_TIMEOUT_SEC` | `300` | Per-request timeout |
| `COORDINATOR_MODEL` | `gemma4` | Decomposition and synthesis model |
| `SUBAGENT_MODEL` | `gemma4` | Research worker model |
| `MAX_PARALLEL_AGENTS` | `4` | Maximum simultaneously running workers |
| `DEMO_MODE` | unset | Set to `1`, `true`, or `yes` for mock mode |

Example:

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export MAX_PARALLEL_AGENTS=3
python app_gradio.py
```

## Code-level limits

These values currently require editing `config.py`:

| Setting | Value | Purpose |
|---|---:|---|
| `MIN_SUBTASKS` | `3` | Requested minimum decomposition size |
| `MAX_SUBTASKS` | `5` | Maximum accepted decomposition size |
| `SUBAGENT_MAX_TOKENS` | `2000` | Output budget for each research agent |
| `REPORT_MAX_TOKENS` | `4000` | Output budget for final synthesis |

## Cost and latency considerations

Increasing parallelism can reduce wall-clock time but also increases local CPU,
GPU, and memory pressure. Larger token budgets may improve depth while
increasing latency. Start with the defaults and adjust after observing the
target machine.
