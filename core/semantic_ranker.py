"""Lazy local Sentence Transformer ranking with in-memory cosine similarity."""
from __future__ import annotations

import hashlib
import os
import threading

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_MODEL = None
_MODEL_NAME = None
_MODEL_LOCK = threading.Lock()


def semantic_text(job: dict) -> str:
    """Create controlled evidence text for one job without personal information."""
    tags = ", ".join(str(tag) for tag in job.get("tags", []) if tag)
    parts = [
        f"Title: {job.get('title') or ''}",
        f"Skills: {tags}",
        f"Description: {job.get('description') or ''}",
    ]
    return "\n".join(parts)[:6000]


def _load_model(model_name: str):
    global _MODEL, _MODEL_NAME
    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_NAME == model_name:
            return _MODEL
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
        except Exception as exc:
            raise RuntimeError(f"Semantic model unavailable: {type(exc).__name__}") from exc
        _MODEL, _MODEL_NAME = model, model_name
        return model


def _validated_matrix(value: object, expected_rows: int) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != expected_rows or matrix.shape[1] == 0:
        raise RuntimeError("Semantic model returned invalid embedding dimensions")
    if not np.isfinite(matrix).all():
        raise RuntimeError("Semantic model returned non-finite embeddings")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= 1e-12):
        raise RuntimeError("Semantic model returned a zero-length embedding")
    return matrix / norms


def score_jobs(query: str, jobs: list[dict], encoder=None,
               model_name: str | None = None) -> list[float]:
    """Return cosine scores aligned with jobs; embeddings live only for this call."""
    if not jobs:
        return []
    query = str(query or "").strip()
    if not query:
        return [0.0] * len(jobs)
    model_name = model_name or os.environ.get(
        "JOBSEARCH_EMBEDDING_MODEL", DEFAULT_MODEL
    )
    encoder = encoder or _load_model(model_name)

    hashes, unique_texts, unique_index = [], [], {}
    for job in jobs:
        text = semantic_text(job)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        hashes.append(digest)
        if digest not in unique_index:
            unique_index[digest] = len(unique_texts)
            unique_texts.append(text)
    try:
        encoded = encoder.encode(
            [query, *unique_texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Semantic encoding failed: {type(exc).__name__}") from exc
    matrix = _validated_matrix(encoded, 1 + len(unique_texts))
    query_vector, document_vectors = matrix[0], matrix[1:]
    unique_scores = document_vectors @ query_vector
    return [float(unique_scores[unique_index[digest]]) for digest in hashes]
