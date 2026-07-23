# Configuration

[Documentation index](document.md)

The current live job pipeline has no required credentials. Feed timeouts,
maximum ranked results, relevance thresholds, and source selection are defined
in `core/jobs.py`.

`MAX_PARALLEL_AGENTS` and the Ollama settings in `config.py` belong to the
legacy general-research implementation and do not control live source agents.
