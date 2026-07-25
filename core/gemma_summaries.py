"""Evidence-validated optional Gemma summaries for displayed job listings."""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from core.llm import llm_complete, parse_json_block

SYSTEM = """You summarize one job posting using only supplied source text.
Return one JSON object and no commentary:
{
  "role_overview": "40-100 word concise overview",
  "overview_evidence": ["1-3 exact source excerpts"],
  "experience": [{"text": "concise requirement", "evidence": "exact source excerpt"}],
  "requirements": [{"text": "concise requirement", "evidence": "exact source excerpt"}]
}
Every evidence value must be copied exactly from the source. Do not infer salary,
experience, education, responsibilities, technologies, or benefits. Omit missing
information. Never include contact details or private reasoning."""


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _supported(excerpt: object, source: str) -> bool:
    evidence = _normalized(excerpt)
    return 8 <= len(evidence) <= 500 and evidence.lower() in source.lower()


def _validated_items(value: object, source: str, limit: int) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Summary evidence list is invalid")
    results = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            raise ValueError("Summary item is invalid")
        text = _normalized(item.get("text"))
        evidence = item.get("evidence")
        if not (5 <= len(text) <= 240 and _supported(evidence, source)):
            raise ValueError("Summary item lacks exact source evidence")
        results.append(text)
    return results


def summarize_job(job: dict, query: str, completion=llm_complete) -> dict:
    """Generate and validate one structured summary or raise ValueError."""
    source = _normalized(job.get("description"))
    if len(source) < 40:
        raise ValueError("Job description is too short for Gemma summarization")
    prompt = (
        f"Search query: {_normalized(query)}\n"
        f"Job title: {_normalized(job.get('title'))}\n"
        f"Company: {_normalized(job.get('company'))}\n\n"
        f"SOURCE POSTING:\n{source[:12000]}"
    )
    raw = completion(
        prompt, system=SYSTEM, model=config.JOB_SUMMARY_MODEL,
        max_tokens=config.JOB_SUMMARY_MAX_TOKENS,
    )
    try:
        value = parse_json_block(raw)
    except Exception as exc:
        raise ValueError("Gemma summary was not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Gemma summary must be an object")
    overview = _normalized(value.get("role_overview"))
    evidence = value.get("overview_evidence")
    if not (30 <= len(overview) <= 700 and isinstance(evidence, list)
            and 1 <= len(evidence) <= 3
            and all(_supported(item, source) for item in evidence)):
        raise ValueError("Role overview lacks exact source evidence")
    experience = _validated_items(value.get("experience", []), source, 6)
    requirements = _validated_items(value.get("requirements", []), source, 8)
    return {
        "role_overview": overview,
        "experience": experience,
        "requirements": requirements,
        "gemma_summary": True,
        "summary_evidence": [_normalized(item) for item in evidence],
    }


def enrich_jobs(jobs: list[dict], query: str, log=lambda _message: None,
                enabled: bool = False, completion=llm_complete) -> dict:
    """Summarize a bounded displayed prefix and preserve deterministic fallbacks."""
    if not enabled or not jobs:
        return {"enabled": bool(enabled), "attempted": 0, "generated": 0, "failed": 0}
    maximum = max(1, min(30, int(os.environ.get("JOBSEARCH_GEMMA_MAX_JOBS", "10"))))
    targets = jobs[:maximum]
    generated = 0
    log(f"[gemma summaries] generating evidence-backed summaries for {len(targets)} jobs...")
    with ThreadPoolExecutor(max_workers=min(2, len(targets))) as pool:
        futures = {
            pool.submit(summarize_job, job, query, completion): job
            for job in targets
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                job.update(future.result())
                generated += 1
            except (RuntimeError, ValueError) as exc:
                job["gemma_summary"] = False
                job["gemma_summary_error"] = type(exc).__name__
    failed = len(targets) - generated
    log(f"[gemma summaries] generated {generated}; deterministic fallback {failed}")
    return {"enabled": True, "attempted": len(targets), "generated": generated, "failed": failed}
