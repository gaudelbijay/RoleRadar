"""Constrained tabular Q-learning policy with deterministic cold-start behavior."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .models import Action, SchedulerConfig, SearchState


class QLearningPolicy:
    """Choose source-launch actions and learn from completed transitions.

    The live application performs inference only. Training is an explicit
    offline operation so user searches are never silently used for exploration.
    """

    def __init__(self, q_values: dict[str, dict[str, float]] | None = None,
                 alpha: float = 0.20, gamma: float = 0.90,
                 epsilon: float = 0.0, seed: int = 0):
        if not 0 < alpha <= 1 or not 0 <= gamma <= 1 or not 0 <= epsilon <= 1:
            raise ValueError("invalid Q-learning hyperparameters")
        self.q_values = q_values or {}
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self._random = random.Random(seed)

    @classmethod
    def load(cls, path: str | Path | None) -> "QLearningPolicy":
        if not path:
            return cls()
        policy_path = Path(path)
        if not policy_path.exists():
            return cls()
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("q_values"), dict):
            raise ValueError("unsupported RL scheduler policy format")
        return cls(q_values=payload["q_values"])

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "version": 1,
            "q_values": self.q_values,
        }, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def allowed_actions(state: SearchState) -> list[Action]:
        actions = [Action.STOP_LAUNCHING]
        if state.remaining_agents > 0:
            actions.insert(0, Action.LAUNCH_NEXT)
        return actions

    @staticmethod
    def fallback_action(state: SearchState, config: SchedulerConfig) -> Action:
        """Safe baseline used whenever a state has no learned values."""
        if state.remaining_agents <= 0:
            return Action.STOP_LAUNCHING
        if state.eligible_jobs >= config.target_results:
            return Action.STOP_LAUNCHING
        if (state.elapsed_seconds >= config.soft_deadline_seconds
                and state.eligible_jobs >= config.minimum_results):
            return Action.STOP_LAUNCHING
        # Never trade complete result loss for latency. If verified yield is
        # below the minimum, continue through the finite remaining source set.
        if (state.elapsed_seconds >= config.hard_deadline_seconds
                and state.eligible_jobs >= config.minimum_results):
            return Action.STOP_LAUNCHING
        return Action.LAUNCH_NEXT

    def choose(self, state: SearchState, config: SchedulerConfig,
               explore: bool = False) -> Action:
        actions = self.allowed_actions(state)
        key = state.bucket()
        values = self.q_values.get(key)
        if not values:
            return self.fallback_action(state, config)
        if explore and self._random.random() < self.epsilon:
            return self._random.choice(actions)
        return max(
            actions,
            key=lambda action: (float(values.get(action.value, 0.0)),
                                action == Action.STOP_LAUNCHING),
        )

    def update(self, state: SearchState, action: Action, reward: float,
               next_state: SearchState, terminal: bool = False) -> None:
        """Apply one standard Q-learning update for offline training."""
        key, next_key = state.bucket(), next_state.bucket()
        current = self.q_values.setdefault(key, {}).get(action.value, 0.0)
        next_actions = self.allowed_actions(next_state)
        future = 0.0 if terminal else max(
            self.q_values.get(next_key, {}).get(item.value, 0.0)
            for item in next_actions
        )
        target = float(reward) + self.gamma * future
        self.q_values[key][action.value] = current + self.alpha * (target - current)


def transition_reward(previous: SearchState, current: SearchState,
                      config: SchedulerConfig, launched_source: bool,
                      source_failed: bool) -> float:
    """Reward verified yield while charging latency, calls, and failures."""
    eligible_gain = max(0, current.eligible_jobs - previous.eligible_jobs)
    elapsed = max(0.0, current.elapsed_seconds - previous.elapsed_seconds)
    return (
        config.eligible_job_reward * eligible_gain
        - config.latency_penalty * elapsed
        - config.source_call_penalty * int(launched_source)
        - config.failure_penalty * int(source_failed)
    )
