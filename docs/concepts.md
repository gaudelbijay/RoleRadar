# Concepts and practical architecture

[Documentation index](document.md)

## Decision rule

Job Search is currently a local, single-user application that retrieves a few
hundred fresh listings per search. A component belongs in the roadmap only when
it improves result quality, responsiveness, safety, or testability at that
scale. Technologies are not included merely to make the stack look larger.

Gradio and Streamlit call Python modules directly. The project does **not** need
FastAPI or another API layer. An API should be reconsidered only when a separate
client or external consumer exists.

## Keep

| Concept | Selected approach | Why it helps |
|---|---|---|
| Deterministic hard gates | Existing Python rules | Country, date, search type, and safety constraints must never be overridden by a model |
| Keyword retrieval | `rank-bm25` | Improves exact matching for role names, credentials, and technologies |
| Semantic matching | Sentence Transformers | Finds close concepts when job descriptions use different terminology |
| Similarity | In-memory cosine similarity | A few hundred listings do not require a vector database |
| Hybrid fusion | Small project-owned RRF function | Combines BM25 and semantic rankings without score-normalization problems |
| Final reranking | Local CrossEncoder behind a feature flag | Improves precision on only the top candidates |
| Local cache and memory | SQLite | One local dependency can cache source results and store user-approved state |
| Optional summaries | Gemma through Ollama | Can improve role summaries when evidence and output schemas are constrained |
| Tests | pytest | Prevents ranking, parsing, filtering, and privacy regressions |
| CI | GitHub Actions | Runs tests and documentation checks on every change |
| Packaging | Existing virtual environment and launcher | Lowest-friction local setup |

The current deterministic ranking remains the fallback whenever an optional
model is unavailable.

## Remove from the active roadmap

| Concept or tool | Decision | Why it makes the project worse now |
|---|---|---|
| FastAPI | Remove | There is no separate frontend or external API consumer |
| LangGraph | Remove | The bounded pipeline is already clear with Python functions and thread pools |
| LangChain | Remove | It would wrap simple local operations without adding needed capability |
| Pinecone | Remove | Managed vector infrastructure is unnecessary for hundreds of listings |
| ChromaDB | Defer | Persistence is unnecessary until the corpus grows beyond per-search retrieval |
| Weaviate | Remove | Adds a server and operational surface for features that can run in memory |
| Milvus | Remove | Designed for a much larger vector workload than this project has |
| pgvector | Defer | Useful only if PostgreSQL becomes the primary persistent database |
| Redis | Remove | A separate cache server is excessive for a local, single-user application |
| RAG framework | Remove | Retrieval can be implemented directly; no framework is required |
| Sentry | Defer | Local errors are visible directly, and external reporting creates privacy risk |
| Langfuse | Defer | External prompt tracing is unnecessary and risks exposing resume evidence |
| Docker Compose | Defer | Without Redis or database services, it adds complexity to local startup |
| LoRA | Remove | There is no large, consented, labeled relevance dataset |
| QLoRA | Remove | It has the same data problem and adds a training toolchain |
| Distillation | Remove | There is no validated teacher model or demonstrated latency problem |
| DOLG | Remove | Image retrieval does not improve text-based resume and job matching |
| Chain-of-thought collection | Reject | Private reasoning should not be requested, displayed, or persisted |

“Defer” means the component has a plausible future use but should not be
installed or implemented now. It must satisfy the adoption criteria below
before returning to the roadmap.

## Target search pipeline

```text
User query, resume evidence, country, age, education, and search type
    -> SQLite cache lookup
    -> live sources on cache miss
    -> normalize and deduplicate
    -> mandatory country/date/search-type/safety gates
    -> BM25 score
    -> Sentence Transformers embedding and cosine score
    -> Reciprocal Rank Fusion
    -> optional CrossEncoder reranking of the top 30–50
    -> resume-fit, city preference, and recency adjustments
    -> job cards and PDF report
```

This pipeline stays small because embeddings are computed only for listings
that pass inexpensive hard gates. The CrossEncoder sees only the fused top
candidates, not every fetched listing.

## Hybrid matching

### BM25

BM25 preserves precision for exact evidence such as `ROS 2`, `CPA`, `FastAPI`,
degree names, certifications, and specialized job titles. The searchable text
contains the normalized title, description, requirements, skills, company, and
location.

### Semantic similarity

A compact local Sentence Transformers model encodes the query, derived resume
evidence, and eligible job text. Cosine similarity runs in memory. Embeddings
are cached in SQLite by content hash and model version so unchanged listings do
not need to be encoded again.

### Reciprocal Rank Fusion

The project owns a deterministic RRF implementation:

```text
RRF(document) = sum(1 / (k + rank_in_each_result_list))
```

The initial `k` can be 60, but it must be selected using ranking tests. RRF
combines BM25 and semantic positions without assuming their raw scores are
directly comparable.

### CrossEncoder reranking

The CrossEncoder is optional and receives at most 30–50 fused candidates. It
must run locally and behind a configuration flag. The feature is enabled by
default only if evaluation shows a meaningful Precision@10 improvement with
acceptable latency.

Mandatory constraints run before reranking. A high semantic score cannot admit
an old, wrong-country, wrong-search-type, or unsafe listing.

## Gemma and constrained generation

Gemma is optional and limited to evidence-backed role summaries, requirement
grouping, and report prose. It receives selected source fragments and must
return a validated structured schema.

Gemma must not determine country, publication age, application status, salary,
or whether a listing passes mandatory gates. Missing information is labeled,
not invented. The application requests conclusions and source evidence rather
than private chain-of-thought reasoning.

## SQLite boundaries

SQLite may store:

- short-lived source results keyed by normalized search settings;
- content hashes and embeddings;
- model and taxonomy versions;
- saved searches explicitly approved by the user;
- application review status.

SQLite must not persist raw CV text, portfolio page text, contact information,
or credentials by default. Cached jobs and embeddings require configurable
expiry and invalidation when the model version changes.

## Performance limits

- Apply hard gates before embeddings or reranking.
- Embed each unique content hash once.
- Retrieve no more than 100 BM25 and 100 semantic candidates.
- Fuse candidates before CrossEncoder processing.
- Rerank no more than 50 candidates.
- Generate summaries only for displayed results.
- Cap model workers to avoid memory pressure.
- Fall back to deterministic ranking when a model fails.
- Never run training during an interactive search.

## Evaluation

Add a versioned, de-identified benchmark before changing ranking behavior. It
should measure:

- hard-filter correctness;
- Precision@5 and Precision@10;
- Recall@50 before reranking;
- NDCG@10 after reranking;
- wrong-country, stale, wrong-search-type, and incidental-domain leakage;
- p50 and p95 search latency;
- cache hit rate and model failures.

BM25, semantic matching, or the CrossEncoder is retained only when it improves
measured quality enough to justify its latency and dependencies.

## Delivery plan

1. Add pytest fixtures and baseline ranking metrics.
2. Add SQLite source caching and content hashes.
3. Add BM25 behind a feature flag and compare it with the baseline.
4. Add compact local embeddings and in-memory cosine similarity.
5. Add the project-owned RRF implementation.
6. Add a local CrossEncoder behind a feature flag.
7. Enable only the components that pass quality and latency thresholds.
8. Add GitHub Actions after the test suite is stable.

## Criteria for deferred infrastructure

Reconsider a vector database only when the searchable corpus is persistently
large enough that in-memory cosine search becomes a measured bottleneck.
Reconsider Redis when concurrent users or distributed workers make SQLite
locking or cache throughput a measured problem. Reconsider an API when a real
separate client exists. Reconsider Docker when deployment reproducibility,
rather than local setup, becomes a requirement.

Training techniques such as LoRA, QLoRA, and distillation require a consented,
de-identified labeled dataset, a defined baseline, and evidence that prompting
or a compact existing reranker cannot meet the target. Until those conditions
exist, they remain outside the project.
