# Development guide

[Documentation index](document.md)

## Main modules

- `core/jobs.py`: source adapters, normalization, filtering, ranking, and report
  text
- `core/applications.py`: CV extraction, profile validation, and application
  draft preparation
- `core/pdf_report.py`: styled PDF generation
- `agents/coordinator.py`: source orchestration and artifact creation
- `app_gradio.py`: Gradio interface
- `app_streamlit.py`: Streamlit interface
- `run.sh`: explicit Gradio, Streamlit, and CLI launcher

## Adding a source

Implement an adapter returning the normalized dictionary produced by `_job()`,
then register it in `search_jobs()`. Preserve the authoritative posting and
application URL. Respect attribution, robots rules, caching guidance, and rate
limits. Do not bypass authenticated access controls.

## Validation

Test normalizers with mocked responses. Cover HTML cleanup, deduplication,
concept relevance, robotics evidence, education gates, location behavior,
recency, malformed dates, requirement extraction, source failures, URL
validation, and dashboard escaping.

Application tests should cover PDF/DOCX/text extraction, empty and scanned CVs,
profile validation, truthful overlap evidence, duplicate queue entries, and the
requirement for review before submission. UI changes should be executed through
Gradio import/startup checks and Streamlit's `AppTest` runtime.

Never commit CVs, applicant contact details, credentials, or generated local
reports.
