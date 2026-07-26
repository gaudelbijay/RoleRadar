# Configuration

[Documentation index](document.md)

## Dashboard launch modes

```bash
./run.sh gradio
./run.sh streamlit
./run.sh help
```

Gradio normally binds to `127.0.0.1:7864`; override it with the
`JOBSEARCH_GRADIO_PORT` environment variable. Streamlit normally uses
`localhost:8501`. Each framework prints the actual URL when launched.

## Ranking mode

The production default is the evaluated BM25 ranker. It runs after mandatory filters and automatically falls back to deterministic recency-first ranking when unavailable. Override the default for a process with:

```bash
JOBSEARCH_RANKER=deterministic ./run.sh gradio
```

Accepted values are `bm25`, `hybrid`, `semantic`, `rerank`, and `deterministic`. BM25 runs only after mandatory gates and falls back to deterministic ordering if its dependency is unavailable. Hybrid mode combines BM25 and semantic positions with project-owned RRF at `k=60`; it uses whichever ranker remains available and ultimately falls back to deterministic ordering. Semantic mode uses local in-memory cosine similarity and falls back to BM25, then deterministic ordering, if the model cannot run.

Install the optional local semantic stack and launch semantic evaluation with:

```bash
python -m pip install -r requirements-semantic.txt
JOBSEARCH_RANKER=semantic ./run.sh gradio
JOBSEARCH_RANKER=hybrid ./run.sh gradio
JOBSEARCH_RANKER=rerank ./run.sh gradio
```

The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`. Rerank mode uses `cross-encoder/ms-marco-MiniLM-L-6-v2` for at most 50 retrieved candidates; override it with `JOBSEARCH_CROSS_ENCODER_MODEL`. Override it with `JOBSEARCH_EMBEDDING_MODEL`. The first semantic run downloads model weights from Hugging Face; no API key is required. Job and resume embeddings are held in memory only and are not written to a database.

## Search behavior

The dashboards expose country, optional city, maximum posting age, minimum annual salary, education,
and query controls. Feed timeouts, maximum ranked results, relevance thresholds,
concept mappings, country aliases, and source selection are defined in
`core/jobs.py`.

The live public-source pipeline requires no API credentials. JobSpy behavior is
controlled by the installed `python-jobspy` version and the target sites may
change or rate-limit responses.

## Adaptive source scheduling

The dashboards and CLI enable the RL source scheduler by default. It runs bounded
source waves and can stop launching additional agents after sufficient verified
yield. Uncheck the dashboard option or use `--no-rl-scheduler` in the CLI for
full parallel dispatch. `JOBSEARCH_SOURCE_SCHEDULER=all` selects full dispatch
for direct core usage; policy path,
agent limits, result targets, and deadlines are documented in
[Adaptive RL source scheduler](rl-scheduler.md).

## Resume enrichment

GitHub public metadata works without credentials but is rate-limited. An optional `GITHUB_TOKEN` environment secret increases the GitHub API limit.
Never store it in the repository. Portfolio fetching is controlled by a
dashboard opt-in and cannot be enabled globally through configuration.

## Optional Gemma job summaries

Both dashboards expose an opt-in **Improve top job summaries with Gemma
(Ollama)** control. The CLI equivalent is `--gemma-summaries`. The model runs
only after hard filtering and ranking, so it cannot admit, reject, or reorder a
listing. Its JSON output is accepted only when every supporting excerpt occurs
verbatim in the source description; otherwise the deterministic summary stays
in place.

The default model is `gemma3:4b`. Configure the bounded local step with:

- `JOB_SUMMARY_MODEL`: Ollama model name
- `JOB_SUMMARY_MAX_TOKENS`: maximum generated tokens per listing; default `900`
- `JOBSEARCH_GEMMA_MAX_JOBS`: displayed listings to summarize; default `10`, maximum `30`
- `OLLAMA_BASE_URL`: Ollama endpoint; default `http://localhost:11434`
- `OLLAMA_TIMEOUT_SEC`: request timeout; default `300`

At most two summaries run concurrently. Failure, timeout, invalid JSON, or
unsupported claims trigger a per-listing deterministic fallback.
