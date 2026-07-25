"""Optional BM25 scoring for already-eligible job listings."""
from __future__ import annotations

import re

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # The deterministic ranker must remain usable without it.
    BM25Okapi = None

TOKEN = re.compile(r"(?:c\+\+|c#|[a-z0-9]+(?:[.-][a-z0-9]+)*)", re.I)


def tokenize(value: object) -> list[str]:
    """Tokenize technical text while retaining forms such as C++, C#, and ROS-2."""
    return [token.lower().replace("-", "") for token in TOKEN.findall(str(value or ""))]


def searchable_text(job: dict) -> str:
    """Build a field-weighted document without changing the source evidence."""
    title = str(job.get("title") or "")
    tags = " ".join(str(tag) for tag in job.get("tags", []) if tag)
    return " ".join([
        title, title, title, title,
        tags, tags,
        str(job.get("description") or ""),
        str(job.get("company") or ""),
        str(job.get("location") or ""),
    ])


def score_jobs(query: str, jobs: list[dict]) -> list[float]:
    """Return BM25 scores aligned with jobs, or raise when dependency is absent."""
    if BM25Okapi is None:
        raise RuntimeError("BM25 is unavailable; install rank-bm25")
    if not jobs:
        return []
    corpus = [tokenize(searchable_text(job)) for job in jobs]
    query_tokens = tokenize(query)
    if not query_tokens or not any(corpus):
        return [0.0] * len(jobs)
    model = BM25Okapi(corpus)
    return [float(score) for score in model.get_scores(query_tokens)]
