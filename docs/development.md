# Development Guide

[Documentation index](document.md)

## Repository layout

```text
.
├── agents/
│   ├── coordinator.py
│   └── subagent.py
├── core/
│   └── llm.py
├── docs/
│   └── document.md
├── reports/
├── app_gradio.py
├── app_streamlit.py
├── cli.py
├── config.py
├── PROJECT.md
├── README.md
└── requirements.txt
```

## Common extension points

### Change decomposition behavior

Edit `DECOMPOSE_SYSTEM` in `agents/coordinator.py`. Preserve the strict JSON
shape expected by `parse_json_block()`.

### Change research standards

Edit `SUBAGENT_SYSTEM` in `agents/subagent.py`. This prompt controls factual
caution, uncertainty handling, financial boundaries, and output organization.

### Change final report structure

Edit `SYNTHESIS_SYSTEM` in `agents/coordinator.py`.

### Add another model provider

Implement provider-neutral completion and research functions in `core/llm.py`,
then select the provider through configuration. Keep the existing result shape
so coordinator and UI code remain independent of the provider.

### Add a new interface

Instantiate `Coordinator`, supply a logging callable, and call `run(query)`.
The returned dictionary includes report text, artifact paths, and findings.

## Recommended test coverage

The repository does not currently contain automated tests. A useful initial
suite should cover:

- JSON extraction and malformed decomposition responses
- Minimum and maximum subtask enforcement
- Parallel dispatch and stable result ordering
- Individual worker failure handling
- Synthesis with partial findings
- Empty provenance handling and future retrieval integration
- Report and audit serialization
- Demo-mode CLI behavior

Mock Ollama calls in unit tests so the suite remains deterministic and does not
require a running local model.

## Documentation convention

Add new documentation pages under `docs/`, link each page from
`docs/document.md`, and include a link back to the documentation index near the
top of every page.
