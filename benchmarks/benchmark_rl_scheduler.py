"""Reproducible latency/call benchmark for the adaptive source scheduler.

The benchmark uses deterministic local source functions so network variance,
rate limits, and changing job-board contents do not obscure scheduler behavior.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rl_scheduler import SchedulerConfig, run_scheduled_sources


SCENARIOS = {
    "early_yield_sufficient": [
        ("source-a", 0.030, 8),
        ("source-b", 0.040, 7),
        ("source-c", 0.050, 4),
        ("source-d", 0.060, 3),
        ("source-e", 0.080, 2),
    ],
    "early_yield_insufficient": [
        ("source-a", 0.030, 0),
        ("source-b", 0.040, 0),
        ("source-c", 0.050, 2),
        ("source-d", 0.060, 3),
        ("source-e", 0.080, 10),
    ],
}


def source(spec):
    name, delay, count = spec

    def fetch(_query):
        time.sleep(delay)
        return [{"id": f"{name}-{index}"} for index in range(count)]

    return name, fetch


def run_all(specs):
    sources = [source(item) for item in specs]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        batches = list(pool.map(lambda item: item[1]("benchmark"), sources))
    elapsed = time.perf_counter() - started
    jobs = [job for batch in batches for job in batch]
    return {"seconds": elapsed, "calls": len(sources), "jobs": len(jobs)}


def run_adaptive(specs):
    result = run_scheduled_sources(
        [source(item) for item in specs], "benchmark", lambda jobs: len(jobs),
        config=SchedulerConfig(
            initial_agents=2, max_parallel_agents=2,
            minimum_results=5, target_results=15,
            soft_deadline_seconds=5, hard_deadline_seconds=10,
        ),
        log=lambda _message: None,
    )
    return {
        "seconds": result.elapsed_seconds,
        "calls": result.launched_agents,
        "jobs": len(result.jobs),
        "skipped": result.skipped_agents,
    }


def percentile(values, fraction):
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[position]


def summarize(samples):
    seconds = [item["seconds"] for item in samples]
    return {
        "p50_seconds": round(statistics.median(seconds), 4),
        "p95_seconds": round(percentile(seconds, 0.95), 4),
        "mean_calls": round(statistics.mean(item["calls"] for item in samples), 2),
        "mean_jobs": round(statistics.mean(item["jobs"] for item in samples), 2),
        "mean_skipped": round(statistics.mean(item.get("skipped", 0) for item in samples), 2),
    }


def benchmark(trials=10):
    output = {"version": 1, "trials": trials, "scenarios": {}}
    for name, specs in SCENARIOS.items():
        baseline = [run_all(specs) for _ in range(trials)]
        adaptive = [run_adaptive(specs) for _ in range(trials)]
        baseline_summary = summarize(baseline)
        adaptive_summary = summarize(adaptive)
        output["scenarios"][name] = {
            "all_sources": baseline_summary,
            "rl_scheduler": adaptive_summary,
            "p50_latency_change_percent": round(
                100 * (adaptive_summary["p50_seconds"] / baseline_summary["p50_seconds"] - 1), 2
            ),
            "source_call_change_percent": round(
                100 * (adaptive_summary["mean_calls"] / baseline_summary["mean_calls"] - 1), 2
            ),
        }
    return output


def main():
    parser = argparse.ArgumentParser(description="Benchmark adaptive source scheduling")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.trials < 2:
        raise ValueError("trials must be at least 2")
    result = benchmark(args.trials)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
