"""
Gradio UI for the multi-agent research system.

Run:  pip install gradio
      ollama pull gemma4
      python app_gradio.py
"""

import queue
import threading

import gradio as gr

import config
from agents.coordinator import Coordinator

EXAMPLES = [
    "Research silicon/semiconductor companies: 5-year performance, key collaborations, risks, and how they compare",
    "State of solid-state battery research: leading labs, breakthroughs, commercialization timelines",
    "CRISPR gene editing: major research groups, recent clinical trials, ethical debates",
]


def run_research(query: str):
    """Generator: streams live agent logs, then the final report."""
    if not query.strip():
        yield "Please enter a research query.", ""
        return

    log_q: queue.Queue = queue.Queue()
    result_holder = {}

    def log(msg: str):
        log_q.put(str(msg))

    def worker():
        try:
            result_holder["result"] = Coordinator(log=log).run(query)
        except Exception as exc:
            log(f"ERROR: {exc}")
            result_holder["result"] = {"report": f"Run failed: {exc}"}
        finally:
            log_q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    mode = "LOCAL (Gemma via Ollama)" if config.live_mode() else "DEMO"
    lines = [f"Mode: {mode}"]
    while True:
        item = log_q.get()
        if item is None:
            break
        lines.append(item)
        yield "\n".join(lines), ""

    report = result_holder.get("result", {}).get("report", "")
    yield "\n".join(lines), report


with gr.Blocks(title="Multi-Agent Deep Research") as demo:
    gr.Markdown("# 🔬 Multi-Agent Deep Research\n"
                "A coordinator agent splits your query into subtasks, sub-agents "
                "analyzes them **in parallel** with local Gemma, and the coordinator "
                "writes the final report.")
    query_box = gr.Textbox(label="Research query", lines=3,
                           placeholder="e.g. Research silicon-based semiconductor companies: "
                                       "5-year performance, collaborations, risks...")
    gr.Examples(EXAMPLES, inputs=query_box)
    run_btn = gr.Button("Run research", variant="primary")
    with gr.Row():
        log_box = gr.Textbox(label="Agent activity (live)", lines=14, interactive=False)
    report_box = gr.Markdown(label="Final report")
    run_btn.click(run_research, inputs=query_box, outputs=[log_box, report_box])

if __name__ == "__main__":
    demo.launch()
