from datetime import datetime, timezone

from core.jobs import _job
from rl_scheduler import SchedulerConfig
from rl_scheduler.evaluate import evaluate_scenarios, promotion_gate
from rl_scheduler.replay import build_scenario, label_template, load_scenario, save_scenario


def job(identifier, title, description, relevance=0):
    item = _job(
        "Replay", identifier, title, "Example Robotics", "Boston, MA, US",
        description, f"https://example.test/{identifier}",
        datetime.now(timezone.utc).isoformat(), "120000 - 180000 USD yearly",
    )
    return item, relevance


def scenario():
    strong, strong_grade = job(
        "strong", "Robotics Perception Engineer",
        "PhD robotics engineer developing robot perception, SLAM, motion planning, and manipulation.",
        3,
    )
    weak, weak_grade = job(
        "weak", "Robotics Program Manager",
        "PhD program role coordinating robotics perception and autonomous systems teams.",
        0,
    )
    later, later_grade = job(
        "later", "Robot Learning Scientist",
        "PhD robotics scientist developing robot learning, perception, manipulation, and motion planning.",
        2,
    )
    payload = build_scenario(
        "robotics perception engineer",
        {
            "country": "United States", "city": "", "max_age_days": 10,
            "education": "PhD", "search_type": "Jobs", "minimum_salary": 0,
            "max_results": 50, "ranking_mode": "bm25",
        },
        [
            {"name": "LinkedIn / Indeed / Google", "elapsed_seconds": 2.0,
             "jobs": [strong, weak], "error": ""},
            {"name": "Remotive", "elapsed_seconds": 1.0, "jobs": [], "error": ""},
            {"name": "Jobicy", "elapsed_seconds": 1.5, "jobs": [later], "error": ""},
        ],
        {strong["id"]: strong_grade, weak["id"]: weak_grade, later["id"]: later_grade},
    )
    return payload


def test_scenario_round_trip_and_privacy_filter(tmp_path):
    payload = scenario()
    payload["sources"][0]["jobs"][0]["email"] = "private@example.test"
    rebuilt = build_scenario(
        payload["query"], payload["settings"], payload["sources"], payload["relevance"]
    )
    destination = save_scenario(tmp_path / "scenario.json", rebuilt)
    loaded = load_scenario(destination)
    assert loaded["version"] == 1
    assert "email" not in loaded["sources"][0]["jobs"][0]
    assert len(label_template(loaded)) == 3


def test_paired_evaluation_uses_identical_recorded_sources():
    result = evaluate_scenarios([
        scenario()
    ], config=SchedulerConfig(
        initial_agents=2, max_parallel_agents=2,
        minimum_results=1, target_results=1,
        soft_deadline_seconds=5, hard_deadline_seconds=10,
    ))
    pair = result["paired_results"][0]
    assert pair["full_parallel"]["source_calls"] == 3
    assert pair["adaptive"]["source_calls"] == 2
    assert pair["full_parallel"]["quality"] is not None
    assert pair["adaptive"]["quality"] is not None
    assert result["policy_loaded"] is False
    assert "trained_rl" not in pair


def test_promotion_gate_refuses_missing_quality_labels():
    baseline = {
        "p50_latency_seconds": 10, "mean_source_calls": 4,
        "empty_result_rate": 0, "quality_scenarios": 0,
    }
    candidate = {
        "p50_latency_seconds": 5, "mean_source_calls": 2,
        "empty_result_rate": 0, "quality_scenarios": 0,
    }
    gate = promotion_gate(baseline, candidate)
    assert gate["passed"] is False
    assert gate["checks"]["quality_labels_available"] is False
