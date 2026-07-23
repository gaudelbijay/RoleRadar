# Architecture

[Documentation index](document.md)

`Coordinator.run()` launches `core.jobs.search_jobs()`. Four source adapters
execute concurrently through `ThreadPoolExecutor`: Remotive, Jobicy,
Arbeitnow, and Remote OK.

Every adapter maps its feed to one stable job schema. The ranking stage removes
duplicates, applies AI/robotics concept groups, enforces country, uses city as a
soft preference, rejects undated or user-defined stale listings, sorts
newest-first, and extracts salary, experience, and requirement evidence.

The coordinator writes a Markdown report and a JSON audit. Gradio renders HTML
cards; Streamlit renders native containers and link buttons. Applications
always open the original source URL in a new page.

LinkedIn, Indeed, Glassdoor, and Google Jobs are discovery links rather than
scraped sources. The legacy Ollama modules remain available in the repository
but are not used by the live job-search path.
