# Reports and Auditing

[Documentation index](document.md)

Each search writes:

- `reports/report-YYYYMMDD-HHMMSS.md`
- `reports/audit-YYYYMMDD-HHMMSS.json`

The report includes ranked openings, original application links, posting
metadata, extracted requirements, description excerpts, major-platform search
links, limitations, and source failures.

The JSON audit contains the query, generation time, fetched count, normalized
ranked jobs, source errors, and platform links. Generated files should remain
local and should not be committed.
