# Job Search technical design

Job Search combines live job aggregation with review-first application
preparation. The same search and preparation modules serve two explicitly
launchable dashboards:

```bash
./run.sh gradio
./run.sh streamlit
```

## Data flow

```text
query + country + optional city + age + education
  └─ coordinator
      ├─ Remotive
      ├─ Jobicy
      ├─ Arbeitnow
      ├─ Remote OK
      └─ JobSpy: LinkedIn + Indeed + Google
           ↓
      normalize → deduplicate → evidence gates → newest-first rank
           ↓
      Gradio cards or Streamlit cards
           ├─ original application links
           ├─ Markdown + JSON audit + styled PDF
           └─ optional CV/profile preparation
                    ↓
              editable draft → applicant review → original employer form
```

A normalized job contains title, company, location, source, description,
publication date, type, salary evidence, tags, extracted requirements,
experience, relevance evidence, and an original application URL.

`core/applications.py` reads PDF, DOCX, TXT, and Markdown CVs and creates drafts
from CV/posting overlap and applicant-provided profile values. It does not
invent qualifications or submit forms. Gradio and Streamlit keep application
state separate from generated search reports.

LinkedIn, Indeed, Glassdoor, and Google targeted search URLs supplement feed
coverage. Authenticated pages are not scraped and platform restrictions are not
bypassed.

## Current limitations

- Public-source coverage and fields vary by site and time.
- Salary and experience remain undisclosed when the source omits them.
- Scanned image-only PDFs require OCR before upload.
- Employer login, consent, CAPTCHA, assessments, and custom screening questions
  require applicant review on the original site.
- Application tracking does not claim submission confirmation.

## Next improvements

- Saved-job and reviewed/submitted status tracking
- Optional local encrypted applicant profiles
- More normalizer and UI regression tests
- Feed caching and scheduled refresh
- Employer-authorized ATS integrations where credentials and custom questions
  are legitimately available
