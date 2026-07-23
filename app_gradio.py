"""Gradio UI for live job search and review-first applications."""
import html
import queue
import threading
from pathlib import Path

import gradio as gr

from agents.coordinator import Coordinator
from core.applications import (
    ApplicantProfile, extract_cv_text, prepare_application, validate_profile,
)
from core.jobs import COUNTRIES, EDUCATION_LEVELS

EXAMPLES = [
    "AI robotics research scientist",
    "robot learning reinforcement learning",
    "computer vision robotics research engineer",
]

CSS = """
.gradio-container {max-width: 1240px !important; margin: auto !important;}
.hero {padding: 30px; border-radius: 24px; color: white; margin-bottom: 18px;
 background: radial-gradient(circle at top right,#7c3aed 0,#2563eb 35%,#0f172a 100%);
 box-shadow: 0 18px 50px rgba(37,99,235,.22)}
.hero h1 {font-size: 42px; margin: 0 0 7px}.hero p {opacity:.88;font-size:17px;margin:0}
.section-card {border:1px solid var(--border-color-primary);border-radius:20px;padding:8px}
.job-card {border:1px solid #dbeafe;border-radius:20px;padding:22px;margin:16px 0;
 background:linear-gradient(145deg,#fff,#f8faff);box-shadow:0 9px 28px rgba(30,64,175,.08)}
.job-meta {font-size:12px;color:#6366f1;letter-spacing:.08em;font-weight:700}
.job-card h2 {margin:7px 0}.job-facts {display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:15px 0}
.fact {background:#eef2ff;border-radius:12px;padding:11px}.apply-link {display:inline-block;background:#2563eb;
 color:white!important;padding:10px 16px;border-radius:10px;text-decoration:none!important;font-weight:700}
.platform-links {display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 20px}.platform-links a {padding:8px 12px;
 border:1px solid #c7d2fe;border-radius:999px;text-decoration:none!important}
.queue-card {border-left:4px solid #22c55e;background:#f0fdf4;padding:14px 17px;border-radius:12px;margin:10px 0}
@media(max-width:700px){.job-facts{grid-template-columns:1fr}.hero h1{font-size:32px}}
"""


def _valid_url(value: object) -> str:
    url = str(value or "")
    return url if url.startswith(("https://", "http://")) else ""


def _job_choices(jobs: list[dict]) -> list[str]:
    return [f"{i} · {job['title']} — {job['company']}" for i, job in enumerate(jobs, 1)]


def render_jobs(jobs, links, diagnostics=None):
    diagnostics = diagnostics or {}
    platforms = "".join(
        f"<a href='{html.escape(x['url'], quote=True)}' target='_blank'>{html.escape(x['name'])} ↗</a>"
        for x in links)
    cards = []
    for index, job in enumerate(jobs, 1):
        apply_url = _valid_url(job.get("apply_url"))
        education = next((values for key, values in job.get("concept_evidence", {}).items()
                          if key.startswith("education:")), [])
        requirements = "".join(f"<li>{html.escape(x)}</li>" for x in job.get("requirements", []))
        experience = "".join(f"<li>{html.escape(x)}</li>" for x in job.get("experience", []))
        apply_link = (f"<a class='apply-link' href='{html.escape(apply_url, quote=True)}' target='_blank'>"
                      "Open original listing ↗</a>") if apply_url else "<b>Application URL unavailable</b>"
        cards.append(
            "<article class='job-card'>"
            f"<div class='job-meta'>#{index} · {html.escape(job['source'].upper())} · "
            f"POSTED {job['age_days']} DAYS AGO</div>"
            f"<h2>{html.escape(job['title'])}</h2>"
            f"<p><b>{html.escape(job['company'])}</b> · 📍 {html.escape(job['location'])}</p>"
            "<div class='job-facts'>"
            f"<div class='fact'><small>SALARY</small><br><b>{html.escape(job['salary_display'])}</b></div>"
            f"<div class='fact'><small>TYPE</small><br><b>{html.escape(job.get('job_type') or 'Not disclosed')}</b></div>"
            f"<div class='fact'><small>EDUCATION</small><br><b>{html.escape(', '.join(education) or 'Not stated')}</b></div>"
            "</div>"
            f"<p><b>Match signals:</b> {html.escape(', '.join(job.get('matched_keywords', [])) or 'Close concept match')}</p>"
            f"<details><summary><b>Description</b></summary><p>{html.escape(job.get('description', '')[:1800])}</p></details>"
            f"<details><summary><b>Experience</b></summary><ul>{experience or '<li>Not explicitly stated</li>'}</ul></details>"
            f"<details><summary><b>Requirements</b></summary><ul>{requirements or '<li>None clearly extracted</li>'}</ul></details><br>"
            f"{apply_link}</article>")
    audit = ""
    if not jobs and diagnostics:
        audit = ("<div class='job-card'><h3>No verified matches</h3>"
                 f"<p>Missing concept: <b>{diagnostics.get('missing_requested_concept', 0)}</b> · "
                 f"Weak domain evidence: <b>{diagnostics.get('weak_domain_evidence', 0)}</b> · "
                 f"Too old: <b>{diagnostics.get('outside_age_window', 0)}</b> · "
                 f"Country mismatch: <b>{diagnostics.get('country_mismatch', 0)}</b></p></div>")
    return f"<div class='platform-links'>{platforms}</div>{audit}{''.join(cards) or '<p>No verified jobs found.</p>'}"


def run_research(query, country, city, max_age_days, education):
    empty_selector = gr.update(choices=[], value=None)
    if not str(query).strip():
        yield "Enter a job search query.", "", None, empty_selector, []
        return
    if not str(country).strip():
        yield "Country is required.", "", None, empty_selector, []
        return
    log_q, result_holder = queue.Queue(), {}

    def log(message):
        log_q.put(str(message))

    def worker():
        try:
            result_holder["result"] = Coordinator(log=log).run(
                query, country, city, int(max_age_days), education)
        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            log_q.put(None)

    threading.Thread(target=worker, daemon=True).start()
    lines = ["Searching live public job sources..."]
    while True:
        item = log_q.get()
        if item is None:
            break
        lines.append(item)
        yield "\n".join(lines), "", None, empty_selector, []
    if result_holder.get("error"):
        yield "\n".join(lines + ["ERROR: " + result_holder["error"]]), "", None, empty_selector, []
        return
    result = result_holder["result"]
    jobs = result.get("jobs", [])
    choices = _job_choices(jobs)
    selector = gr.update(choices=choices, value=choices[0] if choices else None)
    yield "\n".join(lines), render_jobs(jobs, result.get("search_links", []),
          result.get("diagnostics")), result.get("pdf_path"), selector, jobs


def _profile(name, email, phone, location, linkedin, portfolio,
             authorization, sponsorship, relocation, salary):
    profile = ApplicantProfile(name or "", email or "", phone or "", location or "",
                               linkedin or "", portfolio or "", authorization,
                               sponsorship, relocation, salary or "")
    errors = validate_profile(profile)
    if errors:
        raise ValueError(" ".join(errors))
    return profile


def _read_cv(cv_path):
    if not cv_path:
        raise ValueError("Upload a CV before preparing applications.")
    path = Path(cv_path)
    return extract_cv_text(path.name, path.read_bytes())


def render_queue(queue_items):
    if not queue_items:
        return "<p>No prepared applications yet.</p>"
    cards = []
    for draft in queue_items:
        job = draft["job"]
        url = _valid_url(job.get("apply_url"))
        link = (f"<a class='apply-link' href='{html.escape(url, quote=True)}' target='_blank'>Review and apply ↗</a>"
                if url else "Application URL unavailable")
        cards.append("<div class='queue-card'>"
                     f"<b>{html.escape(job['title'])}</b> · {html.escape(job['company'])}<br>"
                     f"CV match: {html.escape(', '.join(draft['matched_cv_terms']) or 'Review manually')}<br><br>{link}</div>")
    return "".join(cards)


def prepare_selected(selected, cv_path, name, email, phone, location, linkedin,
                     portfolio, authorization, sponsorship, relocation, salary,
                     jobs, queue_items):
    try:
        if not selected or not jobs:
            raise ValueError("Search for jobs and select one first.")
        profile = _profile(name, email, phone, location, linkedin, portfolio,
                           authorization, sponsorship, relocation, salary)
        cv_text = _read_cv(cv_path)
        index = int(str(selected).split(" · ", 1)[0]) - 1
        job = jobs[index]
        draft = prepare_application(job, profile, cv_text)
        queue_items = list(queue_items or [])
        key = _valid_url(job.get("apply_url")) or f"{job['company']}:{job['title']}"
        queue_items = [x for x in queue_items if (_valid_url(x['job'].get('apply_url')) or
                       f"{x['job']['company']}:{x['job']['title']}") != key]
        queue_items.append(draft)
        answers = "<h3>Suggested answers</h3><table>" + "".join(
            f"<tr><td><b>{html.escape(k)}</b></td><td>{html.escape(v)}</td></tr>"
            for k, v in draft["suggested_answers"].items()) + "</table>"
        status = f"✅ Prepared {html.escape(job['title'])} at {html.escape(job['company'])}. Review before applying."
        return status, draft["cover_letter"], answers, render_queue(queue_items), queue_items
    except Exception as exc:
        return f"⚠️ {html.escape(str(exc))}", "", "", render_queue(queue_items or []), queue_items or []


def prepare_all(cv_path, name, email, phone, location, linkedin, portfolio,
                authorization, sponsorship, relocation, salary, jobs, queue_items):
    try:
        if not jobs:
            raise ValueError("Search for jobs first.")
        profile = _profile(name, email, phone, location, linkedin, portfolio,
                           authorization, sponsorship, relocation, salary)
        cv_text = _read_cv(cv_path)
        queue_items = [prepare_application(job, profile, cv_text) for job in jobs]
        first = queue_items[0]
        answers = "<h3>Suggested answers</h3><table>" + "".join(
            f"<tr><td><b>{html.escape(k)}</b></td><td>{html.escape(v)}</td></tr>"
            for k, v in first["suggested_answers"].items()) + "</table>"
        return f"✅ Prepared {len(queue_items)} applications for review.", first["cover_letter"], answers, render_queue(queue_items), queue_items
    except Exception as exc:
        return f"⚠️ {html.escape(str(exc))}", "", "", render_queue(queue_items or []), queue_items or []


with gr.Blocks(title="Job Search") as demo:
    jobs_state, queue_state = gr.State([]), gr.State([])
    gr.HTML("<div class='hero'><h1>Job Search</h1><p>Recent, relevant openings with a review-first application assistant.</p></div>")
    with gr.Row():
        with gr.Column(scale=2, elem_classes="section-card"):
            gr.Markdown("## Find matching jobs")
            query_box = gr.Textbox(label="What job are you looking for?", lines=2,
                                   placeholder="e.g. AI robotics research scientist")
            with gr.Row():
                country_box = gr.Dropdown(COUNTRIES, value="United States",
                                          label="Country — required", filterable=True)
                city_box = gr.Textbox(label="City — optional preference", placeholder="e.g. Boston")
            with gr.Row():
                age_box = gr.Slider(1, 30, value=10, step=1, label="Maximum posting age")
                education_box = gr.Dropdown(EDUCATION_LEVELS, value="PhD", label="Education")
            gr.Examples(EXAMPLES, inputs=query_box)
            run_btn = gr.Button("Search Jobs", variant="primary", size="lg")
        with gr.Column(scale=1, elem_classes="section-card"):
            gr.Markdown("## Application profile")
            cv_file = gr.File(label="Upload CV (PDF, DOCX, TXT, MD)",
                              file_types=[".pdf", ".docx", ".txt", ".md"], type="filepath")
            with gr.Accordion("Applicant details", open=False):
                name = gr.Textbox(label="Full name *")
                email = gr.Textbox(label="Email *")
                phone = gr.Textbox(label="Phone")
                applicant_location = gr.Textbox(label="Current location")
                linkedin = gr.Textbox(label="LinkedIn URL")
                portfolio = gr.Textbox(label="Portfolio URL")
                authorization = gr.Dropdown(["Prefer not to answer", "Yes", "No"], value="Prefer not to answer", label="Authorized to work?")
                sponsorship = gr.Dropdown(["Prefer not to answer", "Yes", "No"], value="Prefer not to answer", label="Need sponsorship?")
                relocation = gr.Dropdown(["Prefer not to answer", "Yes", "No"], value="Prefer not to answer", label="Open to relocation?")
                salary = gr.Textbox(label="Salary expectation")
            gr.Markdown("Your CV and profile are used only in this local app session.")

    with gr.Accordion("Agent activity — click to show or hide", open=False):
        log_box = gr.Textbox(label="Live source activity", lines=12, interactive=False)

    gr.Markdown("## Live job results")
    jobs_box = gr.HTML()
    report_box = gr.File(label="Download styled PDF report")

    with gr.Group():
        gr.Markdown("## Prepare applications")
        gr.Markdown("Select a result, prepare a truthful draft, then review and submit on the employer's site.")
        selected_job = gr.Dropdown(label="Choose a job", choices=[])
        with gr.Row():
            prepare_btn = gr.Button("Prepare selected application", variant="primary")
            prepare_all_btn = gr.Button("Prepare all results")
        prep_status = gr.HTML()
        cover_letter = gr.Textbox(label="Editable cover-letter draft", lines=12)
        answers_box = gr.HTML()
        with gr.Accordion("Application review queue", open=True):
            queue_box = gr.HTML("<p>No prepared applications yet.</p>")

    search_outputs = [log_box, jobs_box, report_box, selected_job, jobs_state]
    run_btn.click(run_research,
                  [query_box, country_box, city_box, age_box, education_box],
                  search_outputs)
    profile_inputs = [cv_file, name, email, phone, applicant_location, linkedin,
                      portfolio, authorization, sponsorship, relocation, salary]
    prepare_btn.click(prepare_selected,
                      [selected_job, *profile_inputs, jobs_state, queue_state],
                      [prep_status, cover_letter, answers_box, queue_box, queue_state])
    prepare_all_btn.click(prepare_all,
                          [*profile_inputs, jobs_state, queue_state],
                          [prep_status, cover_letter, answers_box, queue_box, queue_state])

if __name__ == "__main__":
    demo.launch(inbrowser=True, css=CSS)
