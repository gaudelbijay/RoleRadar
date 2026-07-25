import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core import jobs
from core.ranking_metrics import (
    ndcg_at_k, precision_at_k, ranking_metrics, recall_at_k,
)

BENCHMARK = Path(__file__).parents[1] / "benchmarks" / "ranking_v1.json"


def load_benchmark():
    return json.loads(BENCHMARK.read_text(encoding="utf-8"))


def make_listing(candidate):
    published = (
        datetime.now(timezone.utc) - timedelta(days=candidate["days_old"])
    ).isoformat()
    return jobs._job(
        "Benchmark", candidate["id"], candidate["title"],
        f"Synthetic Company {candidate['id']}", candidate["location"],
        candidate["description"], f"https://example.test/{candidate['id']}",
        published, candidate.get("salary", ""),
    )


def test_metric_formulas_are_deterministic():
    relevance = {"a": 3, "b": 2, "c": 0, "d": 1}
    assert precision_at_k(["a", "c", "b"], relevance, 3) == pytest.approx(2 / 3)
    assert recall_at_k(["a", "c", "b"], relevance, 3) == pytest.approx(2 / 3)
    assert ndcg_at_k(["a", "b", "d", "c"], relevance, 4) == pytest.approx(1.0)
    assert ndcg_at_k(["c", "d", "b", "a"], relevance, 4) < 1.0
    with pytest.raises(ValueError, match="positive"):
        precision_at_k([], relevance, 0)


def test_versioned_benchmark_measures_current_baseline_without_gate_leakage():
    benchmark = load_benchmark()
    assert benchmark["version"] == 1
    case_metrics = []

    for case in benchmark["cases"]:
        candidates = case["candidates"]
        ranked = jobs.rank(
            [make_listing(candidate) for candidate in candidates],
            case["query"], limit=50, **case["filters"],
        )
        ranked_ids = [item["id"].split(":", 1)[1] for item in ranked]
        relevance = {
            item["id"]: 0 if item.get("must_reject") else item["relevance"]
            for item in candidates
        }
        forbidden = {item["id"] for item in candidates if item.get("must_reject")}

        assert forbidden.isdisjoint(ranked_ids), (
            f"{case['name']} leaked hard-rejected listings: "
            f"{forbidden.intersection(ranked_ids)}"
        )
        metrics = ranking_metrics(ranked_ids, relevance)
        case_metrics.append(metrics)
        assert metrics["recall_at_50"] >= 0.5, case["name"]

    aggregate = {
        name: sum(item[name] for item in case_metrics) / len(case_metrics)
        for name in case_metrics[0]
    }
    for name, expected in benchmark["baseline"].items():
        if name != "ranker":
            assert aggregate[name] == pytest.approx(expected, abs=1e-6)


def test_bm25_candidate_improves_ordering_without_metric_regression():
    benchmark = load_benchmark()
    case_metrics = []
    for case in benchmark["cases"]:
        candidates = case["candidates"]
        ranked = jobs.rank(
            [make_listing(candidate) for candidate in candidates],
            case["query"], limit=50, ranking_mode="bm25", **case["filters"],
        )
        ranked_ids = [item["id"].split(":", 1)[1] for item in ranked]
        relevance = {
            item["id"]: 0 if item.get("must_reject") else item["relevance"]
            for item in candidates
        }
        forbidden = {item["id"] for item in candidates if item.get("must_reject")}
        assert forbidden.isdisjoint(ranked_ids)
        assert all(item["bm25_score"] is not None for item in ranked)
        case_metrics.append(ranking_metrics(ranked_ids, relevance))

    aggregate = {
        name: sum(item[name] for item in case_metrics) / len(case_metrics)
        for name in case_metrics[0]
    }
    baseline = benchmark["baseline"]
    assert aggregate["precision_at_5"] >= baseline["precision_at_5"]
    assert aggregate["precision_at_10"] >= baseline["precision_at_10"]
    assert aggregate["recall_at_50"] >= baseline["recall_at_50"]
    assert aggregate["ndcg_at_10"] >= baseline["ndcg_at_10"] + 0.15
