import numpy as np
import pytest

import core.cross_encoder_ranker as reranker


class FakeCrossEncoder:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def predict(self, pairs, **kwargs):
        self.calls.append((pairs, kwargs))
        return self.values


def test_cross_encoder_scores_bounded_query_job_pairs():
    jobs = [
        {"title": "Robotics Engineer", "description": "Manipulation"},
        {"title": "Backend Engineer", "description": "Payments"},
    ]
    encoder = FakeCrossEncoder([2.5, -1.0])
    scores = reranker.score_jobs("robot learning", jobs, encoder=encoder)
    assert scores == pytest.approx([2.5, -1.0])
    pairs, kwargs = encoder.calls[0]
    assert pairs[0][0] == "robot learning"
    assert "Robotics Engineer" in pairs[0][1]
    assert kwargs["show_progress_bar"] is False


def test_cross_encoder_enforces_candidate_cap():
    jobs = [{"title": str(index)} for index in range(51)]
    with pytest.raises(ValueError, match="at most 50"):
        reranker.score_jobs("query", jobs, encoder=FakeCrossEncoder([]))


def test_cross_encoder_rejects_invalid_outputs():
    jobs = [{"title": "Engineer"}]
    with pytest.raises(RuntimeError, match="dimensions"):
        reranker.score_jobs("query", jobs, encoder=FakeCrossEncoder([1.0, 2.0]))
    with pytest.raises(RuntimeError, match="non-finite"):
        reranker.score_jobs("query", jobs, encoder=FakeCrossEncoder([np.nan]))
