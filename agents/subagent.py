"""
Sub-agent: an autonomous research worker.

Each sub-agent receives ONE subtask from the coordinator, then independently:
  1. analyzes its assigned research angle,
  2. writes focused findings with local Gemma,
  3. returns a structured result to the coordinator.

Sub-agents never talk to each other — only to the coordinator. That keeps
the system simple, parallelizable, and easy to debug.
"""

from __future__ import annotations

import time

import config
from core import llm

SUBAGENT_SYSTEM = """You are a focused research sub-agent inside a multi-agent \
research system. You are assigned exactly ONE research subtask.

Rules:
- Work only from knowledge available to the model. Do not claim that you \
searched the web or accessed live sources.
- Be explicit when current or externally verifiable information is unavailable.
- Report concrete facts: numbers, dates, names. Note the year of each figure.
- Clearly separate established facts from analyst opinion or speculation.
- If sources conflict, say so.
- Write findings as dense, well-organized analysis (not a list of links).
- If the subtask involves investments or securities, report factual research \
only — performance data, business fundamentals, risks — and do NOT give \
buy/sell recommendations or personalized financial advice.
- End with a short "Key takeaways" list of 3-5 bullets."""


def run_subagent(agent_id: int, subtask: dict, query: str,
                 log=lambda msg: None) -> dict:
    """Execute one research subtask. Returns an envelope the coordinator collects."""
    started = time.time()
    log(f"[agent {agent_id}] started: {subtask['title']}")

    if config.live_mode():
        prompt = (
            f"Overall user research query: \"{query}\"\n\n"
            f"YOUR subtask: {subtask['task']}\n\n"
            f"Analyze this thoroughly, then write your findings. You do not have "
            f"live web access, so do not invent citations or claim current facts."
        )
        try:
            result = llm.llm_research(prompt, system=SUBAGENT_SYSTEM,
                                      max_tokens=config.SUBAGENT_MAX_TOKENS)
            status = "ok"
        except Exception as exc:  # graceful degradation: one failed agent won't kill the run
            result = {"text": f"Sub-agent failed: {exc}", "sources": [], "searches": []}
            status = "error"
    else:
        result = llm.mock_research(subtask, query)
        status = "demo"

    elapsed = time.time() - started
    log(f"[agent {agent_id}] finished in {elapsed:.1f}s "
        f"({len(result['searches'])} searches, {len(result['sources'])} sources)")

    return {
        "agent_id": agent_id,
        "subtask": subtask,
        "result": result,
        "status": status,
        "elapsed_sec": round(elapsed, 1),
    }
