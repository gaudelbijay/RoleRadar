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

st.set_page_config(page_title="Multi-Agent Deep Research", page_icon="🔬", layout="wide")

st.title("🔬 Multi-Agent Deep Research")
st.caption("Coordinator agent → parallel research sub-agents → synthesized report")

mode = "🟢 LOCAL (Gemma via Ollama)" if config.live_mode() else "🟡 DEMO mode"
st.info(mode)

query = st.text_area(
    "Research query",
    placeholder="e.g. Research silicon-based semiconductor companies: 5-year "
                "performance, key collaborations, risks, and how they compare",
    height=100,
)

col1, col2 = st.columns([1, 3])
with col1:
    run = st.button("Run research", type="primary", use_container_width=True)

if run and query.strip():
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
            result_holder["result"] = Coordinator(log=log).run(query)
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
        st.success(f"Report saved to `{result['report_path']}`")
        st.markdown("---")
        st.markdown(result["report"])
        st.download_button("Download report (.md)", result["report"],
                           file_name="research_report.md")
elif run:
    st.warning("Please enter a research query.")
