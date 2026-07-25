"""Small dependency-free information-retrieval metrics for ranking evaluation."""
from __future__ import annotations

import math


def precision_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int,
                   relevant_at: int = 1) -> float:
    """Return relevant fraction in the available top-k result window."""
    if k <= 0:
        raise ValueError("k must be positive")
    window = ranked_ids[:k]
    if not window:
        return 0.0
    return sum(relevance.get(item, 0) >= relevant_at for item in window) / len(window)


def recall_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int,
                relevant_at: int = 1) -> float:
    """Return the fraction of all labeled relevant documents found in top-k."""
    if k <= 0:
        raise ValueError("k must be positive")
    relevant = {item for item, grade in relevance.items() if grade >= relevant_at}
    if not relevant:
        return 1.0
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)


def dcg_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int) -> float:
    """Return graded discounted cumulative gain using exponential gain."""
    if k <= 0:
        raise ValueError("k must be positive")
    return sum(
        (2 ** relevance.get(item, 0) - 1) / math.log2(position + 2)
        for position, item in enumerate(ranked_ids[:k])
    )


def ndcg_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int) -> float:
    """Normalize DCG by the best ordering possible for the same judgments."""
    ideal_ids = [
        item for item, _grade in
        sorted(relevance.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    ideal = dcg_at_k(ideal_ids, relevance, k)
    return dcg_at_k(ranked_ids, relevance, k) / ideal if ideal else 1.0


def ranking_metrics(ranked_ids: list[str], relevance: dict[str, int]) -> dict[str, float]:
    """Return the project baseline metric set."""
    return {
        "precision_at_5": precision_at_k(ranked_ids, relevance, 5),
        "precision_at_10": precision_at_k(ranked_ids, relevance, 10),
        "recall_at_50": recall_at_k(ranked_ids, relevance, 50),
        "ndcg_at_10": ndcg_at_k(ranked_ids, relevance, 10),
    }
