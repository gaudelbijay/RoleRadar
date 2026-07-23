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
AI PhD robotics research scientist
```

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

The complete report appears below the cards and is saved under `reports/`.
It includes every ranked job, application link, requirements, description
excerpt, source coverage, platform searches, and feed errors.

## Command line

```bash
python cli.py --country "United States" --max-age 10 "AI PhD robotics"
```
