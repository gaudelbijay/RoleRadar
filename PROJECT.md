# RoleRadar technical design

RoleRadar combines live aggregation, evidence-gated ranking, resume
intelligence, reporting, and review-first application preparation. Gradio and
Streamlit are explicit launch modes:

```bash
./run.sh gradio
./run.sh streamlit
```

## Data flow

```text
CV + optional GitHub/portfolio links
  └─ parallel resume intelligence agents
       └─ derived skills, roles, domains, education, provenance

query + country + optional city + age + education
  └─ coordinator
      ├─ Remotive                 ├─ Jobicy
      ├─ Arbeitnow                ├─ Remote OK
      └─ JobSpy: LinkedIn + Indeed + Google
           ↓
      normalize → deduplicate → hard eligibility gates
           ↓
      no CV: newest-first
      CV: resume fit + query relevance + city preference + recency
           ↓
      Gradio or Streamlit cards
           ├─ original application links
           ├─ Markdown + JSON audit + styled PDF
           └─ editable application drafts → applicant review
```

A normalized job contains title, company, location, source, description, date,
type, salary evidence, tags, extracted requirements, experience, relevance
evidence, and an original application URL.

`core.skill_taxonomy.py` supplies a broad cross-industry taxonomy rather than an
AI-only vocabulary. `core.resume_intelligence.py` extracts structured CV evidence, recognizes URLs,
uses public GitHub API metadata, and optionally reads protected public portfolio
pages. LinkedIn links are recognized without scraping. Name, email, phone,
photos, work authorization, sponsorship, relocation, and salary expectations
are not ranking features.

`core.applications.py` creates review drafts from CV/posting overlap and
applicant-supplied fields. It does not invent qualifications or submit forms.
Raw CV and fetched page text stay outside reports; derived match terms and fit
scores may be reported for explainability.

## Current limitations

- Public-source coverage and fields vary by site and time.
- GitHub unauthenticated requests are rate-limited.
- LinkedIn profile content is not fetched.
- Scanned image-only PDFs require OCR before upload.
- Resume fit is evidence overlap, not proof of qualification.
- Login, consent, CAPTCHA, assessments, and custom screening questions require
  applicant review on the original site.

## Next improvements

- Saved-job and reviewed/submitted status tracking
- Optional encrypted applicant profiles with explicit retention controls
- Broader tested skill aliases and multilingual resume parsing
- Feed caching and scheduled refresh
- Employer-authorized ATS integrations where credentials and custom questions
  are legitimately available
