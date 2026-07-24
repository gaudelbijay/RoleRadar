# Reports and auditing

[Documentation index](document.md)

Each successful search writes timestamped local artifacts:

- `reports/report-YYYYMMDD-HHMMSS.md`
- `reports/report-YYYYMMDD-HHMMSS.pdf`
- `reports/audit-YYYYMMDD-HHMMSS.json`

Both dashboards offer the styled PDF as the user-facing download. It contains
ranked openings, source metadata, posting dates, available salary, selected minimum-salary evidence, education
and experience evidence, extracted requirements, description excerpts,
platform searches, and clickable original application links.

The JSON audit preserves query controls, generation time, fetched count,
normalized ranked jobs, source errors, gate diagnostics, and platform links.
The Markdown file is the text report used to build related output.

Raw CV contents, fetched public-page text, applicant contact data, generated cover
letters, and reusable application answers are not written into these reports.
Derived skill matches and estimated fit scores may be included to explain
personalized ordering. Generated report files
are ignored by Git and should remain local unless deliberately shared.
