"""Versioned, privacy-bounded source recording and replay utilities."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SCENARIO_VERSION = 1
BLOCKED_JOB_KEYS = {
    "resume_fit", "resume_summary", "applicant_profile", "cv_text",
    "contact", "email", "phone",
}


def _json_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_value(item) for key, item in value.items()
            if not str(key).startswith("_") and str(key) not in BLOCKED_JOB_KEYS
        }
    return str(value)


def sanitize_job(job: dict) -> dict:
    """Remove private/internal values while retaining public ranking evidence."""
    return _json_value(dict(job))


def build_scenario(query: str, settings: dict, source_records: list[dict],
                   relevance: dict[str, int] | None = None) -> dict:
    sources = []
    for record in source_records:
        sources.append({
            "name": str(record.get("name") or "unknown"),
            "elapsed_seconds": max(0.0, float(record.get("elapsed_seconds") or 0)),
            "error": str(record.get("error") or ""),
            "jobs": [sanitize_job(job) for job in record.get("jobs", [])],
        })
    return {
        "version": SCENARIO_VERSION,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "query": str(query),
        "settings": _json_value(settings),
        "sources": sources,
        "relevance": {str(key): int(value) for key, value in (relevance or {}).items()},
    }


def save_scenario(path: str | Path, scenario: dict) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    return destination


def load_scenario(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("version") != SCENARIO_VERSION:
        raise ValueError("unsupported replay scenario version")
    if not isinstance(payload.get("sources"), list) or not payload.get("query"):
        raise ValueError("invalid replay scenario")
    return payload


def label_template(scenario: dict) -> dict:
    """Return every unique public job ID with an unset relevance grade."""
    labels = {}
    for source in scenario["sources"]:
        for job in source.get("jobs", []):
            identifier = str(job.get("id") or job.get("apply_url") or "")
            if identifier:
                labels.setdefault(identifier, None)
    return labels
