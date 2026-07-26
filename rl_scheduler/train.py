"""Offline trainer for versioned scheduler transition files.

Usage:
    python -m rl_scheduler.train transitions.json scheduler-policy.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import Action, SearchState
from .policy import QLearningPolicy


def train_transitions(transitions: list[dict], *, epochs: int = 20,
                      policy: QLearningPolicy | None = None) -> QLearningPolicy:
    """Train from explicit, non-sensitive state transitions."""
    if epochs < 1:
        raise ValueError("epochs must be positive")
    policy = policy or QLearningPolicy()
    for _epoch in range(epochs):
        for item in transitions:
            state = SearchState(**item["state"])
            next_state = SearchState(**item["next_state"])
            policy.update(
                state, Action(item["action"]), float(item["reward"]),
                next_state, terminal=bool(item.get("terminal", False)),
            )
    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the job-source Q-learning policy offline")
    parser.add_argument("transitions", type=Path, help="Versioned JSON transition dataset")
    parser.add_argument("output", type=Path, help="Destination policy JSON")
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()
    payload = json.loads(args.transitions.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("transitions"), list):
        raise ValueError("transition dataset must use version 1")
    policy = train_transitions(payload["transitions"], epochs=args.epochs)
    policy.save(args.output)
    print(f"Saved {len(policy.q_values)} learned states to {args.output}")


if __name__ == "__main__":
    main()
