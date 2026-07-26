import json

import pytest

from rl_scheduler import (
    Action, QLearningPolicy, SchedulerConfig, SearchState,
    run_scheduled_sources,
)
from rl_scheduler.policy import transition_reward
from rl_scheduler.train import train_transitions


def state(**overrides):
    values = {
        "elapsed_seconds": 2.0, "fetched_jobs": 4, "eligible_jobs": 2,
        "completed_agents": 1, "failed_agents": 0, "active_agents": 1,
        "remaining_agents": 3,
    }
    values.update(overrides)
    return SearchState(**values)


def test_cold_policy_uses_safe_stopping_rules():
    config = SchedulerConfig(minimum_results=5, target_results=10)
    policy = QLearningPolicy()
    assert policy.choose(state(eligible_jobs=2), config) == Action.LAUNCH_NEXT
    assert policy.choose(state(eligible_jobs=10), config) == Action.STOP_LAUNCHING
    assert policy.choose(
        state(elapsed_seconds=7, eligible_jobs=5), config
    ) == Action.STOP_LAUNCHING
    assert policy.choose(
        state(elapsed_seconds=20, eligible_jobs=0), config
    ) == Action.LAUNCH_NEXT


def test_q_update_and_policy_round_trip(tmp_path):
    policy = QLearningPolicy(alpha=1.0, gamma=0.0)
    current = state()
    following = state(eligible_jobs=6, completed_agents=2)
    policy.update(current, Action.LAUNCH_NEXT, 7.5, following)
    assert policy.q_values[current.bucket()][Action.LAUNCH_NEXT.value] == 7.5
    destination = tmp_path / "policy.json"
    policy.save(destination)
    loaded = QLearningPolicy.load(destination)
    assert loaded.q_values == policy.q_values
    assert json.loads(destination.read_text())["version"] == 1


def test_transition_reward_values_verified_yield_and_penalizes_cost():
    config = SchedulerConfig()
    reward = transition_reward(
        state(elapsed_seconds=1, eligible_jobs=1),
        state(elapsed_seconds=3, eligible_jobs=4),
        config, launched_source=True, source_failed=False,
    )
    assert reward == pytest.approx(6 - 0.1 - 0.2)


def test_scheduler_stops_launching_after_initial_sources_meet_target():
    calls = []

    def source(name, count):
        def fetch(_query):
            calls.append(name)
            return [{"id": f"{name}-{index}"} for index in range(count)]
        return name, fetch

    sources = [source("a", 6), source("b", 6), source("c", 10), source("d", 10)]
    result = run_scheduled_sources(
        sources, "engineer", lambda jobs: len(jobs),
        config=SchedulerConfig(initial_agents=2, max_parallel_agents=2,
                               minimum_results=5, target_results=10),
    )
    assert set(calls) == {"a", "b"}
    assert result.launched_agents == 2
    assert result.skipped_agents == 2
    assert len(result.jobs) == 12
    assert any(item.get("action") == "stop_launching" for item in result.trace)


def test_scheduler_launches_remaining_sources_when_yield_is_low():
    calls = []

    def fetch(name):
        def run(_query):
            calls.append(name)
            return []
        return run

    sources = [(name, fetch(name)) for name in ("a", "b", "c", "d")]
    result = run_scheduled_sources(
        sources, "niche role", lambda jobs: len(jobs),
        config=SchedulerConfig(initial_agents=2, max_parallel_agents=2,
                               minimum_results=5, target_results=10,
                               soft_deadline_seconds=30,
                               hard_deadline_seconds=60),
    )
    assert set(calls) == {"a", "b", "c", "d"}
    assert result.launched_agents == 4
    assert result.skipped_agents == 0


def test_hard_deadline_never_stops_with_zero_verified_results():
    calls = []

    def fetch(name):
        def run(_query):
            calls.append(name)
            return []
        return run

    sources = [(name, fetch(name)) for name in ("a", "b", "c")]
    ticks = iter([0.0, 0.0, 0.0, 0.2, 0.2, 0.3, 0.3, 0.4, 0.4, 0.5, 0.5])
    result = run_scheduled_sources(
        sources, "niche role", lambda jobs: 0,
        config=SchedulerConfig(
            initial_agents=2, max_parallel_agents=2,
            minimum_results=1, target_results=2,
            soft_deadline_seconds=0.05, hard_deadline_seconds=0.1,
        ),
        clock=lambda: next(ticks, 0.6),
    )
    assert set(calls) == {"a", "b", "c"}
    assert result.skipped_agents == 0


def test_offline_training_accepts_explicit_transitions():
    current = state()
    following = state(eligible_jobs=8, remaining_agents=2)
    policy = train_transitions([{
        "state": current.to_dict(), "action": "launch_next", "reward": 5.0,
        "next_state": following.to_dict(), "terminal": True,
    }], epochs=2, policy=QLearningPolicy(alpha=1.0, gamma=0.0))
    assert policy.q_values[current.bucket()]["launch_next"] == 5.0


def test_invalid_scheduler_limits_are_rejected():
    with pytest.raises(ValueError, match="max_parallel"):
        SchedulerConfig(initial_agents=3, max_parallel_agents=2)
