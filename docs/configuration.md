# Configuration

[Documentation index](document.md)

## Dashboard launch modes

```bash
./run.sh gradio
./run.sh streamlit
./run.sh help
```

Gradio normally binds to `127.0.0.1:7860`; Streamlit normally uses
`localhost:8501`. Each framework prints the actual URL when launched.

## Search behavior

The dashboards expose country, optional city, maximum posting age, education,
and query controls. Feed timeouts, maximum ranked results, relevance thresholds,
concept mappings, country aliases, and source selection are defined in
`core/jobs.py`.

The live public-source pipeline requires no API credentials. JobSpy behavior is
controlled by the installed `python-jobspy` version and the target sites may
change or rate-limit responses.

## Legacy Ollama settings

`COORDINATOR_MODEL`, `SUBAGENT_MODEL`, `OLLAMA_BASE_URL`,
`OLLAMA_TIMEOUT_SEC`, and `MAX_PARALLEL_AGENTS` in `config.py` belong to the
legacy general-research implementation. They do not control the live job-source
search used by either dashboard.
