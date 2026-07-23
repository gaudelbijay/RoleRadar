# Usage

[Documentation index](document.md)

## Start the dashboard

```bash
./run.sh
```

For Streamlit:

```bash
./run.sh streamlit
```

Enter a focused query such as:

```text
AI robotics research scientist
```

Select education independently: High School, Bachelor's, Master's, or PhD.
PhD is the default. A listing must contain evidence supporting the selected
education level; the dashboard does not infer it from seniority alone.

Useful alternatives include `robot learning PhD`, `robotics perception
engineer`, and `computer vision robotics`.

Country is selected from a dropdown and defaults to United States. City is an
optional preference and never excludes otherwise relevant jobs in that country.
Use the posting-age control to choose how recent results must be.

## Read and apply

Matching uses closely related concepts across the title and full description,
not literal word-for-word filtering. Robotics searches still require robotics
domain evidence. Undated or older-than-your-selected-age jobs are removed and
newest listings appear first. Open a card to inspect salary evidence,
experience evidence, and extracted requirements. Select
**Apply on original site** to open the authoritative job-board or employer
page. The dashboard does not submit applications or collect credentials.

Use the LinkedIn, Indeed, Glassdoor, and Google Jobs buttons when the public
feeds have limited coverage. Those buttons preserve your query and open the
platform's own search experience.

## Reports

Use **Download PDF Report** after a search. The styled PDF includes each matched
job's salary, education and experience evidence, requirements, description,
source, posting date, and clickable application link.

## Command line

```bash
python cli.py --country "United States" --max-age 10 \
  --education PhD "AI robotics"
```
