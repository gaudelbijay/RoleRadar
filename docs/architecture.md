# Architecture

[Documentation index](document.md)

## Execution flow

```text
Research query
      |
      v
Gradio / Streamlit / CLI
      |
      v
Coordinator
  1. Decompose query
  2. Dispatch tasks
      |
      +----> Sub-agent 1 ----> local Gemma
      +----> Sub-agent 2 ----> local Gemma
      +----> Sub-agent 3 ----> local Gemma
      +----> Sub-agent N ----> local Gemma
      |
  3. Collect findings
  4. Synthesize report
      |
      +----> Markdown report
      +----> JSON audit trail
```

## Coordinator

`agents/coordinator.py` owns the complete workflow:

- `decompose()` asks the language model for independent research tasks.
- `dispatch()` starts one sub-agent per task with `ThreadPoolExecutor`.
- `synthesize()` combines all available findings into a final report.
- `run()` coordinates the pipeline and writes its artifacts.

The coordinator does not search the web. This separation allows it to focus on
planning, aggregation, and cross-topic analysis.

## Research sub-agents

`agents/subagent.py` contains the worker implementation. Each worker receives
the original query and one research brief. In local mode, the worker calls
Gemma through Ollama's HTTP API.

Workers return an envelope containing:

```json
{
  "agent_id": 1,
  "subtask": {"title": "Topic", "task": "Research brief"},
  "result": {
    "text": "Analyzed findings",
    "sources": [],
    "searches": []
  },
  "status": "ok",
  "elapsed_sec": 4.2
}
```

An API failure inside one research worker produces an error envelope instead of
terminating all other workers.

The empty provenance arrays preserve a stable result schema for a future
retrieval integration. They remain empty in the current Ollama-only version.

## LLM layer

`core/llm.py` isolates the Ollama integration:

- `llm_complete()` handles coordinator completions.
- `llm_research()` obtains Gemma analysis in the coordinator's result format.
- Mock functions implement offline decomposition, research, and reporting.
- `parse_json_block()` extracts structured decomposition output.

## Concurrency model

Research calls are I/O-bound, so the project uses threads. The maximum worker
count is controlled by `MAX_PARALLEL_AGENTS`. Completed findings are sorted by
agent ID before synthesis to keep report ordering deterministic.
