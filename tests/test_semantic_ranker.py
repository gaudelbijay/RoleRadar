import numpy as np
import pytest

import core.semantic_ranker as semantic


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        return np.asarray(self.vectors, dtype=np.float32)


def test_cosine_scores_are_aligned_and_duplicate_text_is_encoded_once():
    jobs = [
        {"title": "Robot Learning Engineer", "description": "Manipulation"},
        {"title": "Backend Engineer", "description": "Payments"},
        {"title": "Robot Learning Engineer", "description": "Manipulation"},
    ]
    encoder = FakeEncoder([
        [1.0, 0.0],
        [0.8, 0.2],
        [0.0, 1.0],
    ])
    scores = semantic.score_jobs("robot learning", jobs, encoder=encoder)
    assert scores[0] == pytest.approx(scores[2])
    assert scores[0] > scores[1]
    assert len(encoder.calls[0][0]) == 3  # query plus two unique documents
    assert encoder.calls[0][1]["normalize_embeddings"] is True


def test_semantic_text_is_bounded_and_excludes_company_and_location():
    job = {"title": "Engineer", "description": "x" * 7000,
           "company": "Private Company", "location": "Home Address"}
    text = semantic.semantic_text(job)
    assert len(text) == 6000
    assert "Private Company" not in text
    assert "Home Address" not in text


def test_invalid_embeddings_fail_closed():
    job = [{"title": "Engineer", "description": "Robotics"}]
    with pytest.raises(RuntimeError, match="dimensions"):
        semantic.score_jobs("robotics", job, encoder=FakeEncoder([[1.0], [1.0], [1.0]]))
    with pytest.raises(RuntimeError, match="non-finite"):
        semantic.score_jobs("robotics", job, encoder=FakeEncoder([[1.0, 0.0], [np.nan, 1.0]]))
    with pytest.raises(RuntimeError, match="zero-length"):
        semantic.score_jobs("robotics", job, encoder=FakeEncoder([[1.0, 0.0], [0.0, 0.0]]))
