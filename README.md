# jobSearch — Comprehensive Live Job Dashboard

jobSearch queries documented public job feeds in parallel, ranks and
deduplicates real openings, extracts requirements from posting descriptions,
generates Markdown/JSON reports, and provides direct application links.

Searches use close concept matching across the full description while retaining
a robotics-domain gate when robotics is requested. Country is mandatory and
defaults to United States; city is an optional preference. Users choose the
maximum posting age, and results sort newest-first.

## Run

```bash
./run.sh                 # Gradio at http://127.0.0.1:7860
./run.sh streamlit       # Streamlit dashboard
```

Or run the CLI:

```bash
python cli.py --country "United States" --city Boston "robotics PhD"
```

## Live sources

Independent source agents query Remotive, Jobicy, Arbeitnow, Remote OK, plus
public LinkedIn, Indeed, and Google Jobs listings through JobSpy.
Results preserve the source, company, location, description,
publication information, salary when supplied, extracted requirements, and the
original application URL.

The dashboard also builds targeted searches for LinkedIn, Indeed, Glassdoor,
and Google Jobs. These platforms do not provide an unrestricted public
job-search API, so jobSearch links to their searches instead of scraping user
accounts or bypassing access controls.

## Output

Each run provides:

- Ranked and deduplicated live job cards
- Description excerpts and extracted requirements
- An **Apply on original site** button
- Major-platform search links
- A comprehensive Markdown report
- A JSON audit containing normalized job data

Reports are written under `reports/`.

## Documentation

Start with [`docs/document.md`](docs/document.md).
