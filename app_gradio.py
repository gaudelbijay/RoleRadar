"""Gradio UI for live job search and review-first applications."""
import html
import os
import queue
import threading
from pathlib import Path

import gradio as gr

from agents.coordinator import Coordinator
from core.applications import (
    ApplicantProfile, extract_cv_text, prepare_application, validate_profile,
)
from core.jobs import COUNTRIES, EDUCATION_LEVELS
from core.company_people import research_all_companies, research_company
from core.resume_intelligence import analyze_candidate

EXAMPLES = [
    "AI robotics research scientist",
    "robot learning reinforcement learning",
    "computer vision robotics research engineer",
]

CSS = """
.gradio-container {max-width:1440px!important;margin:auto!important;padding-bottom:70px}
.hero {padding:30px;border-radius:24px;color:#fff!important;margin-bottom:18px;background:radial-gradient(circle at top right,#7c3aed 0,#2563eb 35%,#0f172a 100%);box-shadow:0 18px 50px rgba(37,99,235,.22)}
.hero h1,.hero p {color:#fff!important}.hero h1 {font-size:42px;margin:0 0 7px}.hero p {opacity:.92;font-size:17px;margin:0}
.section-card {border:1px solid var(--border-color-primary);border-radius:22px;padding:16px}
.profile-panel {position:sticky;top:16px;align-self:flex-start;background:var(--block-background-fill)}
.profile-note {font-size:13px;opacity:.78;line-height:1.5}
.jobs-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:stretch}
.job-card {color:#0f172a!important;border:1px solid #bfdbfe;border-radius:22px;padding:22px;margin:0;height:850px;display:flex;flex-direction:column;overflow:hidden;background:linear-gradient(145deg,#fff,#f8faff);box-shadow:0 10px 30px rgba(30,64,175,.10)}
.job-card h2,.job-card h3,.job-card p,.job-card b,.job-card li,.job-card small,.job-card div {color:#0f172a!important}
.job-meta {font-size:12px;color:#6366f1!important;letter-spacing:.08em;font-weight:700}
.job-card h2 {margin:7px 0;line-height:1.15;min-height:52px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.company-line {height:48px;margin:0 0 10px!important;overflow:hidden}
.job-facts {display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:10px 0}
.fact {color:#0f172a!important;background:#e0e7ff;border:1px solid #c7d2fe;border-radius:12px;padding:11px;min-width:0}
.fact b {font-size:13px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.resume-fit {display:grid;grid-template-columns:78px 1fr;gap:10px;align-items:center;background:#ecfeff;border:1px solid #a5f3fc;border-radius:13px;padding:10px;margin-bottom:10px;height:74px;overflow:hidden}
.fit-score {font-size:24px;font-weight:900;color:#0e7490!important;text-align:center}.fit-copy {font-size:12px;line-height:1.4;overflow:hidden}.fit-copy b {color:#155e75!important}
.match-strip {background:#f5f3ff;border:1px solid #ddd6fe;border-radius:12px;padding:9px 11px;height:43px;overflow:hidden;margin:0 0 10px!important;font-size:13px}
.evidence-stack {display:grid;grid-template-rows:190px 160px;gap:10px;min-height:360px;flex:1}
.evidence-row {display:grid;grid-template-columns:1fr 1fr;gap:10px;min-height:0}
.evidence-panel {background:#fff;border:1px solid #dbeafe;border-radius:14px;padding:13px;overflow:auto;scrollbar-width:thin;box-shadow:inset 0 1px 0 rgba(255,255,255,.8)}
.evidence-panel.overview {background:#f8fafc}.evidence-panel.experience {background:#f0f9ff}.evidence-panel.requirements {background:#f0fdf4}
.panel-title {font-size:12px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;margin-bottom:8px;color:#334155!important;position:sticky;top:-13px;padding:10px 0 6px;z-index:1}
.overview .panel-title {background:#f8fafc}.experience .panel-title {background:#f0f9ff}.requirements .panel-title {background:#f0fdf4}
.evidence-panel p,.evidence-panel li {font-size:13px;line-height:1.52;margin-top:0}.evidence-panel ul {margin:0;padding-left:18px}.evidence-panel li {margin-bottom:6px}
.job-action {padding-top:13px;margin-top:auto}
.apply-link {display:inline-block;background:#1d4ed8;color:white!important;padding:10px 16px;border-radius:10px;text-decoration:none!important;font-weight:700}
.platform-links {display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 20px}.platform-links a {color:#1e3a8a!important;background:#eff6ff;padding:8px 12px;border:1px solid #93c5fd;border-radius:999px;text-decoration:none!important;font-weight:650}
.queue-card {color:#052e16!important;border-left:4px solid #16a34a;background:#dcfce7;border-top:1px solid #86efac;border-right:1px solid #86efac;border-bottom:1px solid #86efac;padding:14px 17px;border-radius:12px;margin:10px 0}.queue-card b,.queue-card br {color:#052e16!important}
.feature-panel {background:linear-gradient(145deg,#ffffff,#f8fafc)!important;border:1px solid #cbd5e1!important;border-radius:18px!important;padding:18px!important;box-shadow:0 8px 24px rgba(15,23,42,.06)}
.feature-panel h2 {color:#0f172a!important;margin-bottom:4px!important}.feature-panel p {color:#475569!important}.feature-panel .empty-research {background:#f1f5f9;border:1px dashed #94a3b8;border-radius:12px;padding:14px 16px;color:#475569!important;margin-top:12px}
.people-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.people-company {border:1px solid #cbd5e1;border-radius:16px;padding:16px;background:#fff}.company-contact {background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px;margin:10px 0;font-size:12px}.company-contact a,.person-links a {color:#1d4ed8!important}.person-row {border-top:1px solid #e2e8f0;padding:13px 0}.person-title {font-weight:650;color:#334155!important}.person-bio {font-size:12px;line-height:1.45;margin:8px 0!important;color:#475569!important}.person-links {font-size:12px}.manager-badge {display:inline-block;background:#fef3c7;color:#92400e!important;border:1px solid #f59e0b;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:800}.leader-badge {display:inline-block;background:#e0f2fe;color:#075985!important;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:700}
.no-match-card {color:#0f172a!important;border:1px solid #bfdbfe;border-radius:18px;padding:24px;background:linear-gradient(145deg,#fff,#f8faff);box-shadow:0 10px 30px rgba(30,64,175,.08)}
.no-match-card h3,.no-match-card p,.no-match-card b {color:#0f172a!important}
.searching-state {display:flex;align-items:center;gap:16px;padding:22px 24px;margin:8px 0 20px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(135deg,#eff6ff,#f5f3ff);box-shadow:0 10px 26px rgba(37,99,235,.10);color:#172554!important}
.searching-spinner {width:30px;height:30px;flex:0 0 30px;border:4px solid #bfdbfe;border-top-color:#4f46e5;border-radius:50%;animation:jobsearch-spin .8s linear infinite}
.searching-copy b,.searching-copy span {color:#172554!important}.searching-copy b {display:block;font-size:16px;margin-bottom:3px}.searching-copy span {font-size:13px;opacity:.78}
@keyframes jobsearch-spin {to {transform:rotate(360deg)}}
@media(max-width:1050px){.jobs-grid{grid-template-columns:1fr}.profile-panel{position:static}}
@media(max-width:700px){.job-facts,.evidence-row{grid-template-columns:1fr}.job-card{height:1030px}.evidence-stack{grid-template-rows:230px 320px}.hero h1{font-size:32px}}
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
        resume_fit = job.get("resume_fit")
        if resume_fit:
            fit_terms = ", ".join(resume_fit.get("matched_skills", [])[:4]) or "Limited direct skill overlap"
            fit_html = (
                f"<div class=\"resume-fit\"><div class=\"fit-score\">{resume_fit['score']}%<br><small>FIT</small></div>"
                f"<div class=\"fit-copy\"><b>Resume evidence</b><br>{html.escape(fit_terms)}</div></div>"
            )
        else:
            fit_html = ""
        cards.append(
            "<article class='job-card'>"
            f"<div class='job-meta'>#{index} · {html.escape(job['source'].upper())} · "
            f"POSTED {job['age_days']} DAYS AGO</div>"
            f"<h2>{html.escape(job['title'])}</h2>"
            f"<p class='company-line'><b>{html.escape(job['company'])}</b><br>"
            f"📍 {html.escape(job['location'])}</p>"
            "<div class='job-facts'>"
            f"<div class='fact'><small>SALARY</small><br><b>{html.escape(job['salary_display'])}</b></div>"
            f"<div class='fact'><small>TYPE</small><br><b>{html.escape(job.get('job_type') or 'Not disclosed')}</b></div>"
            f"<div class='fact'><small>EDUCATION</small><br><b>{html.escape(', '.join(education) or 'Not stated')}</b></div>"
            "</div>"
            f"<p class='match-strip'><b>✦ Why it matches:</b> "
            f"{html.escape(', '.join(job.get('matched_keywords', [])) or 'Close concept match')}</p>"
            f"{fit_html}"
            "<div class='evidence-stack'>"
            "<section class='evidence-panel overview'><div class='panel-title'>📋 Role overview</div>"
            f"<p>{html.escape(job.get('role_overview', '')) or 'The source did not provide a role overview.'}</p></section>"
            "<div class='evidence-row'>"
            "<section class='evidence-panel experience'><div class='panel-title'>🧭 Experience sought</div>"
            f"<ul>{experience or '<li>The posting does not state a specific experience requirement.</li>'}</ul></section>"
            "<section class='evidence-panel requirements'><div class='panel-title'>✓ What you’ll bring</div>"
            f"<ul>{requirements or '<li>No explicit requirements were available in the source text.</li>'}</ul></section>"
            "</div></div>"
            f"<div class='job-action'>{apply_link}</div></article>")
    audit = ""
    if not jobs and diagnostics:
        audit = ("<div class='no-match-card'><h3>No verified matches</h3>"
                 f"<p>Salary missing: <b>{diagnostics.get('salary_missing_or_unusable', 0)}</b> · "
                 f"Below minimum: <b>{diagnostics.get('salary_below_minimum', 0)}</b> · "
                 f"Wrong search type: <b>{diagnostics.get('search_type_mismatch', 0)}</b> · "
                 f"Missing concept: <b>{diagnostics.get('missing_requested_concept', 0)}</b> · "
                 f"Weak domain evidence: <b>{diagnostics.get('weak_domain_evidence', 0)}</b> · "
                 f"Too old: <b>{diagnostics.get('outside_age_window', 0)}</b> · "
                 f"Country mismatch: <b>{diagnostics.get('country_mismatch', 0)}</b></p></div>")
    card_grid = f"<div class='jobs-grid'>{''.join(cards)}</div>" if cards else "<p>No verified jobs found.</p>"
    return f"<div class='platform-links'>{platforms}</div>{audit}{card_grid}"


def render_searching(message="Starting search agents..."):
    safe_message = html.escape(str(message))
    return ("<div class=\"searching-state\" role=\"status\" aria-live=\"polite\">"
            "<div class=\"searching-spinner\" aria-hidden=\"true\"></div>"
            "<div class=\"searching-copy\"><b>Searching for matching jobs</b>"
            f"<span>{safe_message}</span></div></div>")


def render_resume_profile(profile):
    if not profile:
        return "<div class=\"queue-card\">Upload a CV to personalize job ranking.</div>"
    categories = profile.get("skill_categories", {})
    category_html = "".join(
        f"<div><b>{html.escape(category)}:</b> {html.escape(', '.join(values[:8]))}</div>"
        for category, values in list(categories.items())[:8]
    ) or "No categorized skills detected"
    sources = " · ".join(
        f"{item.get('kind', 'link').title()}: {item.get('status', 'unknown')}"
        for item in profile.get("sources", [])
    ) or "CV only"
    warnings = "<br>".join(html.escape(x) for x in profile.get("warnings", []))
    warning_html = f"<p><b>Notes:</b><br>{warnings}</p>" if warnings else ""
    return ("<div class=\"queue-card\"><b>Resume intelligence ready</b><br>"
            f"{html.escape(profile.get('summary', ''))}<br><br>"
            f"<b>Categorized evidence:</b>{category_html}<br>"
            f"<b>Public links:</b> {html.escape(sources)}{warning_html}</div>")


def run_research(query, search_type, country, city, max_age_days, education, minimum_salary, cv_path,
                 linkedin_url, portfolio_url, use_github, use_portfolios):
    empty_selector = gr.update(choices=[], value=None)
    empty_profile = render_resume_profile(None)
    empty_report = gr.update(value=None, visible=False)
    empty_people = '<div class="empty-research">Technical staff will appear here after a successful search.</div>'
    if not str(query).strip():
        yield "Enter a job search query.", "", empty_report, empty_selector, [], empty_profile, empty_people
        return
    if not str(country).strip():
        yield "Country is required.", "", empty_report, empty_selector, [], empty_profile, empty_people
        return
    log_q, result_holder = queue.Queue(), {}

    def log(message):
        log_q.put(str(message))

    def worker():
        try:
            candidate = None
            if cv_path:
                cv_text = _read_cv(cv_path)
                candidate = analyze_candidate(
                    cv_text, [linkedin_url, portfolio_url], bool(use_github),
                    bool(use_portfolios), log=log)
            result_holder["candidate"] = candidate
            result_holder["result"] = Coordinator(log=log).run(
                query, country, city, int(max_age_days), education, int(minimum_salary),
                resume_profile=candidate, search_type=search_type)
        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            log_q.put(None)

    threading.Thread(target=worker, daemon=True).start()
    lines = ["Searching live public job sources..."]
    yield "\n".join(lines), render_searching(), empty_report, empty_selector, [], empty_profile, empty_people
    while True:
        item = log_q.get()
        if item is None:
            break
        lines.append(item)
        yield "\n".join(lines), render_searching(item), empty_report, empty_selector, [], empty_profile, empty_people
    if result_holder.get("error"):
        error_message = html.escape(result_holder["error"])
        error_html = f"<div class=\"queue-card\"><b>Search stopped</b><br>{error_message}</div>"
        yield "\n".join(lines + ["ERROR: " + result_holder["error"]]), error_html, empty_report, empty_selector, [], empty_profile, empty_people
        return
    result = result_holder["result"]
    candidate = result_holder.get("candidate")
    jobs = result.get("jobs", [])
    choices = _job_choices(jobs)
    selector = gr.update(choices=choices, value=choices[0] if choices else None)
    job_html = render_jobs(jobs, result.get("search_links", []), result.get("diagnostics"))
    report_update = gr.update(value=result.get("pdf_path"), visible=bool(result.get("pdf_path")))
    profile_html = render_resume_profile(candidate)
    people_loading = render_searching("Jobs found. Reading official company staff pages...")
    yield "\n".join(lines), job_html, report_update, selector, jobs, profile_html, people_loading
    people_results = research_all_companies(jobs) if jobs else []
    yield ("\n".join(lines + [f"Technical staff research completed for {len(people_results)} companies."]),
           job_html, report_update, selector, jobs, profile_html,
           render_company_people(people_results))



def render_company_people(results):
    if not results:
        return '<div class="empty-research">Select a job above, then choose a research action.</div>'
    cards = []
    for result in results:
        official = _valid_url(result.get("official_url"))
        heading = html.escape(result.get("company") or "Company")
        if official:
            heading = (f'<a href="{html.escape(official, quote=True)}" target="_blank">'
                       f'{heading} ↗</a>')
        contact_bits = []
        for email_address in result.get("generic_emails", []):
            safe_email = html.escape(email_address)
            contact_bits.append(f'<a href="mailto:{safe_email}">✉ {safe_email}</a>')
        for contact_url in result.get("contact_urls", [])[:3]:
            safe_url = _valid_url(contact_url)
            if safe_url:
                contact_bits.append(
                    f'<a href="{html.escape(safe_url, quote=True)}" target="_blank">Careers / contact ↗</a>'
                )
        contact_html = (
            '<div class="company-contact"><b>Public company contact</b><br>'
            + " · ".join(contact_bits) + "</div>"
            if contact_bits else ""
        )
        rows = []
        for person in result.get("people", []):
            badge = ('<span class="manager-badge">Hiring manager — explicitly identified</span>'
                     if person.get("hiring_manager") else
                     '<span class="leader-badge">Relevant technical staff</span>')
            profile = _valid_url(person.get("official_profile_url"))
            name = html.escape(person.get("name") or "Unknown")
            if profile:
                name = (f'<a href="{html.escape(profile, quote=True)}" target="_blank">'
                        f'{name} ↗</a>')
            public_links = []
            if profile:
                public_links.append(f'<a href="{html.escape(profile, quote=True)}" target="_blank">Official profile ↗</a>')
            for item in person.get("public_links", []):
                link_url = _valid_url(item.get("url"))
                if link_url:
                    public_links.append(
                        f'<a href="{html.escape(link_url, quote=True)}" target="_blank">'
                        f'{html.escape(item.get("label") or "Public link")} ↗</a>'
                    )
            source = _valid_url(person.get("source_url"))
            if source:
                public_links.append(f'<a href="{html.escape(source, quote=True)}" target="_blank">Source ↗</a>')
            bio = html.escape(person.get("bio") or "No public biography was provided on the source page.")
            links_html = " · ".join(public_links)
            rows.append(
                f'<div class="person-row">{badge}<br><b>{name}</b><br>'
                f'<span class="person-title">{html.escape(person.get("title") or "Title not stated")}</span><br>'
                f'<small>{html.escape(person.get("technical_area") or "Technical")}</small>'
                f'<p class="person-bio">{bio}</p><div class="person-links">{links_html}</div></div>'
            )
        content = "".join(rows) or '<p>No technical staff were explicitly listed on the scanned official pages.</p>'
        cards.append(
            f'<section class="people-company"><h3>{heading}</h3>'
            f'<p><small>{result.get("pages_scanned", 0)} official page(s) scanned · '
            f'{html.escape(result.get("note") or "")}</small></p>{contact_html}{content}</section>'
        )
    return f'<div class="people-grid">{"".join(cards)}</div>'


def research_selected_ui(selected, jobs):
    if not selected or not jobs:
        return '<div class="no-match-card">Search for jobs and choose one first.</div>'
    index = int(str(selected).split(" · ", 1)[0]) - 1
    return render_company_people([research_company(jobs[index])])


def research_all_ui(jobs):
    if not jobs:
        return '<div class="no-match-card">Search for jobs first.</div>'
    return render_company_people(research_all_companies(jobs))


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
    with gr.Sidebar(label="Application profile", open=True, width=350,
                    position="left", elem_classes="profile-sidebar"):
        gr.Markdown("## Application profile")
        gr.Markdown("Add your details once, then prepare any matched job.",
                    elem_classes="profile-note")
        cv_file = gr.File(label="Upload CV (PDF, DOCX, TXT, MD)",
                          file_types=[".pdf", ".docx", ".txt", ".md"],
                          type="filepath", height=150)
        name = gr.Textbox(label="Full name *")
        email = gr.Textbox(label="Email *")
        with gr.Row():
            phone = gr.Textbox(label="Phone")
            applicant_location = gr.Textbox(label="Current location")
        linkedin = gr.Textbox(label="LinkedIn URL")
        portfolio = gr.Textbox(label="Portfolio URL")
        use_github = gr.Checkbox(value=True, label="Analyze public GitHub evidence")
        use_portfolios = gr.Checkbox(
            value=False, label="Analyze public portfolio pages (opt in)")
        resume_box = gr.HTML(
            "<div class=\"queue-card\">Upload a CV, then search to run resume intelligence.</div>")
        authorization = gr.Dropdown(
            ["Prefer not to answer", "Yes", "No"], value="Prefer not to answer",
            label="Authorized to work?")
        sponsorship = gr.Dropdown(
            ["Prefer not to answer", "Yes", "No"], value="Prefer not to answer",
            label="Need sponsorship?")
        relocation = gr.Dropdown(
            ["Prefer not to answer", "Yes", "No"], value="Prefer not to answer",
            label="Open to relocation?")
        salary = gr.Textbox(label="Salary expectation")
        gr.Markdown("🔒 Used only in this app session. Never added to reports.",
                    elem_classes="profile-note")

    gr.HTML("<div class='hero'><h1 style='color:#fff!important;-webkit-text-fill-color:#fff!important'>Job Search</h1><p style='color:#fff!important;-webkit-text-fill-color:#fff!important'>Recent, relevant openings with a review-first application assistant.</p></div>")
    with gr.Column(elem_classes="section-card"):
        gr.Markdown("## Find matching jobs")
        query_box = gr.Textbox(label="What job are you looking for?", lines=2,
                               placeholder="e.g. financial analyst, registered nurse, robotics engineer")
        search_type = gr.Radio(["Jobs", "Internships"], value="Jobs",
                               label="Search type")
        with gr.Row():
            country_box = gr.Dropdown(COUNTRIES, value="United States",
                                      label="Country — required", filterable=True)
            city_box = gr.Textbox(label="City — optional preference", placeholder="e.g. Boston")
        with gr.Row():
            age_box = gr.Slider(1, 30, value=10, step=1, label="Maximum posting age")
            education_box = gr.Dropdown(EDUCATION_LEVELS, value="PhD", label="Education")
        salary_box = gr.Slider(
            0, 300_000, value=100_000, step=5_000,
            label="Minimum annual salary (listing currency)",
            info="Only jobs with a disclosed annualized maximum at or above this amount are shown. Set to 0 to include undisclosed salaries.",
        )
        gr.Examples(EXAMPLES, inputs=query_box)
        run_btn = gr.Button("Search Jobs", variant="primary", size="lg")

    with gr.Accordion("Agent activity — click to show or hide", open=False):
        log_box = gr.Textbox(label="Live source activity", lines=12, interactive=False)

    gr.Markdown("## Live job results")
    jobs_box = gr.HTML()
    report_box = gr.File(label="Download styled PDF report", visible=False)

    with gr.Group(elem_classes="feature-panel"):
        gr.Markdown("## Choose a result")
        selected_job = gr.Dropdown(label="Job opening", choices=[], info="This selection is used for company research and application preparation.")

    with gr.Group(elem_classes="feature-panel"):
        gr.Markdown("## Public technical staff")
        gr.Markdown("Read official public company pages on demand. A person is marked as a hiring manager only when a public source says so explicitly.")
        with gr.Row():
            people_selected_btn = gr.Button("🔎 Research selected company", variant="primary")
            people_all_btn = gr.Button("🏢 Research all result companies", variant="primary")
        company_people_box = gr.HTML('<div class="empty-research">Select a job above, then choose a research action.</div>')

    with gr.Group(elem_classes="feature-panel"):
        gr.Markdown("## Prepare applications")
        gr.Markdown("Prepare a truthful draft for the selected result, then review it before opening the employer’s site.")
        with gr.Row():
            prepare_btn = gr.Button("Prepare selected application", variant="primary")
            prepare_all_btn = gr.Button("Prepare all results")
        prep_status = gr.HTML()
        cover_letter = gr.Textbox(label="Editable cover-letter draft", lines=12)
        answers_box = gr.HTML()
        with gr.Accordion("Application review queue", open=True):
            queue_box = gr.HTML("<p>No prepared applications yet.</p>")

    search_outputs = [log_box, jobs_box, report_box, selected_job, jobs_state, resume_box, company_people_box]
    run_btn.click(run_research,
                  [query_box, search_type, country_box, city_box, age_box, education_box, salary_box, cv_file,
                   linkedin, portfolio, use_github, use_portfolios],
                  search_outputs)
    people_selected_btn.click(research_selected_ui, [selected_job, jobs_state], company_people_box)
    people_all_btn.click(research_all_ui, jobs_state, company_people_box)
    profile_inputs = [cv_file, name, email, phone, applicant_location, linkedin,
                      portfolio, authorization, sponsorship, relocation, salary]
    prepare_btn.click(prepare_selected,
                      [selected_job, *profile_inputs, jobs_state, queue_state],
                      [prep_status, cover_letter, answers_box, queue_box, queue_state])
    prepare_all_btn.click(prepare_all,
                          [*profile_inputs, jobs_state, queue_state],
                          [prep_status, cover_letter, answers_box, queue_box, queue_state])

if __name__ == "__main__":
    demo.launch(
        inbrowser=True, css=CSS,
        server_port=int(os.environ.get("JOBSEARCH_GRADIO_PORT", "7864")),
    )
