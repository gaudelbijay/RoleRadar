# Job Search

Job Search retrieves current openings from public feeds and major job sites,
deduplicates and ranks them, extracts salary and requirement evidence, and
presents them in Gradio or Streamlit. Both dashboards include a review-first CV
application assistant and downloadable PDF reports.

Searches use concept-aware matching across titles and descriptions. Robotics
queries retain a robotics-domain gate without requiring one exact phrase.
Search type defaults to Jobs, with an optional Internships mode that filters for
intern, internship, co-op, or trainee listings. Country is mandatory and defaults
to the United States; city is an optional
ranking preference. Users choose the maximum posting age, education level, and minimum annual salary. The salary threshold defaults to 100,000; setting it to zero includes listings without usable salary evidence.
Without a CV, results are newest-first. With a CV, eligible jobs are ordered by estimated resume fit, query relevance, optional city preference, and recency.

## Launch a dashboard

Choose the interface explicitly:

```bash
./run.sh gradio
./run.sh streamlit
```

- Gradio normally opens at `http://127.0.0.1:7864` and offers styled cards,
  collapsible agent activity, CV upload, application preparation, and a review
  queue.
- Streamlit normally opens at `http://localhost:8501` and offers native job
  cards, a sidebar applicant profile, CV upload, application preparation, and a
  review queue.

Show launcher help with `./run.sh help`. Run without a dashboard with:

```bash
./run.sh cli --country "United States" --city Boston --education PhD "robotics"
```

## Live sources

Parallel source agents query Remotive, Jobicy, Arbeitnow, Remote OK, and public
LinkedIn/Indeed/Google listings through JobSpy. Glassdoor is provided as a
targeted search link because its public scraping path is unreliable. Original
source and employer application URLs are preserved.

## Resume-personalized ranking

An uploaded CV can influence job ordering. A broad occupational taxonomy covers
356 skills across 21 categories and 32 domains—not only AI or robotics. Parallel
agents extract resume skills
and public URLs, enrich public GitHub evidence, recognize LinkedIn URLs without
scraping them, and optionally analyze protected public portfolio pages—including
profile websites and repository homepages discovered through GitHub. Country,
recency, education, and domain requirements remain mandatory.

## Application workflow

Upload a PDF, DOCX, TXT, or Markdown CV, provide the required applicant fields,
and prepare one or all matched applications. The assistant produces an
editable cover-letter draft, reusable profile answers, CV-to-job evidence, and a review queue. When a CV is present, parallel resume and public-link
agents extract evidence and rerank otherwise eligible jobs by estimated fit.
Final submission happens on the original employer site.
Credentials, CAPTCHAs, assessments, consent, and unknown screening questions
are not automated.

## Output

Each search provides ranked job cards, extracted requirements and experience,
salary when disclosed, major-platform search links, an original-site Apply
link, a styled PDF report, and a local JSON audit. Generated files are written
to `reports/` and ignored by Git.

Start with the [documentation index](docs/document.md).
