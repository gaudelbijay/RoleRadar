"""Small immutable state and configuration objects for source scheduling."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Action(str, Enum):
    """Actions permitted to a learned policy.

    Safety constraints are intentionally absent from the action space.
    """

    LAUNCH_NEXT = "launch_next"
    STOP_LAUNCHING = "stop_launching"


@dataclass(frozen=True)
class SchedulerConfig:
    """Hard scheduler limits that a learned policy cannot override."""

    initial_agents: int = 2
    max_parallel_agents: int = 2
    minimum_results: int = 5
    target_results: int = 15
    soft_deadline_seconds: float = 6.0
    hard_deadline_seconds: float = 15.0
    latency_penalty: float = 0.05
    source_call_penalty: float = 0.20
    failure_penalty: float = 1.0
    eligible_job_reward: float = 2.0

    def __post_init__(self):
        if self.initial_agents < 1:
            raise ValueError("initial_agents must be positive")
        if self.max_parallel_agents < self.initial_agents:
            raise ValueError("max_parallel_agents must be at least initial_agents")
        if self.minimum_results < 0 or self.target_results < self.minimum_results:
            raise ValueError("result targets are invalid")
        if not 0 < self.soft_deadline_seconds <= self.hard_deadline_seconds:
            raise ValueError("deadlines are invalid")


@dataclass(frozen=True)
class SearchState:
    """Non-sensitive numeric observation exposed to the policy."""

    elapsed_seconds: float
    fetched_jobs: int
    eligible_jobs: int
    completed_agents: int
    failed_agents: int
    active_agents: int
    remaining_agents: int

    def to_dict(self) -> dict:
        return asdict(self)

    def bucket(self) -> str:
        """Return a compact, stable state key for tabular Q-learning."""
        elapsed = min(5, int(self.elapsed_seconds // 3))
        eligible = min(5, self.eligible_jobs // 3)
        remaining = min(5, self.remaining_agents)
        failures = min(2, self.failed_agents)
        active = min(3, self.active_agents)
        return f"t{elapsed}|e{eligible}|r{remaining}|f{failures}|a{active}"
