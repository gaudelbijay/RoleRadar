"""Streamlit dashboard for job search and review-first applications."""
import queue
import threading
import time
from pathlib import Path

import streamlit as st

from agents.coordinator import Coordinator
from core.applications import (
    ApplicantProfile, extract_cv_text, prepare_application, validate_profile,
)
from core.jobs import COUNTRIES, EDUCATION_LEVELS
from core.resume_intelligence import analyze_candidate

st.set_page_config(page_title="Job Search", page_icon="🔎", layout="wide")
st.title("Job Search")
st.caption("Find recent jobs, prepare applications from your CV, and review before applying.")

for key, default in (("application_queue", {}), ("search_result", None),
                     ("cv_text", ""), ("cv_name", ""),
                     ("applicant_profile", None), ("application_notice", ""),
                     ("resume_intelligence", None)):
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.header("Application assistant")
    st.caption("Your CV and profile stay in this local dashboard session and are not added to reports.")
    cv_file = st.file_uploader("Upload CV", type=["pdf", "docx", "txt", "md"])
    if cv_file is not None and cv_file.name != st.session_state.cv_name:
        try:
            st.session_state.cv_text = extract_cv_text(cv_file.name, cv_file.getvalue())
            st.session_state.cv_name = cv_file.name
            st.session_state.resume_intelligence = None
            st.success(f"CV ready: {cv_file.name}")
        except Exception as exc:
            st.session_state.cv_text = ""
            st.error(str(exc))
    elif st.session_state.cv_name:
        st.success(f"CV ready: {st.session_state.cv_name}")
    use_github = st.checkbox("Analyze public GitHub evidence", value=True)
    use_portfolios = st.checkbox("Analyze public portfolio pages (opt in)", value=False)

    saved = st.session_state.applicant_profile
    with st.form("applicant_profile_form"):
        full_name = st.text_input("Full name *", value=saved.full_name if saved else "")
        email = st.text_input("Email *", value=saved.email if saved else "")
        phone = st.text_input("Phone", value=saved.phone if saved else "")
        applicant_location = st.text_input("Current location", value=saved.location if saved else "")
        linkedin_url = st.text_input("LinkedIn URL", value=saved.linkedin_url if saved else "")
        portfolio_url = st.text_input("Portfolio URL", value=saved.portfolio_url if saved else "")
        authorization = st.selectbox(
            "Authorized to work in target country?",
            ["Prefer not to answer", "Yes", "No"],
            index=["Prefer not to answer", "Yes", "No"].index(saved.work_authorization) if saved else 0,
        )
        sponsorship = st.selectbox(
            "Require visa sponsorship?", ["Prefer not to answer", "Yes", "No"],
            index=["Prefer not to answer", "Yes", "No"].index(saved.sponsorship) if saved else 0,
        )
        relocation = st.selectbox(
            "Open to relocation?", ["Prefer not to answer", "Yes", "No"],
            index=["Prefer not to answer", "Yes", "No"].index(saved.relocation) if saved else 0,
        )
        salary = st.text_input("Salary expectation", value=saved.salary_expectation if saved else "")
        save_profile = st.form_submit_button("Save applicant profile", type="primary")
        if save_profile:
            profile = ApplicantProfile(full_name, email, phone, applicant_location,
                                       linkedin_url, portfolio_url, authorization,
                                       sponsorship, relocation, salary)
            errors = validate_profile(profile)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.session_state.applicant_profile = profile
                st.success("Applicant profile saved.")

    st.info("The assistant prepares drafts only. You review every answer and submit on the employer's site.")
    if st.session_state.resume_intelligence:
        intelligence = st.session_state.resume_intelligence
        st.success(intelligence.get("summary", "Resume intelligence ready."))
        for category, skills in list(intelligence.get("skill_categories", {}).items())[:8]:
            st.caption(f"{category}: {', '.join(skills[:8])}")
        for warning in intelligence.get("warnings", []):
            st.caption(warning)


    cv_ready = bool(st.session_state.cv_text)
    profile_ready = st.session_state.applicant_profile is not None
    if cv_ready and profile_ready:
        st.success("Ready to prepare applications.")
    else:
        missing = []
        if not cv_ready:
            missing.append("upload a CV")
        if not profile_ready:
            missing.append("save your profile")
        st.warning("To enable Prepare application: " + " and ".join(missing) + ".")


def application_ready() -> bool:
    return bool(st.session_state.cv_text and st.session_state.applicant_profile)


def application_key(job: dict) -> str:
    return str(job.get("apply_url") or f"{job.get('company')}:{job.get('title')}")


def add_to_queue(job: dict) -> str:
    key = application_key(job)
    st.session_state.application_queue[key] = prepare_application(
        job, st.session_state.applicant_profile, st.session_state.cv_text)
    return key


search_type = st.radio("Search type", ["Jobs", "Internships"], index=0, horizontal=True)
query = st.text_area("What job are you looking for?",
                     placeholder="e.g. AI robotics research scientist", height=100)
location_col1, location_col2 = st.columns(2)
with location_col1:
    country = st.selectbox("Country — required", COUNTRIES,
                           index=COUNTRIES.index("United States"))
with location_col2:
    city = st.text_input("City — optional preference",
                         placeholder="e.g. Boston (other cities remain eligible)")
max_age_days = st.slider("Maximum posting age", 1, 30, 10,
                         help="Undated and older jobs are excluded.")
education = st.selectbox("Education level", EDUCATION_LEVELS,
                         index=EDUCATION_LEVELS.index("PhD"))
run = st.button("Search Jobs", type="primary")

if run and query.strip() and country.strip():
    log_area = st.expander("Search activity", expanded=False)
    log_placeholder = log_area.empty()
    lines, log_queue, result_holder = [], queue.Queue(), {}
    cv_text_for_search = st.session_state.cv_text
    profile_for_search = st.session_state.applicant_profile

    def log(msg: str):
        log_queue.put(str(msg))

    def worker():
        try:
            candidate = None
            if cv_text_for_search:
                explicit_urls = ([profile_for_search.linkedin_url, profile_for_search.portfolio_url]
                                 if profile_for_search else [])
                candidate = analyze_candidate(
                    cv_text_for_search, explicit_urls, use_github,
                    use_portfolios, log=log)
            result_holder["candidate"] = candidate
            result_holder["result"] = Coordinator(log=log).run(
                query, country, city, max_age_days, education,
                resume_profile=candidate, search_type=search_type)
        except Exception as exc:
            result_holder["error"] = exc
        finally:
            log_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()
    with st.spinner("Searching live job sources..."):
        finished = False
        while not finished:
            try:
                item = log_queue.get(timeout=0.1)
                if item is None:
                    finished = True
                else:
                    lines.append(item)
                    log_placeholder.code("\n".join(lines))
            except queue.Empty:
                time.sleep(0.05)
    if "error" in result_holder:
        st.error(f"Search failed: {result_holder['error']}")
    else:
        st.session_state.search_result = result_holder["result"]
        st.session_state.resume_intelligence = result_holder.get("candidate")
elif run and not query.strip():
    st.warning("Please enter a job search query.")
elif run:
    st.warning("Country is required. City is optional.")

result = st.session_state.search_result
if result:
    if st.session_state.application_notice:
        st.success(st.session_state.application_notice)
        st.session_state.application_notice = ""

    st.success(f"Found {len(result['jobs'])} ranked jobs from {result['fetched_count']} fetched listings.")
    metrics = st.columns(4)
    metrics[0].metric("Verified matches", len(result["jobs"]))
    metrics[1].metric("Maximum age", f"{result['max_age_days']} days")
    metrics[2].metric("Location", ", ".join(x for x in [result.get("city"), result.get("country")] if x) or "Any")
    metrics[3].metric("Education", result["education"])

    if result["jobs"]:
        if not application_ready():
            st.info("Upload your CV and save the applicant profile in the sidebar to enable application preparation.")
        if st.button("Prepare all matching applications", type="primary",
                     disabled=not application_ready(),
                     help="Requires an uploaded CV and saved applicant profile."):
            for job in result["jobs"]:
                add_to_queue(job)
            st.session_state.application_notice = (
                f"Prepared {len(result['jobs'])} applications. Review them below.")
            st.rerun()
    else:
        st.error("No verified listing passed this search.")
        diagnostics = result["diagnostics"]
        st.dataframe({"Gate": ["Wrong search type", "Missing concept", "Weak domain evidence", "Outside age window", "Country mismatch", "Missing date"],
                      "Rejected": [diagnostics["search_type_mismatch"], diagnostics["missing_requested_concept"], diagnostics["weak_domain_evidence"], diagnostics["outside_age_window"], diagnostics["country_mismatch"], diagnostics["missing_or_invalid_date"]]},
                     hide_index=True, use_container_width=True)

    if st.session_state.application_queue:
        st.subheader(f"Application review queue ({len(st.session_state.application_queue)})")
        st.caption("Check every draft. Employer questions, login, consent, assessments, and CAPTCHAs must be completed on the original site.")
        for queue_key, draft in list(st.session_state.application_queue.items()):
            job = draft["job"]
            with st.expander(f"{job['title']} — {job['company']}"):
                st.markdown("**CV evidence matched:** " + (", ".join(draft["matched_cv_terms"]) or "Review manually"))
                st.text_area("Cover-letter draft", draft["cover_letter"], height=260,
                             key=f"letter-{queue_key}")
                st.markdown("**Suggested profile answers**")
                st.table([{"Question": k, "Answer": v} for k, v in draft["suggested_answers"].items()])
                controls = st.columns([2, 1])
                apply_url = str(job.get("apply_url") or "")
                if apply_url.startswith(("https://", "http://")):
                    controls[0].link_button("Review and apply on original site ↗", apply_url,
                                            type="primary", use_container_width=True)
                if controls[1].button("Remove", key=f"remove-{queue_key}", use_container_width=True):
                    del st.session_state.application_queue[queue_key]
                    st.rerun()

    st.subheader("Search major job platforms")
    columns = st.columns(len(result["search_links"]))
    for column, link in zip(columns, result["search_links"]):
        column.link_button(link["name"], link["url"], use_container_width=True)

    st.subheader("Ranked live openings")
    for index, job in enumerate(result["jobs"], 1):
        with st.container(border=True):
            st.markdown(f"### {index}. {job['title']}")
            st.markdown(f"**{job['company']}** · {job['location']} · **{job['source']}**")
            st.caption(f"Posted {job['published_iso']} · {job['age_days']} days ago · {', '.join(job['matched_keywords']) or 'close concept match'}")
            resume_fit = job.get("resume_fit")
            if resume_fit:
                fit_col, evidence_col = st.columns([1, 3])
                fit_col.metric("Estimated resume fit", f"{resume_fit['score']}%")
                evidence_col.markdown(
                    "**Resume evidence:** "
                    + (", ".join(resume_fit.get("matched_skills", [])[:8])
                       or "Limited direct skill overlap")
                )
                if resume_fit.get("reasons"):
                    evidence_col.caption(" · ".join(resume_fit["reasons"]))
            detail1, detail2, detail3 = st.columns(3)
            detail1.markdown(f"**💰 Salary**\n\n{job['salary_display']}")
            detail2.markdown(f"**💼 Type**\n\n{job['job_type'] or 'Not disclosed'}")
            evidence = job["concept_evidence"].get(f"education: {result['education']}", [])
            detail3.markdown(f"**🎓 Education**\n\n{', '.join(evidence) or 'Not stated'}")
            with st.expander("Experience and requirements"):
                for item in job["experience"] or ["Experience not explicitly stated."]:
                    st.markdown(f"- {item}")
                for item in job["requirements"] or ["No clear requirements extracted."]:
                    st.markdown(f"- {item}")
            with st.expander("Job description"):
                st.write(job["description"][:1800] or "No description supplied.")
            actions = st.columns(2)
            apply_url = str(job.get("apply_url") or "")
            if apply_url.startswith(("https://", "http://")):
                actions[0].link_button("Open original listing ↗", apply_url,
                                       use_container_width=True)
            queue_key = application_key(job)
            is_prepared = queue_key in st.session_state.application_queue
            button_label = "Prepared ✓" if is_prepared else "Prepare application"
            if actions[1].button(
                    button_label, key=f"prepare-{index}-{apply_url}",
                    type="primary", use_container_width=True,
                    disabled=is_prepared or not application_ready(),
                    help="Upload a CV and save your profile first." if not application_ready() else None):
                add_to_queue(job)
                st.session_state.application_notice = (
                    f"Prepared {job['title']} at {job['company']}. Review it in the queue.")
                st.rerun()
            if is_prepared:
                st.caption("✓ This application is in the review queue above.")

    pdf_path = Path(result["pdf_path"])
    if pdf_path.exists():
        st.download_button("Download PDF Report", pdf_path.read_bytes(),
                           "job_search_report.pdf", "application/pdf", type="primary")
