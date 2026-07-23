"""
Gradio UI for the multi-agent research system.

Run:  pip install gradio
      ollama pull gemma4
      python app_gradio.py
"""

import queue
import threading
import html

import gradio as gr

import config
from agents.coordinator import Coordinator
from core.jobs import COUNTRIES, EDUCATION_LEVELS

EXAMPLES = [
    "AI robotics research scientist",
    "robot learning reinforcement learning",
    "computer vision robotics research engineer",
]

def render_jobs(jobs, links, diagnostics=None, near_matches=None):
    diagnostics = diagnostics or {}
    near_matches = near_matches or []
    cards = []
    for job in jobs:
        apply_url = str(job.get("apply_url") or "")
        if not apply_url.startswith(("https://", "http://")):
            continue
        reqs = "".join(f"<li>{html.escape(r)}</li>" for r in job["requirements"])
        education_evidence = next(
            (values for key, values in job.get("concept_evidence", {}).items()
             if key.startswith("education:")),
            [],
        )
        cards.append(
            "<article style='border:1px solid #dbe4ff;border-radius:18px;padding:22px;"
            "margin:16px 0;background:linear-gradient(135deg,#ffffff,#f6f8ff);"
            "box-shadow:0 8px 24px rgba(22,54,120,.08)'>"
            f"<div style='font-size:12px;color:#526;letter-spacing:.08em'>"
            f"{html.escape(job['source'].upper())} · POSTED {job['age_days']} DAYS AGO</div>"
            f"<h2 style='margin:8px 0'>{html.escape(job['title'])}</h2>"
            f"<p style='font-size:17px'><b>{html.escape(job['company'])}</b> · "
            f"📍 {html.escape(job['location'])}</p>"
            f"<p><b>💰 Salary:</b> {html.escape(job['salary_display'])}</p>"
            f"<p><b>💼 Type:</b> {html.escape(job['job_type'] or 'Not disclosed')} · "
            f"<b>🎓 Education:</b> "
            f"{html.escape(', '.join(education_evidence) or 'Not stated')}</p>"
            f"<p><b>🎯 Relevance signals:</b> "
            f"{html.escape(', '.join(job['matched_keywords']) or 'close concept match')}</p>"
            f"<details><summary><b>Job description</b></summary>"
            f"<p>{html.escape(job['description'][:1400])}</p></details>"
            f"<details><summary><b>Experience requested ({len(job['experience'])})</b>"
            f"</summary><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in job['experience']) or '<li>Not explicitly stated</li>'}</ul></details>"
            f"<details><summary><b>All extracted requirements ({len(job['requirements'])})</b></summary>"
            f"<ul>{reqs or '<li>None clearly extracted</li>'}</ul></details><br>"
            f"<a href='{html.escape(apply_url, quote=True)}' target='_blank' "
            "style='background:#1769e0;color:white;padding:9px 15px;border-radius:8px;"
            "text-decoration:none'>Apply on original site ↗</a></article>")
    searches = " · ".join(
        f"<a href='{html.escape(x['url'], quote=True)}' target='_blank'>"
        f"Search {html.escape(x['name'])} ↗</a>" for x in links)
    audit = ""
    if not jobs and diagnostics:
        audit = (
            "<section style='background:#fff4e5;border:1px solid #ffcc80;"
            "border-radius:14px;padding:18px;margin:14px 0'>"
            "<h3>Why zero jobs?</h3>"
            f"<p>Missing requested concept: <b>{diagnostics.get('missing_requested_concept', 0)}</b><br>"
            f"Incidental robotics mention: <b>{diagnostics.get('weak_domain_evidence', 0)}</b><br>"
            f"Outside age window: <b>{diagnostics.get('outside_age_window', 0)}</b><br>"
            f"Country mismatch: <b>{diagnostics.get('country_mismatch', 0)}</b><br>"
            f"Missing date: <b>{diagnostics.get('missing_or_invalid_date', 0)}</b></p>"
            "<p>Counts can overlap because one listing may fail several gates.</p></section>"
        )
    return f"<p>{searches}</p>{audit}{''.join(cards) or '<p>No verified feed matches.</p>'}"


def run_research(query: str, country: str, city: str, max_age_days: int,
                 education: str):
    """Generator: streams live agent logs, then the final report."""
    if not query.strip():
        yield "Please enter a job search.", "", None
        return
    if not country.strip():
        yield "Country is required. City is optional.", "", None
        return

    log_q: queue.Queue = queue.Queue()
    result_holder = {}

    def log(msg: str):
        log_q.put(str(msg))

    def worker():
        try:
            result_holder["result"] = Coordinator(log=log).run(
                query, country, city, int(max_age_days), education
            )
        except Exception as exc:
            log(f"ERROR: {exc}")
            result_holder["result"] = {"report": f"Run failed: {exc}"}
        finally:
            log_q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    mode = "LIVE PUBLIC JOB FEEDS"
    lines = [f"Mode: {mode}"]
    while True:
        item = log_q.get()
        if item is None:
            break
        lines.append(item)
        yield "\n".join(lines), "", None

    result = result_holder.get("result", {})
    yield "\n".join(lines), render_jobs(
        result.get("jobs", []), result.get("search_links", []),
        result.get("diagnostics"), result.get("near_matches")), result.get("pdf_path")


with gr.Blocks(title="Job Search") as demo:
    gr.Markdown("# Job Search\nRecent matched jobs with salary, requirements, and Apply links.")
    query_box = gr.Textbox(label="What job are you looking for?", lines=2,
                           placeholder="e.g. AI robotics research scientist")
    with gr.Row():
        country_box = gr.Dropdown(
            choices=COUNTRIES, value="United States",
            label="Country — required", filterable=True
        )
        city_box = gr.Textbox(
            label="City — optional preference",
            placeholder="e.g. Boston (other US cities remain eligible)"
        )
        age_box = gr.Slider(
            minimum=1, maximum=30, value=10, step=1,
            label="Maximum posting age (days)"
        )
        education_box = gr.Dropdown(
            choices=EDUCATION_LEVELS, value="PhD",
            label="Education level"
        )
    gr.Examples(EXAMPLES, inputs=query_box)
    run_btn = gr.Button("Search Jobs", variant="primary")
    with gr.Row():
        log_box = gr.Textbox(label="Agent activity (live)", lines=14, interactive=False)
    jobs_box = gr.HTML(label="Live job results")
    report_box = gr.File(label="Download PDF report")
    run_btn.click(run_research,
                  inputs=[query_box, country_box, city_box, age_box, education_box],
                  outputs=[log_box, jobs_box, report_box])

if __name__ == "__main__":
    demo.launch()
