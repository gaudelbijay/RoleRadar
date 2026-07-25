# Job Search — Technical Report

[← Clone and run the project](README.md#tab-1--clone--run) · [Documentation index](docs/document.md)

### 1. Project objective

Job Search is an end-to-end applied information-retrieval system. It addresses five practical problems:

1. Aggregate recent openings from inconsistent public sources.
2. Prevent irrelevant, stale, wrong-country, wrong-search-type, and below-threshold listings from leaking into results.
3. Match concepts even when a listing does not repeat the exact user phrase.
4. Personalize eligible results using resume evidence without persisting raw applicant data.
5. Present understandable evidence, reports, and application drafts without claiming that an application was submitted.

The project is a substantial engineering and portfolio system. Its synthetic benchmark provides a repeatable regression check for ranking changes; production behavior also depends on the availability and quality of live source data.

### 2. System architecture

![Job Search system architecture](assets/system-architecture.svg)

The architecture keeps eligibility rules separate from relevance models. Live
sources feed a normalized job schema, mandatory gates establish the eligible
set, and layered rankers organize only that set before the dashboards generate
evidence, reports, and review-first application materials.

Hard constraints are evaluated before optional neural ranking. A high model score cannot admit an old, wrong-country, wrong-search-type, or otherwise ineligible listing.

### 3. Live retrieval and normalization

Bounded parallel source agents retrieve listings from Remotive, Jobicy, Arbeitnow, Remote OK, and public LinkedIn/Indeed/Google paths through JobSpy. Glassdoor is exposed as a targeted search link because its public scraping route is unreliable. Each source is converted to a common schema containing title, company, location, description, publication date, salary evidence, source URL, and original application URL.

Normalization includes HTML cleanup, date handling, salary normalization, canonical identifiers, URL validation, and cross-source deduplication. The original source remains authoritative.

### 4. Constraint-preserving filtering

The inexpensive mandatory gates run before embeddings and reranking:

- valid and sufficiently recent publication date;
- mandatory country match;
- Jobs versus Internships evidence;
- requested education evidence;
- disclosed annualized salary threshold when the threshold is nonzero;
- concept relevance across the title and description;
- domain evidence for specialized queries such as robotics;
- unsafe or malformed listing rejection.

City is deliberately a soft preference. Robotics is concept-aware rather than literal: terms such as manipulation, SLAM, localization, motion planning, autonomy, perception, ROS, and robot learning can establish domain evidence.

### 5. BM25 keyword retrieval

BM25 is the production default. The document representation gives additional weight to titles and tags while retaining description, company, and location evidence. Its core score is:

```text
BM25(q, d) = Σ IDF(qᵢ) · [f(qᵢ,d) · (k₁ + 1)]
                         ─────────────────────────────
                         f(qᵢ,d) + k₁ · (1 - b + b|d|/avgdl)
```

This method is strong for exact technical evidence such as `ROS 2`, `CPA`, `C++`, certifications, degrees, and specialized titles. The implementation uses `rank-bm25`, stable tokenization, fourfold title weighting, and deterministic fallback when the dependency is unavailable.

### 6. Semantic embeddings and cosine similarity

Optional semantic mode uses `sentence-transformers/all-MiniLM-L6-v2`. It encodes the query and controlled job text locally. For query vector **q** and document vector **d**:

```text
cos(q, d) = (q · d) / (||q||₂ ||d||₂)
```

Vectors are normalized before the dot product. Duplicate job text is collapsed by SHA-256 content hash during each call so identical text is encoded once. Embeddings remain in memory and are discarded after the process; the project does not require Pinecone, ChromaDB, Weaviate, Milvus, Redis, SQLite, or another persistent vector store.

### 7. Reciprocal Rank Fusion

Hybrid mode combines BM25 and semantic rankings without averaging incompatible raw scores:

```text
RRF(d) = Σᵣ 1 / (k + rankᵣ(d)),    k = 60
```

RRF rewards documents that rank well in either constituent list and is stable when BM25 and cosine scores use different numerical scales. If semantic retrieval fails, the pipeline retains BM25; if both optional rankers fail, it returns to deterministic ordering.

### 8. CrossEncoder reranking

Experimental rerank mode uses `cross-encoder/ms-marco-MiniLM-L-6-v2`. Unlike independent embeddings, a CrossEncoder reads each query–job pair jointly and produces a relevance score. To control latency and memory, it processes at most the top **50** hybrid candidates. Failure preserves the best available retrieval order.

### 9. Resume intelligence and personalization

The project taxonomy covers **356 skills, 21 categories, and 32 domains**, including—but not limited to—AI and robotics. Resume agents extract structured evidence from PDF, DOCX, TXT, or Markdown CVs. Public GitHub evidence can be analyzed; public portfolio analysis is opt-in. LinkedIn URLs are recognized but not scraped.

Only derived evidence enters ranking. Raw CV text, fetched portfolio text, and applicant contact fields are excluded from reports and audits. Eligible jobs can be ordered using:

```text
personalized score = 0.65(resume fit)
                   + 0.25(query relevance)
                   + 0.10(city preference)
```

Recency provides deterministic tie-breaking. Personalization cannot override mandatory gates.

### 10. Evidence-validated Gemma summaries

Gemma through Ollama is optional and disabled by default. It receives the search query, job title, company, and bounded source description for only the top displayed listings. It returns structured JSON containing:

- role overview;
- overview evidence;
- experience statements with evidence;
- requirements with evidence.

Every evidence excerpt must occur in the source description. Invalid JSON, missing support, timeout, unavailable Ollama, or unsupported claims cause a per-job deterministic fallback. Defaults are:

- model: `gemma3:4b`;
- maximum output: 900 tokens per listing;
- maximum summarized jobs: 10, configurable up to 30;
- concurrency: at most 2 generations.

Gemma does not control country, age, salary, search type, eligibility, ranking, or application status.

### 11. Ranking benchmark and numerical results

The versioned benchmark is stored in `benchmarks/ranking_v1.json`. It contains synthetic, de-identified query–candidate judgments and hard-rejection cases. `tests/test_ranking_benchmark.py` verifies that forbidden listings never enter ranked results and evaluates:

```text
Precision@k = relevant retrieved in top k / retrieved in top k
Recall@k    = relevant retrieved in top k / all labeled relevant

DCG@k  = Σᵢ₌₁ᵏ (2^relᵢ - 1) / log₂(i + 1)
NDCG@k = DCG@k / IDCG@k
```

| Ranking configuration | Precision@5 | Precision@10 | Recall@50 | NDCG@10 | Status |
|---|---:|---:|---:|---:|---|
| Deterministic recency baseline | 0.722222 | 0.722222 | 1.000000 | 0.706427 | Fallback |
| Semantic cosine | 0.722222 | 0.722222 | 1.000000 | 0.895588 | Opt-in |
| BM25 | 0.722222 | 0.722222 | 1.000000 | 0.933686 | Default |
| Hybrid BM25 + semantic RRF | 0.722222 | 0.722222 | 1.000000 | **0.947923** | Best benchmark quality; opt-in |
| Hybrid + CrossEncoder | 0.722222 | 0.722222 | 1.000000 | 0.933686 | Experimental |

Hybrid RRF improves NDCG@10 from **0.706427 to 0.947923**, an absolute gain of **0.241496** and a relative gain of approximately **34.19%** on benchmark v1. Recall@50 remains 1.0 and the hard-gate tests reject all labeled forbidden candidates.

The benchmark cases contain fewer than five eligible jobs in some queries, so Precision@5 and Precision@10 use the available result window and cannot yet demonstrate improvement. The CrossEncoder cold benchmark run was approximately **14.3 seconds** and did not beat hybrid RRF, so it remains experimental.

### 12. Application preparation and company staff discovery

The application assistant creates an editable cover-letter draft, reusable profile answers, CV-to-job evidence, and a review queue. It never claims submission, bypasses authentication, solves CAPTCHA, accepts consent, or answers unknown screening questions automatically. The final action opens the original employer site.

Public company staff discovery is bounded to verified official pages. It can display named technical staff, roles, technical areas, official biographies, careers pages, and explicitly published company recruiting addresses. A person is highlighted as a hiring manager only when an official source explicitly identifies that role. Personal Gmail addresses, guessed emails, phone numbers, LinkedIn scraping, and private contact data are excluded.

### 13. Reports, privacy, and failure behavior

Each search can produce responsive job cards, a styled PDF, original application links, and a local JSON audit. Generated files live in `reports/` and are ignored by Git.

Privacy boundaries include:

- no paid cloud LLM API requirement;
- no persistence of raw CV or portfolio page text in reports;
- no applicant contact data in generated search reports;
- no model authority over hard constraints;
- no automatic application submission;
- bounded URL fetching with scheme, address, port, timeout, content-type, redirect, and response-size controls;
- deterministic degradation when optional models or sources fail.

### 14. Testing and continuous integration

The current offline suite contains **59 passing tests** covering filtering, internship classification, salary behavior, BM25, semantic scoring, RRF, CrossEncoder limits, ranking metrics, Gemma evidence validation, JSON parsing, documentation links, resume behavior, and fallbacks.

GitHub Actions runs on pushes and pull requests with read-only repository permissions. CI:

1. installs base and development dependencies on Python 3.11;
2. runs `pip check`;
3. compiles Python sources;
4. runs pytest and documentation-link validation;
5. checks whitespace.

CI intentionally avoids downloading Ollama and optional neural weights; model interfaces are tested with deterministic fakes.

### 15. Technology map

| Area | Implementation |
|---|---|
| Language | Python |
| Interfaces | Gradio, Streamlit, CLI |
| Job retrieval | Public feeds and JobSpy adapters |
| Keyword ranking | `rank-bm25` |
| Semantic ranking | Sentence Transformers + NumPy cosine similarity |
| Fusion | Project-owned Reciprocal Rank Fusion |
| Final reranking | Local Sentence Transformers CrossEncoder |
| Local generation | Gemma through Ollama |
| Resume files | pypdf, python-docx, plain text/Markdown |
| Reports | ReportLab PDF + JSON audit |
| Tests | pytest |
| Automation | GitHub Actions |
| Concurrency | Bounded Python thread pools |
| Persistence | Generated report artifacts only; no vector database or resume cache |

### 16. Operational limitations

- Live job sources can change markup, rate-limit requests, or return incomplete data.
- Salary and publication dates are shown only when reliable source evidence exists.
- Public web retrieval cannot guarantee complete coverage of every job board.
- Resume-fit scores estimate textual evidence overlap and are not hiring predictions.
- The synthetic benchmark is designed for repeatable regression testing and does not represent every occupation, location, or live source condition.
- Ranking quality depends on the completeness and accuracy of the text supplied by each job source.
- Optional neural ranking adds local model download, memory, and latency costs, so BM25 remains the lightweight default.

The system is designed as a practical open-source job-search and application-preparation product. Ranking scores help organize source evidence; they do not evaluate a person's employability or replace applicant and employer judgment.

### 17. Repository guide

| Path | Responsibility |
|---|---|
| `core/jobs.py` | Source normalization, constraints, relevance, ranking orchestration, and report text |
| `core/bm25_ranker.py` | Keyword retrieval |
| `core/semantic_ranker.py` | Local embeddings and cosine similarity |
| `core/rrf_ranker.py` | Reciprocal Rank Fusion |
| `core/cross_encoder_ranker.py` | Bounded pairwise reranking |
| `core/gemma_summaries.py` | Evidence-validated optional summaries |
| `core/resume_intelligence.py` | Resume and safe public-link evidence analysis |
| `core/applications.py` | CV extraction and review-first drafts |
| `agents/coordinator.py` | Search orchestration and artifact generation |
| `app_gradio.py` | Primary Gradio dashboard |
| `app_streamlit.py` | Streamlit dashboard |
| `benchmarks/ranking_v1.json` | Versioned ranking judgments |
| `tests/` | Offline regression and ranking evaluation suite |
| `.github/workflows/ci.yml` | Continuous integration |

For focused operational documentation, open the [documentation index](docs/document.md).

[← Clone and run the project](README.md#tab-1--clone--run) · [README](README.md)

---

## Responsible-use notice

Job Search assists discovery and preparation. Employers and original job pages remain authoritative. Users must verify every generated statement, eligibility answer, salary value, and application field before submission. The software must not be used to collect private contact information, bypass access controls, misrepresent qualifications, or submit applications without informed human review.
