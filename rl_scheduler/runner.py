"""Bounded source runner controlled by a safe scheduling policy."""
from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable, Sequence

from .models import Action, SchedulerConfig, SearchState
from .policy import QLearningPolicy

Source = tuple[str, Callable[[str], list[dict]]]


@dataclass
class SchedulerResult:
    jobs: list[dict]
    errors: list[str]
    trace: list[dict]
    launched_agents: int
    skipped_agents: int
    elapsed_seconds: float
    source_records: list[dict]


def run_scheduled_sources(
    sources: Sequence[Source], query: str,
    eligible_count: Callable[[list[dict]], int],
    *, policy: QLearningPolicy | None = None,
    config: SchedulerConfig | None = None,
    log: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
) -> SchedulerResult:
    """Run source agents in adaptive waves and return an audit-safe trace."""
    config = config or SchedulerConfig()
    policy = policy or QLearningPolicy()
    if not sources:
        return SchedulerResult([], [], [], 0, 0, 0.0, [])

    started = clock()
    jobs: list[dict] = []
    errors: list[str] = []
    trace: list[dict] = []
    source_records: list[dict] = []
    remaining = list(sources)
    completed = failed = launched = 0
    active = {}
    stop_launching = False
    cached_job_count = -1
    cached_eligible_count = 0

    def state() -> SearchState:
        nonlocal cached_job_count, cached_eligible_count
        if len(jobs) != cached_job_count:
            cached_eligible_count = eligible_count(jobs)
            cached_job_count = len(jobs)
        return SearchState(
            elapsed_seconds=max(0.0, clock() - started),
            fetched_jobs=len(jobs),
            eligible_jobs=cached_eligible_count,
            completed_agents=completed,
            failed_agents=failed,
            active_agents=len(active),
            remaining_agents=len(remaining),
        )

    def launch_one(pool) -> bool:
        nonlocal launched
        if not remaining or len(active) >= config.max_parallel_agents:
            return False
        name, fetcher = remaining.pop(0)
        log(f"[RL scheduler] launching source agent: {name}")
        active[pool.submit(fetcher, query)] = (name, clock())
        launched += 1
        return True

    with ThreadPoolExecutor(max_workers=config.max_parallel_agents) as pool:
        for _ in range(min(config.initial_agents, len(remaining))):
            launch_one(pool)

        while active:
            done, _pending = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                name, source_started = active.pop(future)
                source_failed = False
                try:
                    batch = future.result()
                    jobs.extend(batch)
                    log(f"[source agent: {name}] collected {len(batch)} listings")
                except Exception as exc:
                    source_failed = True
                    failed += 1
                    errors.append(f"{name}: {exc}")
                    log(f"[source agent: {name}] failed: {exc}")
                    batch = []
                completed += 1
                source_seconds = max(0.0, clock() - source_started)
                source_records.append({
                    "name": name,
                    "elapsed_seconds": round(source_seconds, 4),
                    "jobs": batch,
                    "error": errors[-1] if source_failed else "",
                })
                current = state()
                trace.append({
                    "event": "source_completed",
                    "source": name,
                    "source_seconds": round(source_seconds, 4),
                    "failed": source_failed,
                    "state": current.to_dict(),
                })

            if stop_launching:
                continue
            # Decide only after the current wave completes. A fast first source
            # must not trigger another call before its already-running peers
            # have contributed their yield.
            if active:
                continue
            current = state()
            action = policy.choose(current, config, explore=False)
            # Hard deadline is enforced outside the learned policy.
            if (current.elapsed_seconds >= config.hard_deadline_seconds
                    and current.eligible_jobs >= config.minimum_results):
                action = Action.STOP_LAUNCHING
            trace.append({
                "event": "decision",
                "action": action.value,
                "state": current.to_dict(),
            })
            if action == Action.STOP_LAUNCHING:
                stop_launching = True
                log(f"[RL scheduler] stopping new agents with {current.eligible_jobs} verified candidates")
            else:
                # Fill the full parallel budget for this wave instead of adding
                # one source at a time. Launching a single source per decision
                # serialized every expansion wave behind its predecessor, which
                # is what made sparse queries call every source sequentially.
                while launch_one(pool):
                    pass

    elapsed = max(0.0, clock() - started)
    return SchedulerResult(
        jobs=jobs,
        errors=errors,
        trace=trace,
        launched_agents=launched,
        skipped_agents=len(remaining),
        elapsed_seconds=elapsed,
        source_records=source_records,
    )
