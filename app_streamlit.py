"""
Streamlit UI for the multi-agent research system.

Run:  pip install streamlit
      ollama pull gemma4
      streamlit run app_streamlit.py
"""

import queue
import threading
import time

import streamlit as st

import config
from agents.coordinator import Coordinator
from core.jobs import COUNTRIES, EDUCATION_LEVELS

st.set_page_config(page_title="AI Job Search", page_icon="🔎", layout="wide")

st.title("🔎 Comprehensive AI Job Search")
st.caption("Live feeds → ranked openings → extracted requirements → direct applications")

mode = "🟢 LIVE PUBLIC JOB FEEDS"
st.info(mode)

query = st.text_area(
    "What job are you looking for?",
    placeholder="e.g. AI robotics research scientist",
    height=100,
)
location_col1, location_col2 = st.columns(2)
with location_col1:
    country = st.selectbox(
        "Country — required", COUNTRIES,
        index=COUNTRIES.index("United States")
    )
with location_col2:
    city = st.text_input(
        "City — optional preference",
        placeholder="e.g. Boston (other cities remain eligible)"
    )
max_age_days = st.slider(
    "Maximum posting age", min_value=1, max_value=30, value=10,
    help="Undated jobs and jobs older than this number of days are excluded."
)
education = st.selectbox(
    "Education level", EDUCATION_LEVELS,
    index=EDUCATION_LEVELS.index("PhD")
)

col1, col2 = st.columns([1, 3])
with col1:
    run = st.button("Run research", type="primary", use_container_width=True)

if run and query.strip() and country.strip():
    log_area = st.expander("Agent activity (live)", expanded=True)
    log_placeholder = log_area.empty()
    lines: list[str] = []
    log_queue: queue.Queue = queue.Queue()
    result_holder: dict = {}

    def log(msg: str):
        # Coordinator sub-agents call this from worker threads. Queueing keeps
        # all Streamlit element updates on the main script thread.
        log_queue.put(str(msg))

    def worker():
        try:
            result_holder["result"] = Coordinator(log=log).run(
                query, country, city, max_age_days, education
            )
        except Exception as exc:
            result_holder["error"] = exc
        finally:
            log_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    with st.spinner("Coordinator and sub-agents at work..."):
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
        st.error(f"Research run failed: {result_holder['error']}")
    else:
        result = result_holder["result"]
        st.success(f"Found {len(result['jobs'])} ranked jobs from "
                   f"{result['fetched_count']} fetched listings.")
        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Verified matches", len(result["jobs"]))
        metric2.metric("Maximum age", f"{result['max_age_days']} days")
        metric3.metric("Location", ", ".join(
            x for x in [result.get("city"), result.get("country")] if x
        ) or "Any")
        metric4.metric("Education", result["education"])
        if not result["jobs"]:
            st.error(
                "No verified listing from the connected feeds passed the search. "
                "This may be a feed-coverage issue, not proof that no such jobs exist."
            )
            diagnostics = result["diagnostics"]
            st.markdown("#### Why listings were rejected")
            st.dataframe({
                "Gate": [
                    "Missing requested concept", "Incidental robotics mention",
                    "Outside age window",
                    "Country mismatch", "Missing/invalid date",
                ],
                "Rejected listings": [
                    diagnostics["missing_requested_concept"],
                    diagnostics["weak_domain_evidence"],
                    diagnostics["outside_age_window"],
                    diagnostics["country_mismatch"],
                    diagnostics["missing_or_invalid_date"],
                ],
            }, hide_index=True, use_container_width=True)
            st.caption("Counts overlap because a listing may fail more than one gate.")
        st.subheader("Search major job platforms")
        columns = st.columns(len(result["search_links"]))
        for column, link in zip(columns, result["search_links"]):
            column.link_button(link["name"], link["url"], use_container_width=True)
        st.subheader("Ranked live openings")
        for index, job in enumerate(result["jobs"], 1):
            with st.container(border=True):
                st.markdown(f"### {index}. {job['title']}")
                st.markdown(f"**{job['company']}** · {job['location']} · "
                            f"Source: **{job['source']}**")
                st.caption(
                    f"Posted {job['published_iso']} · {job['age_days']} days ago · "
                    f"Relevance signals: "
                    f"{', '.join(job['matched_keywords']) or 'close concept match'}"
                )
                st.markdown(f"#### 💰 {job['salary_display']}")
                st.write(job["description"][:900] or "No description supplied.")
                with st.expander("Experience requested"):
                    for item in job["experience"]:
                        st.markdown(f"- {item}")
                    if not job["experience"]:
                        st.write("Not explicitly stated in the posting.")
                with st.expander("Requirements extracted from this posting"):
                    for requirement in job["requirements"]:
                        st.markdown(f"- {requirement}")
                    if not job["requirements"]:
                        st.write("No clear requirement statements were extracted.")
                apply_url = str(job.get("apply_url") or "")
                if apply_url.startswith(("https://", "http://")):
                    st.link_button(
                        "Apply on original site ↗", apply_url, type="primary"
                    )
                else:
                    st.warning("This source did not provide a valid application URL.")
        st.subheader("Comprehensive report")
        st.markdown("---")
        st.markdown(result["report"])
        st.download_button("Download report (.md)", result["report"],
                           file_name="research_report.md")
elif run and not query.strip():
    st.warning("Please enter a job search query.")
elif run:
    st.warning("Country is required. City is optional.")
