"""
Coordinator (principal) agent.

Responsibilities:
  1. DECOMPOSE  - break the user's query into 3-5 independent research
                  subtasks that can run in parallel.
  2. DISPATCH   - launch one sub-agent per subtask, in parallel
                  (ThreadPoolExecutor; parallelism capped by config).
  3. COLLECT    - gather every sub-agent's findings envelope.
  4. SYNTHESIZE - write the final report: executive summary, sections,
                  comparison/analysis, sources, limitations.

The coordinator never performs research itself — analysis is delegated to
local Gemma sub-agents. It is the only component that sees ALL findings, which is
what lets it compare and synthesize across subtasks.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import config
from agents.subagent import run_subagent
from core import llm
from core.jobs import build_report, search_jobs
from core.gemma_summaries import enrich_jobs
from core.pdf_report import build_pdf

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DECOMPOSE_SYSTEM = f"""You are the coordinator of a multi-agent research system.
Break the user's query into {config.MIN_SUBTASKS}-{config.MAX_SUBTASKS} independent research subtasks that can be
researched IN PARALLEL by separate sub-agents (no subtask may depend on
another's output). Cover complementary angles, e.g.: landscape/key players,
historical performance, partnerships/collaborations, financials, risks and
recent news, technology or competitive positioning — whatever fits the query.

Keep each task brief to one concise sentence. Respond ONLY with a JSON array:
[{{"title": "<3-6 word section title>", "task": "<one-sentence research brief>"}}, ...]"""

SYNTHESIS_SYSTEM = """You are the coordinator agent writing the FINAL research \
report from your sub-agents' findings.

Requirements:
- Start with a 1-paragraph executive summary that directly addresses the query.
- Then one section per research angle, synthesizing (not copy-pasting) findings.
- Add a "Comparative analysis" section that connects findings ACROSS sections \
— tensions, corroborations, and what it adds up to.
- Note conflicting information and gaps honestly in a "Limitations" section.
- Use markdown with ## headings.
- If the query concerns investments or securities: present factual research and \
frameworks for evaluation, but do NOT give a buy/sell recommendation or \
personalized financial advice, and end with a one-line note that this report \
is informational, not financial advice."""


class Coordinator:
    def __init__(self, log=print):
        self.log = log

    # ------------------------------------------------------------------ #
    def decompose(self, query: str) -> list[dict]:
        self.log("[coordinator] decomposing query into subtasks...")
        if config.live_mode():
            raw = llm.llm_complete(f"User query: {query}", system=DECOMPOSE_SYSTEM,
                                   max_tokens=1600)
            try:
                subtasks = llm.parse_json_block(raw)
                if (
                    not isinstance(subtasks, list)
                    or not all(
                        isinstance(item, dict)
                        and isinstance(item.get("title"), str)
                        and isinstance(item.get("task"), str)
                        for item in subtasks
                    )
                    or len(subtasks) < config.MIN_SUBTASKS
                ):
                    raise ValueError("Invalid subtask structure")
            except (json.JSONDecodeError, TypeError, ValueError):
                self.log("[coordinator] decompose parse failed; using default plan")
                subtasks = llm.mock_decompose(query)
        else:
            subtasks = llm.mock_decompose(query)
        subtasks = subtasks[: config.MAX_SUBTASKS]
        for i, st in enumerate(subtasks, 1):
            self.log(f"[coordinator] subtask {i}: {st['title']}")
        return subtasks

    # ------------------------------------------------------------------ #
    def dispatch(self, query: str, subtasks: list[dict]) -> list[dict]:
        self.log(f"[coordinator] dispatching {len(subtasks)} sub-agents "
                 f"(max {config.MAX_PARALLEL_AGENTS} in parallel)...")
        findings: list[dict] = []
        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_AGENTS) as pool:
            futures = {
                pool.submit(run_subagent, i + 1, st, query, self.log): i
                for i, st in enumerate(subtasks)
            }
            for future in as_completed(futures):
                findings.append(future.result())
        findings.sort(key=lambda f: f["agent_id"])  # stable report order
        return findings

    # ------------------------------------------------------------------ #
    def synthesize(self, query: str, findings: list[dict]) -> str:
        self.log("[coordinator] synthesizing final report...")
        if not config.live_mode():
            return llm.mock_report(query, findings)

        bundle = "\n\n".join(
            f"### Findings from sub-agent {f['agent_id']} — {f['subtask']['title']}\n"
            f"(status: {f['status']}; sources: {', '.join(f['result']['sources'][:8]) or 'none'})\n\n"
            f"{f['result']['text']}"
            for f in findings
        )
        prompt = (f"User query: \"{query}\"\n\nSub-agent findings:\n\n{bundle}\n\n"
                  f"Write the final report now.")
        report = llm.llm_complete(prompt, system=SYNTHESIS_SYSTEM,
                                  max_tokens=config.REPORT_MAX_TOKENS)

        all_sources = []
        for f in findings:
            for src in f["result"]["sources"]:
                if src not in all_sources:
                    all_sources.append(src)
        if all_sources:
            report += "\n\n## Sources\n" + "\n".join(f"- {s}" for s in all_sources)
        return report

    # ------------------------------------------------------------------ #
    def run(self, query: str, country: str = "United States", city: str = "",
            max_age_days: int = 10, education: str = "PhD",
            minimum_salary: int = 100_000, resume_profile: dict | None = None,
            search_type: str = "Jobs", use_gemma_summaries: bool = False) -> dict:
        """Search live public job feeds and produce ranked dashboard results."""
        if not country.strip():
            raise ValueError("Country is required. City is optional.")
        started = datetime.now(timezone.utc)
        self.log("[coordinator] launching live job-source agents...")
        search_result = search_jobs(
            query, log=self.log, country=country, city=city,
            max_age_days=max_age_days, education=education, minimum_salary=minimum_salary,
            resume_profile=resume_profile, search_type=search_type
        )
        self.log(f"[coordinator] ranking {search_result['fetched_count']} fetched listings...")
        search_result["gemma_summaries"] = enrich_jobs(
            search_result["jobs"], query, log=self.log,
            enabled=bool(use_gemma_summaries),
        )
        report = build_report(query, search_result)

        stamp = started.strftime("%Y%m%d-%H%M%S")
        path = REPORTS_DIR / f"report-{stamp}.md"
        path.write_text(report, encoding="utf-8")
        audit = REPORTS_DIR / f"audit-{stamp}.json"
        audit.write_text(json.dumps(
            {"query": query, **search_result}, indent=2), encoding="utf-8")
        pdf = REPORTS_DIR / f"report-{stamp}.pdf"
        build_pdf(query, search_result, pdf)
        self.log(f"[coordinator] PDF report saved -> {pdf}")
        return {"report": report, "report_path": str(path),
                "pdf_path": str(pdf), "audit_path": str(audit), **search_result}
