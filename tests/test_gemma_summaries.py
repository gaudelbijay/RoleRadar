import json

import pytest

from core.gemma_summaries import enrich_jobs, summarize_job
from core.llm import parse_json_block

SOURCE = (
    "Build robot manipulation and motion planning systems using Python and ROS. "
    "Candidates need a PhD in Robotics and five years of production experience."
)


def job():
    return {"title": "Robotics Engineer", "company": "Example", "description": SOURCE,
            "role_overview": "Deterministic fallback", "experience": [], "requirements": []}


def valid_completion(*_args, **_kwargs):
    return json.dumps({
        "role_overview": "Develop production robotics software for manipulation and planning, using Python and ROS, in a role requiring advanced education and substantial production experience.",
        "overview_evidence": ["Build robot manipulation and motion planning systems using Python and ROS."],
        "experience": [{"text": "Five years of production experience", "evidence": "five years of production experience"}],
        "requirements": [{"text": "PhD in Robotics", "evidence": "PhD in Robotics"}],
    })


def test_valid_summary_replaces_only_presentation_fields():
    result = summarize_job(job(), "robotics", completion=valid_completion)
    assert result["gemma_summary"] is True
    assert result["requirements"] == ["PhD in Robotics"]
    assert result["experience"] == ["Five years of production experience"]
    assert result["summary_evidence"] == [
        "Build robot manipulation and motion planning systems using Python and ROS."
    ]


def test_unsupported_or_invalid_output_is_rejected():
    unsupported = lambda *_args, **_kwargs: json.dumps({
        "role_overview": "This company offers an excellent salary and remote work to every successful applicant.",
        "overview_evidence": ["excellent salary and remote work"],
        "experience": [], "requirements": [],
    })
    with pytest.raises(ValueError, match="evidence"):
        summarize_job(job(), "robotics", completion=unsupported)
    with pytest.raises(ValueError, match="JSON"):
        summarize_job(job(), "robotics", completion=lambda *_a, **_k: "not json")


def test_enrichment_preserves_fallback_when_one_generation_fails(monkeypatch):
    jobs = [job(), job()]
    calls = {"count": 0}

    def mixed(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return valid_completion(*args, **kwargs)
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setenv("JOBSEARCH_GEMMA_MAX_JOBS", "2")
    stats = enrich_jobs(jobs, "robotics", enabled=True, completion=mixed)
    assert stats == {"enabled": True, "attempted": 2, "generated": 1, "failed": 1}
    assert sum(item.get("gemma_summary") is True for item in jobs) == 1
    fallback = next(item for item in jobs if item.get("gemma_summary") is False)
    assert fallback["role_overview"] == "Deterministic fallback"


def test_disabled_enrichment_does_not_call_model():
    stats = enrich_jobs([job()], "robotics", enabled=False,
                        completion=lambda *_a, **_k: pytest.fail("must not run"))
    assert stats["attempted"] == 0


def test_json_parser_keeps_enclosing_object_with_nested_arrays():
    value = parse_json_block('Result: {"role": "engineer", "skills": ["ROS"]}')
    assert value == {"role": "engineer", "skills": ["ROS"]}


def test_json_parser_still_accepts_fenced_arrays():
    assert parse_json_block('```json\n[{"title": "Engineer"}]\n```') == [
        {"title": "Engineer"}
    ]
