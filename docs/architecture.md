# Architecture

[Documentation index](document.md)

## Search pipeline

`Coordinator.run()` calls `core.jobs.search_jobs()`. A thread pool runs Remotive,
Jobicy, Arbeitnow, Remote OK, and a JobSpy path for LinkedIn, Indeed, and Google.
Each adapter normalizes its results into one job schema.

Hard gates run before personalization: query/domain evidence, robotics-role
evidence when requested, education, country, valid date, selected posting
age, and the selected minimum annual salary. Missing salary is rejected whenever
the salary threshold is above zero. City remains a soft preference. Without a resume, eligible results are
newest-first.

The optional `core.gemma_summaries` stage runs after eligibility and ranking.
It can replace presentation-only overview, experience, and requirement fields
for a bounded displayed prefix. Structured output and exact source excerpts are
validated before mutation; each failed listing retains deterministic text.

## Resume-intelligence pipeline

`core.skill_taxonomy.py` defines the broad cross-industry skill, domain, role,
and category taxonomy. `core.resume_intelligence.analyze_candidate()` coordinates bounded parallel
agents for CV structure, public GitHub metadata, and opt-in public portfolio
pages. LinkedIn URLs are recognized but never fetched. Public-page requests are
restricted by scheme, address class, port, content type, timeout, and response
size.

Only derived non-sensitive evidence is passed into `core.jobs.rank()`. Eligible
jobs receive an estimated fit from capped skill, domain, role, and education
overlap. Personalized ordering blends 65% resume fit, 25% query relevance, and a
10% optional city bonus, then uses recency for ties. Raw CV and fetched page text
never enter the search result or report artifacts.

## Presentation

`app_gradio.py` renders fixed-height responsive cards, uses a native left sidebar for the applicant
profile, preventing its height from creating gaps in the main results flow, and places agent logs in a collapsed accordion.
`app_streamlit.py` renders native cards and uses a sidebar. Both dashboards call
the same coordinator, resume analyzer, ranking code, and application module.

## Application preparation

`core.applications.py` extracts PDF, DOCX, TXT, or Markdown CV text, validates
applicant profile fields, and creates deterministic review drafts. Gradio uses
`gr.State`; Streamlit uses `st.session_state`. Final links always open the
original source or employer page.

## Reports

The coordinator writes Markdown and JSON audits and calls
`core.pdf_report.build_pdf()` for the downloadable PDF. Derived fit scores and
matched skills can explain personalized order, while raw CV text, public-page
text, and applicant contact fields are excluded. Reports live under `reports/`
and are ignored by Git.

The legacy general-research agents remain separate from live retrieval. The
live path uses Ollama only when the user explicitly enables evidence-validated
Gemma summaries.
