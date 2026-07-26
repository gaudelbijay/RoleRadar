"""Paired replay evaluation for full, adaptive, and trained scheduler policies."""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from core.jobs import rank
from core.ranking_metrics import ranking_metrics

from .models import Action, SchedulerConfig, SearchState
from .policy import QLearningPolicy
from .replay import label_template, load_scenario


def _priority_sources(scenario):
    sources = list(scenario["sources"])
    return sorted(
        enumerate(sources),
        key=lambda item: (
            0 if "linkedin" in item[1]["name"].lower()
            or "indeed" in item[1]["name"].lower()
            or "google" in item[1]["name"].lower() else 1,
            item[0],
        ),
    )


def _ranked(scenario, jobs):
    settings = scenario["settings"]
    return rank(
        [dict(job) for job in jobs], scenario["query"],
        int(settings.get("max_results", 50)),
        settings.get("country", ""), settings.get("city", ""),
        int(settings.get("max_age_days", 10)), settings.get("education", "PhD"),
        search_type=settings.get("search_type", "Jobs"),
        minimum_salary=int(settings.get("minimum_salary", 0)),
        ranking_mode=settings.get("ranking_mode", "bm25"),
    )


def _quality(scenario, ranked_jobs):
    relevance = scenario.get("relevance") or {}
    ids = [str(job.get("id") or job.get("apply_url")) for job in ranked_jobs]
    if not relevance or any(value is None for value in relevance.values()):
        return None
    return ranking_metrics(ids, {str(key): int(value) for key, value in relevance.items()})


def _result(scenario, jobs, latency, calls, policy_name, trace):
    ranked_jobs = _ranked(scenario, jobs)
    return {
        "policy": policy_name,
        "modeled_latency_seconds": round(float(latency), 4),
        "source_calls": int(calls),
        "fetched_jobs": len(jobs),
        "verified_jobs": len(ranked_jobs),
        "unique_companies": len({job.get("company") for job in ranked_jobs if job.get("company")}),
        "ranked_ids": [str(job.get("id") or job.get("apply_url")) for job in ranked_jobs],
        "quality": _quality(scenario, ranked_jobs),
        "trace": trace,
    }


def evaluate_full(scenario):
    sources = scenario["sources"]
    jobs = [job for source in sources for job in source.get("jobs", [])]
    latency = max((float(source.get("elapsed_seconds", 0)) for source in sources), default=0)
    return _result(scenario, jobs, latency, len(sources), "full_parallel", [])


def evaluate_scheduled(scenario, policy, config, policy_name):
    ordered = [source for _index, source in _priority_sources(scenario)]
    remaining = list(ordered)
    jobs, trace = [], []
    completed = failed = calls = 0
    elapsed = 0.0

    def launch_wave(batch):
        nonlocal elapsed, calls, completed, failed
        if not batch:
            return
        # Sources in one wave run concurrently in the live runner, so the
        # wave's cost is its slowest member, not the sum of its members.
        elapsed += max(float(source.get("elapsed_seconds", 0)) for source in batch)
        for source in batch:
            calls += 1
            completed += 1
            failed += bool(source.get("error"))
            jobs.extend(source.get("jobs", []))

    launch_wave([remaining.pop(0) for _ in range(min(config.initial_agents, len(remaining)))])

    while True:
        verified = len(_ranked(scenario, jobs))
        state = SearchState(
            elapsed_seconds=elapsed, fetched_jobs=len(jobs), eligible_jobs=verified,
            completed_agents=completed, failed_agents=failed, active_agents=0,
            remaining_agents=len(remaining),
        )
        action = policy.choose(state, config, explore=False)
        if (elapsed >= config.hard_deadline_seconds
                and verified >= config.minimum_results):
            action = Action.STOP_LAUNCHING
        trace.append({"state": state.to_dict(), "action": action.value})
        if action == Action.STOP_LAUNCHING or not remaining:
            break
        # Mirrors run_scheduled_sources: an expansion wave fills the parallel
        # ceiling instead of adding one source at a time.
        launch_wave([remaining.pop(0) for _ in range(min(config.max_parallel_agents, len(remaining)))])

    return _result(scenario, jobs, elapsed, calls, policy_name, trace)


def _aggregate(results):
    if not results:
        return {}
    latency = [item["modeled_latency_seconds"] for item in results]
    quality = [item["quality"] for item in results if item["quality"] is not None]
    output = {
        "scenarios": len(results),
        "p50_latency_seconds": round(statistics.median(latency), 4),
        "p95_latency_seconds": round(sorted(latency)[max(0, int(0.95 * len(latency)) - 1)], 4),
        "mean_source_calls": round(statistics.mean(item["source_calls"] for item in results), 3),
        "mean_verified_jobs": round(statistics.mean(item["verified_jobs"] for item in results), 3),
        "empty_result_rate": round(sum(item["verified_jobs"] == 0 for item in results) / len(results), 4),
        "quality_scenarios": len(quality),
    }
    if quality:
        for metric in quality[0]:
            output[metric] = round(statistics.mean(item[metric] for item in quality), 6)
    return output


def promotion_gate(baseline, candidate):
    """Apply explicit product-release thresholds to aggregate metrics."""
    checks = {
        "latency_improves_20_percent": candidate["p50_latency_seconds"]
        <= 0.80 * baseline["p50_latency_seconds"],
        "source_calls_improve_25_percent": candidate["mean_source_calls"]
        <= 0.75 * baseline["mean_source_calls"],
        "empty_result_rate_not_worse": candidate["empty_result_rate"]
        <= baseline["empty_result_rate"],
    }
    if baseline.get("quality_scenarios") and candidate.get("quality_scenarios"):
        checks.update({
            "ndcg_at_10_within_1_percent": candidate["ndcg_at_10"]
            >= baseline["ndcg_at_10"] - 0.01,
            "recall_at_50_within_2_percent": candidate["recall_at_50"]
            >= baseline["recall_at_50"] - 0.02,
        })
    else:
        checks["quality_labels_available"] = False
    return {"passed": all(checks.values()), "checks": checks}


def evaluate_scenarios(scenarios, policy_path=None, config=None):
    config = config or SchedulerConfig()
    adaptive_policy = QLearningPolicy()
    trained_policy = QLearningPolicy.load(policy_path) if policy_path else None
    paired = []
    for scenario in scenarios:
        item = {
            "query": scenario["query"],
            "full_parallel": evaluate_full(scenario),
            "adaptive": evaluate_scheduled(
                scenario, adaptive_policy, config, "deterministic_adaptive"
            ),
        }
        if trained_policy and trained_policy.q_values:
            item["trained_rl"] = evaluate_scheduled(
                scenario, trained_policy, config, "trained_rl"
            )
        paired.append(item)
    policies = ["full_parallel", "adaptive"]
    if paired and "trained_rl" in paired[0]:
        policies.append("trained_rl")
    aggregate = {
        policy: _aggregate([item[policy] for item in paired])
        for policy in policies
    }
    gates = {"adaptive": promotion_gate(aggregate["full_parallel"], aggregate["adaptive"])}
    if "trained_rl" in aggregate:
        gates["trained_rl"] = promotion_gate(
            aggregate["full_parallel"], aggregate["trained_rl"]
        )
    return {
        "version": 1,
        "policy_loaded": "trained_rl" in aggregate,
        "aggregate": aggregate,
        "promotion_gates": gates,
        "paired_results": paired,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate scheduler policies on identical source recordings")
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--labels", type=Path, help="JSON mapping of scenario filename to job relevance maps")
    parser.add_argument("--label-template", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    scenarios = [load_scenario(path) for path in args.scenarios]
    if args.label_template:
        template = {
            path.name: label_template(scenario)
            for path, scenario in zip(args.scenarios, scenarios)
        }
        args.label_template.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    if args.labels:
        labels = json.loads(args.labels.read_text(encoding="utf-8"))
        for path, scenario in zip(args.scenarios, scenarios):
            scenario["relevance"] = labels.get(path.name, {})
    result = evaluate_scenarios(scenarios, args.policy)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
