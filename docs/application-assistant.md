# Application assistant

[Documentation index](document.md)

Both dashboards provide review-first application preparation. They never
submit an application without the applicant opening and reviewing the original
employer form.

## Gradio workflow

1. Launch with `./run.sh gradio`.
2. Upload a PDF, DOCX, TXT, or Markdown CV under **Application profile**.
3. Open **Applicant details** and enter at least a valid full name and email.
4. Search for jobs.
5. Select a job under **Prepare applications**, then select **Prepare selected
   application**; alternatively select **Prepare all results**.
6. Edit the cover-letter draft, inspect suggested answers, and use the review
   queue link to open the employer form.

The **Agent activity** section is collapsed by default and can be shown or
hidden at any time.

## Streamlit workflow

1. Launch with `./run.sh streamlit`.
2. Upload a CV in the sidebar.
3. Complete the applicant fields and select **Save applicant profile**.
4. Search for jobs.
5. Select **Prepare application** on a card or **Prepare all matching
   applications**.
6. Review drafts in **Application review queue** and open the original form.

Preparation buttons remain disabled until both the CV and profile are ready.

## Generated material

A prepared application contains CV terms overlapping the posting, a
job-specific editable cover-letter draft, reusable applicant answers, and the
original application URL. Drafts are deterministic and based on supplied CV and
posting text; qualifications are not invented.

## Privacy and limitations

CV and profile data remain in the active local dashboard process/session and
are excluded from Markdown, PDF, and JSON reports. Restarting the dashboard
clears application state. Do not expose a locally running dashboard publicly
when it contains personal information.

The assistant does not store job-platform credentials, bypass CAPTCHAs, answer
unknown legal questions, complete assessments, or claim successful submission.
LinkedIn and other restricted platforms open in their supported browser flow.
Employer-owned ATS API secrets are not applicant credentials and are not used.
