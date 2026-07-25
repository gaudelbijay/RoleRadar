import pytest

from core.rrf_ranker import rank_positions, reciprocal_rank_fusion


def test_rank_positions_are_descending_stable_and_one_based():
    assert rank_positions([0.5, 0.9, 0.5]) == [2, 1, 3]


def test_rrf_rewards_a_consensus_winner_and_matches_formula():
    # B ranks second in BM25 and first semantically; neither ranker places it low.
    fused, positions = reciprocal_rank_fusion([
        [0.9, 0.8, 0.7],
        [0.7, 0.9, 0.8],
    ], k=60)
    assert positions == [[1, 2, 3], [3, 1, 2]]
    assert fused[1] > fused[0]
    assert fused[1] > fused[2]
    assert fused[1] == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_validates_inputs():
    with pytest.raises(ValueError, match="positive"):
        reciprocal_rank_fusion([[1.0]], k=0)
    with pytest.raises(ValueError, match="equal lengths"):
        reciprocal_rank_fusion([[1.0], [1.0, 2.0]])
    with pytest.raises(ValueError, match="finite"):
        rank_positions([float("nan")])
    assert reciprocal_rank_fusion([]) == ([], [])
