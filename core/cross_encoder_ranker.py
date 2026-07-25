"""Lazy local CrossEncoder scoring for a bounded candidate set."""
from __future__ import annotations

import os
import threading

import numpy as np

from core.semantic_ranker import semantic_text

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MAX_RERANK_CANDIDATES = 50
_MODEL = None
_MODEL_NAME = None
_MODEL_LOCK = threading.Lock()


def _load_model(model_name: str):
    global _MODEL, _MODEL_NAME
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_NAME == model_name:
            return _MODEL
        try:
            from sentence_transformers import CrossEncoder
            model = CrossEncoder(model_name)
        except Exception as exc:
            raise RuntimeError(f"CrossEncoder unavailable: {type(exc).__name__}") from exc
        _MODEL, _MODEL_NAME = model, model_name
        return model


def score_jobs(query: str, jobs: list[dict], encoder=None,
               model_name: str | None = None) -> list[float]:
    """Score at most 50 query-document pairs and return aligned finite values."""
    if len(jobs) > MAX_RERANK_CANDIDATES:
        raise ValueError(f"CrossEncoder accepts at most {MAX_RERANK_CANDIDATES} jobs")
    if not jobs:
        return []
    query = str(query or "").strip()
    if not query:
        return [0.0] * len(jobs)
    model_name = model_name or os.environ.get(
        "JOBSEARCH_CROSS_ENCODER_MODEL", DEFAULT_MODEL
    )
    encoder = encoder or _load_model(model_name)
    pairs = [(query, semantic_text(job)) for job in jobs]
    try:
        values = encoder.predict(pairs, show_progress_bar=False)
    except Exception as exc:
        raise RuntimeError(f"CrossEncoder prediction failed: {type(exc).__name__}") from exc
    scores = np.asarray(values, dtype=np.float32).reshape(-1)
    if scores.shape != (len(jobs),):
        raise RuntimeError("CrossEncoder returned invalid score dimensions")
    if not np.isfinite(scores).all():
        raise RuntimeError("CrossEncoder returned non-finite scores")
    return [float(score) for score in scores]
