# Usage

[Documentation index](document.md)

## Choose an interface

Launch Gradio explicitly:

```bash
./run.sh gradio
```

Launch Streamlit explicitly:

```bash
./run.sh streamlit
```

Running `./run.sh` without a mode displays help instead of silently choosing an
interface.

### Gradio

Gradio keeps the application profile and CV upload visible in Gradio's native left sidebar. Search and application tools remain in the main workspace. **Agent
activity** is collapsed by default; select its heading to show or hide live
source logs.

Results use equal-height cards with scrollable **Role overview**, **Experience
sought**, and **What you’ll bring** panels. Long source text therefore does not
resize neighboring listings.

### Streamlit

Streamlit places CV upload and applicant details in the sidebar. Search results
remain available while applications are prepared. A job card changes to
**Prepared ✓** after it is added to the review queue.

## Search controls

- Choose **Jobs** or **Internships**. Jobs is the default. Internship mode searches the requested role with dedicated intern terminology and only
  accepts listings with internship, intern, co-op, or trainee evidence; Jobs mode
  excludes those listings.
- Enter a focused role or domain, such as `AI robotics research scientist`.
- Select a country. Country is mandatory and defaults to United States.
- Optionally enter a city. It improves ranking but does not exclude other cities
  in the selected country.
- Choose a maximum posting age from 1–30 days.
- Choose a minimum annual salary from 0–300,000 in the listing currency. The default is 100,000. Listings pass only when their disclosed annualized maximum reaches the threshold; set it to 0 to include undisclosed salaries.
- Choose High School, Bachelor's, Master's, or PhD. PhD is the default.

When a CV is uploaded, resume intelligence runs automatically during search.
Eligible jobs are ordered by estimated resume fit, query relevance, optional
city preference, and recency. GitHub enrichment is enabled by default; public
portfolio analysis is opt-in. Matching still considers related concepts across
the full posting. Robotics searches
still require meaningful robotics-domain evidence. Undated and stale jobs are
removed, and remaining results are ordered newest-first.

## Prepare and apply

Upload a PDF, DOCX, TXT, or Markdown CV and complete the required name and email
fields. Prepare a selected job or all matched jobs. Review the generated cover
letter and profile answers before opening the original application page.

The employer site remains authoritative. Login, consent, CAPTCHA, assessments,
work-authorization wording, and posting-specific questions must be checked by
the applicant. The app does not collect platform credentials or report an
application as submitted.

## Reports

Download the styled PDF after a search. It contains matched jobs, dates, source,
salary when available, extracted requirements, descriptions, and clickable
application links. Application-profile data and CV contents are excluded.

## Command line

```bash
./run.sh cli --country "United States" --max-age 10 \
  --education PhD --minimum-salary 100000 "AI robotics"
```
