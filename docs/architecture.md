# Architecture

[Documentation index](document.md)

## Search pipeline

`Coordinator.run()` calls `core.jobs.search_jobs()`. A thread pool runs five
source paths concurrently:

1. Remotive
2. Jobicy
3. Arbeitnow
4. Remote OK
5. LinkedIn, Indeed, and Google through JobSpy

Each adapter maps results into one normalized schema. Ranking deduplicates jobs,
applies concept groups and the robotics-domain gate, enforces country, treats
city as a soft preference, checks education evidence, excludes missing/stale
dates, and sorts newest-first. Salary, experience, and requirements are
extracted from source fields and descriptions without guessing.

## Presentation

`app_gradio.py` renders responsive HTML cards and keeps agent logs inside a
collapsed accordion. `app_streamlit.py` renders native Streamlit cards and uses
a sidebar for applicant data. Both call the same coordinator and ranking code.

## Application preparation

`core/applications.py` extracts text from PDF, DOCX, TXT, or Markdown CVs,
validates applicant profile fields, compares CV terms with job text, and creates
review drafts. Gradio uses `gr.State`; Streamlit uses `st.session_state`.
Application data is not passed into report generation. Final application links
always open the original source or employer page.

## Reports

The coordinator writes Markdown and JSON audit artifacts and calls
`core.pdf_report.build_pdf()` for the downloadable styled PDF. Generated
artifacts are stored under `reports/` and ignored by Git.

The legacy Ollama/Gemma research modules remain in the repository but are not
used by the live job-search pipeline.
