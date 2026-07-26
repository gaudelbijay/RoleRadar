"""
Coordinator agent.

Orchestrates one live job search: dispatch bounded source agents (directly or
through the adaptive RL scheduler), rank the eligible results, optionally
enrich the top listings with evidence-validated Gemma summaries, and persist
the Markdown report, JSON audit, and PDF artifacts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.jobs import build_report, search_jobs
from core.gemma_summaries import enrich_jobs
from core.pdf_report import build_pdf

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class Coordinator:
    def __init__(self, log=print):
        self.log = log

    def run(self, query: str, country: str = "United States", city: str = "",
            max_age_days: int = 10, education: str = "PhD",
            minimum_salary: int = 100_000, resume_profile: dict | None = None,
            search_type: str = "Jobs", use_gemma_summaries: bool = False,
            use_rl_scheduler: bool = True,
            record_scenario_path: str | None = None) -> dict:
        """Search live public job feeds and produce ranked dashboard results."""
        if not country.strip():
            raise ValueError("Country is required. City is optional.")
        started = datetime.now(timezone.utc)
        self.log("[coordinator] launching live job-source agents...")
        search_result = search_jobs(
            query, log=self.log, country=country, city=city,
            max_age_days=max_age_days, education=education, minimum_salary=minimum_salary,
            resume_profile=resume_profile, search_type=search_type,
            source_scheduler="rl" if use_rl_scheduler else "all",
            record_scenario_path=record_scenario_path,
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
