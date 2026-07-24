# Project overview

[Documentation index](document.md)

Job Search is a live job aggregation, ranking, reporting, and application-
preparation dashboard. Users can explicitly launch either Gradio or Streamlit:

```bash
./run.sh gradio
./run.sh streamlit
```

Parallel source agents query Remotive, Jobicy, Arbeitnow, Remote OK, LinkedIn,
Indeed, and Google. Results are normalized and deduplicated before ranking.
Glassdoor is provided as a targeted search link because its scraper location
handling is unreliable.

Every ranked card shows the title, company, location, source, posting date,
available salary and employment type, matching signals, education evidence,
experience, requirements, description, and original application link.

Search type defaults to Jobs; Internships is optional and uses a dedicated
internship evidence gate. Country is mandatory and defaults to United States. City is optional and used
as a preference. Without a CV, accepted jobs are newest-first. With resume
intelligence, eligible jobs are personalized by evidence and recency. Users choose a 1–30 day posting-age limit and an education
level from High School, Bachelor's, Master's, or PhD. Matching recognizes
related AI and robotics concepts while keeping meaningful domain evidence.


Both dashboards accept PDF, DOCX, TXT, and Markdown CVs. Resume evidence is categorized across software, engineering, science, healthcare,
finance, business, legal, education, creative, operations, trades, and other
industries. Parallel resume and public-link agents personalize eligible job ordering before
the dashboards prepare application
drafts for review. They do not automate platform login, CAPTCHA, assessments,
unknown screening questions, or final submission.

Each search creates local Markdown, PDF, and JSON artifacts. The PDF is the
user-facing download; the JSON audit preserves normalized evidence and source
errors. Applicant profile and CV data are excluded from every report.
