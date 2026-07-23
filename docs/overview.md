# Project Overview

[Documentation index](document.md)

jobSearch is a live job aggregation and analysis dashboard. Independent source
agents query public feeds and major job sites concurrently. The coordinator
normalizes, deduplicates, and ranks listings against the user's query.

For every ranked opening the application presents the title, company,
location, source, available salary/type/date fields, posting description,
requirements extracted directly from that description, and an external Apply
button.

Country is mandatory and defaults to United States. City is optional and used
as a preference rather than an exclusion. Matching recognizes related AI and
robotics concepts in descriptions. Users control maximum age; undated/stale
listings are removed and remaining jobs are shown newest-first.

LinkedIn, Indeed, Glassdoor, and Google Jobs are included as targeted searches.
LinkedIn, Indeed, and Google listings are also retrieved through the major-sites
source agent. Glassdoor remains a targeted search link because its scraper
location parsing is unreliable.
LinkedIn does not expose an unrestricted public job-search API, so the project
does not scrape authenticated pages or automate applications.

Reports are saved as Markdown, while a JSON audit preserves the normalized
results and source errors. Current public feeds focus heavily on remote and
European roles, so major-platform links are important for broader local search.
