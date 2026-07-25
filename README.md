# Job Search

A privacy-conscious, resume-personalized job discovery and application-preparation system. It retrieves recent public listings, enforces user constraints, ranks eligible jobs with classical and neural information retrieval, produces evidence-validated summaries, and keeps final application submission under human control.

<p align="center">
  <a href="#tab-1--clone--run"><strong>▶ Tab 1 · Clone & Run</strong></a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#tab-2--technical-report"><strong>▤ Tab 2 · Technical Report</strong></a>
</p>

> GitHub README files cannot run JavaScript, so these GitHub-compatible links act as two tabs and work in every repository view.

---

## Tab 1 · Clone & Run

### Requirements

- Python 3.11 or newer
- Git
- Internet access for live public job sources
- macOS or Linux for the included Bash launcher
- Optional: [Ollama](https://ollama.com/) for local Gemma summaries

No paid LLM API key is required. BM25 is installed by default. Semantic retrieval and Gemma summaries are optional.

### 1. Clone the repository

```bash
git clone https://github.com/gaudelbijay/jobSearch.git
cd jobSearch
```

### 2. Create the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The launcher also creates `.venv` and installs the base requirements automatically when the environment does not exist.

### 3. Launch a dashboard

Gradio is the primary interface:

```bash
./run.sh gradio
```

Open the URL printed in the terminal, normally `http://127.0.0.1:7864`.

Streamlit is also supported:

```bash
./run.sh streamlit
```

Open the printed URL, normally `http://localhost:8501`.

Keep the terminal running. Press Control+C to stop the server; do not type the literal text `Ctrl+C` as a shell command.

### 4. Run from the command line

```bash
./run.sh cli \
  --country "United States" \
  --city Boston \
  --max-age 10 \
  --education PhD \
  --minimum-salary 100000 \
  "robotics perception engineer"
```

Country is mandatory. City is a preference, not a hard exclusion. Set `--minimum-salary 0` to retain listings without disclosed salary evidence.

### 5. Optional semantic and hybrid ranking

Install the separate local neural stack:

```bash
python -m pip install -r requirements-semantic.txt
```

Choose one ranking mode when launching:

```bash
# Production default
JOBSEARCH_RANKER=bm25 ./run.sh gradio

# Local Sentence Transformer and cosine similarity
JOBSEARCH_RANKER=semantic ./run.sh gradio

# BM25 + semantic retrieval fused with RRF
JOBSEARCH_RANKER=hybrid ./run.sh gradio

# Hybrid retrieval followed by bounded CrossEncoder reranking
JOBSEARCH_RANKER=rerank ./run.sh gradio

# Model-free fallback
JOBSEARCH_RANKER=deterministic ./run.sh gradio
```

The first neural run downloads model weights from Hugging Face. No Hugging Face API key is required for the public default models.

### 6. Optional Gemma summaries

Install and start Ollama, then download the default model:

```bash
ollama pull gemma3:4b
```

Enable **Improve top job summaries with Gemma (Ollama)** in either dashboard, or use:

```bash
./run.sh cli --country "United States" --gemma-summaries "software engineer"
```

Gemma never decides whether a listing passes the filters or changes its ranking. It only rewrites presentation fields after ranking, and unsupported output falls back to deterministic extraction.

### 7. Run tests

```bash
python -m pip install -r requirements-dev.txt
./run.sh test
```

Current verified result: **59 tests passed**. Tests mock external services and do not require live job sites, GitHub, portfolio pages, Ollama, or model downloads.

### Main controls

| Control | Behavior |
|---|---|
| Search type | Jobs by default; Internships accepts internship, intern, co-op, or trainee evidence |
| Country | Required; United States is the default |
| City | Optional ranking preference; does not remove other cities in the country |
| Maximum age | User-selected 1–30 day hard limit; stale and undated listings are rejected |
| Education | High School, Bachelor's, Master's, or PhD; PhD is the default |
| Minimum salary | Defaults to 100,000 in the listing currency; zero includes undisclosed salaries |
| CV | Optional PDF, DOCX, TXT, or Markdown input for resume-aware ordering |
| Gemma summaries | Optional local, evidence-validated presentation enhancement |

[Back to the two tabs](#job-search) · [Open the technical report](#tab-2--technical-report)

---

## Tab 2 · Technical Report

### 1. Project objective

Job Search is an end-to-end applied information-retrieval system. It addresses five practical problems:

1. Aggregate recent openings from inconsistent public sources.
2. Prevent irrelevant, stale, wrong-country, wrong-search-type, and below-threshold listings from leaking into results.
3. Match concepts even when a listing does not repeat the exact user phrase.
4. Personalize eligible results using resume evidence without persisting raw applicant data.
5. Present understandable evidence, reports, and application drafts without claiming that an application was submitted.

The project is a strong engineering prototype and portfolio system. Its current benchmark is synthetic, so the numerical results below are regression evidence—not a claim of real-world user-study performance or research-paper-level generalization.

### 2. System architecture

```text
Query + country + optional city + age + education + salary + search type
                              │
                              ▼
                 Parallel public source adapters
                              │
                              ▼
                  Normalize and deduplicate jobs
                              │
                              ▼
          Mandatory date/location/type/domain/salary gates
                              │
                              ▼
       BM25 ────── Semantic cosine similarity (optional)
          │                         │
          └──────── RRF fusion ─────┘
                              │
                 CrossEncoder top-50 (optional)
                              │
              Resume fit + city + recency signals
                              │
                              ▼
      Job cards + PDF + audit + application review queue
                              │
                 Gemma summaries (optional)
```

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

### 12. Application preparation and company research

The application assistant creates an editable cover-letter draft, reusable profile answers, CV-to-job evidence, and a review queue. It never claims submission, bypasses authentication, solves CAPTCHA, accepts consent, or answers unknown screening questions automatically. The final action opens the original employer site.

Public company research is bounded to verified official pages. It can display named technical staff, roles, technical areas, official biographies, careers pages, and explicitly published company recruiting addresses. A person is highlighted as a hiring manager only when an official source explicitly identifies that role. Personal Gmail addresses, guessed emails, phone numbers, LinkedIn scraping, and private contact data are excluded.

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

### 16. Honest limitations and research status

- Live job sources can change markup, rate-limit requests, or return incomplete data.
- Salary and publication dates are shown only when reliable source evidence exists.
- Public web retrieval cannot guarantee complete coverage of every job board.
- Resume-fit scores estimate textual evidence overlap and are not hiring predictions.
- The benchmark is small and synthetic, with no human annotation or statistical significance testing.
- BM25, embeddings, RRF, and CrossEncoders are established methods; their integration is an engineering contribution rather than a new ranking algorithm.
- Publication-quality claims require a larger frozen dataset, multiple human assessors, inter-annotator agreement, stronger baselines, ablations, latency distributions, confidence intervals, significance tests, and a user study.

As currently implemented, the project is best described as a substantial applied-AI portfolio project and open-source engineering prototype. It is close to a system-demo or workshop direction, but it should not be presented as a validated production hiring system or completed research paper.

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

[Back to Clone & Run](#tab-1--clone--run) · [Back to the two tabs](#job-search)

---

## Responsible-use notice

Job Search assists discovery and preparation. Employers and original job pages remain authoritative. Users must verify every generated statement, eligibility answer, salary value, and application field before submission. The software must not be used to collect private contact information, bypass access controls, misrepresent qualifications, or submit applications without informed human review.
