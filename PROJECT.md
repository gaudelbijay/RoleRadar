# jobSearch Technical Design

jobSearch is a live job aggregation dashboard. A coordinator launches one
independent source agent for each documented public feed: Remotive, Jobicy,
Arbeitnow, and Remote OK. Results are normalized, deduplicated by company and
title, filtered for meaningful query coverage, and ranked.

Each normalized job contains its title, company, location, source, description,
date, type, salary when supplied, tags, extracted requirements, relevance data,
and original application URL. Requirement extraction is deterministic and uses
the posting text; it does not invent qualifications.

Gradio and Streamlit dashboards display cards, expandable requirements,
original-site Apply buttons, and targeted LinkedIn, Indeed, Glassdoor, and
Google Jobs searches. The project does not scrape authenticated pages or
submit applications. Reports and full JSON audits are saved under `reports/`.

## Architecture

```text
query
  └─ coordinator
      ├─ Remotive source agent
      ├─ Jobicy source agent
      ├─ Arbeitnow source agent
      └─ Remote OK source agent
           ↓
      normalize → deduplicate → relevance filter → rank
           ↓
      dashboard cards + Apply links + Markdown report + JSON audit
```

LinkedIn's official job APIs are gated partner products and do not provide an
unrestricted public search API. jobSearch therefore creates a targeted
LinkedIn search URL instead of using unsupported scraping.

## Roadmap

- Employer ATS integrations for Greenhouse and Lever
- Location, remote, salary, experience, and recency filters
- User profiles and resume-to-job matching
- Saved jobs and application tracking
- Feed caching and scheduled refresh
- Tests for every normalizer and ranking rule
