import pytest

import core.bm25_ranker as bm25


def test_tokenizer_preserves_common_technical_tokens():
    assert bm25.tokenize("C++ C# ROS-2 FastAPI") == ["c++", "c#", "ros2", "fastapi"]


def test_title_weighting_prioritizes_role_title_evidence():
    jobs = [
        {"title": "FastAPI Backend Engineer", "description": "Build services.", "tags": []},
        {"title": "Documentation Specialist", "description": "Write about FastAPI backend systems.", "tags": []},
        {"title": "Account Manager", "description": "Manage customer relationships.", "tags": []},
    ]
    scores = bm25.score_jobs("fastapi backend engineer", jobs)
    assert scores[0] > scores[1] > scores[2]


def test_missing_dependency_has_clear_failure(monkeypatch):
    monkeypatch.setattr(bm25, "BM25Okapi", None)
    with pytest.raises(RuntimeError, match="rank-bm25"):
        bm25.score_jobs("python", [{"title": "Python Engineer"}])
