"""Dependency-free Reciprocal Rank Fusion for aligned ranking score lists."""
from __future__ import annotations

import math


def rank_positions(scores: list[float]) -> list[int]:
    """Return stable one-based rank positions for descending finite scores."""
    if not all(math.isfinite(float(score)) for score in scores):
        raise ValueError("RRF input scores must be finite")
    order = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))
    positions = [0] * len(scores)
    for rank, index in enumerate(order, 1):
        positions[index] = rank
    return positions


def reciprocal_rank_fusion(score_lists: list[list[float]], k: int = 60) -> tuple[list[float], list[list[int]]]:
    """Fuse aligned rankings without comparing their incompatible raw scores."""
    if k <= 0:
        raise ValueError("RRF k must be positive")
    if not score_lists:
        return [], []
    size = len(score_lists[0])
    if any(len(scores) != size for scores in score_lists):
        raise ValueError("RRF score lists must have equal lengths")
    positions = [rank_positions(scores) for scores in score_lists]
    fused = [
        sum(1.0 / (k + ranks[index]) for ranks in positions)
        for index in range(size)
    ]
    return fused, positions
