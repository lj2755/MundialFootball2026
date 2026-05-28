"""Unit tests for the probability blending engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processing_layer.probability_engine import compute_final_estimate, ProbabilityEstimate


def make_analysis(market_prob=0.50, ai_prob=0.60, confidence="medium", outcome="team_a_wins"):
    return {
        "team_a": "Argentina",
        "team_b": "France",
        "outcome": outcome,
        "market_prob": market_prob,
        "estimated_prob": ai_prob,
        "edge": ai_prob - market_prob,
        "confidence": confidence,
        "bet_direction": "YES",
        "reasoning": "Test",
        "key_factors": [],
    }


def test_high_confidence_weights_ai_more():
    result = compute_final_estimate(make_analysis(confidence="high"), {}, news_count=10)
    assert result.ai_weight >= 0.60


def test_low_confidence_skips():
    result = compute_final_estimate(make_analysis(confidence="low"), {}, news_count=2)
    assert result.bet_direction == "SKIP"


def test_small_edge_skips():
    result = compute_final_estimate(make_analysis(market_prob=0.50, ai_prob=0.52, confidence="high"), {})
    assert result.bet_direction == "SKIP"


def test_negative_edge_gives_no():
    result = compute_final_estimate(make_analysis(market_prob=0.65, ai_prob=0.50, confidence="high"), {}, news_count=10)
    assert result.bet_direction == "NO"
    assert result.edge < 0


def test_high_liquidity_reduces_ai_weight():
    market_data = {"liquidity": 200_000}
    result = compute_final_estimate(make_analysis(confidence="high"), market_data, news_count=10)
    assert result.ai_weight <= 0.50


def test_final_prob_is_blend():
    result = compute_final_estimate(
        make_analysis(market_prob=0.40, ai_prob=0.60, confidence="medium"),
        {},
        news_count=5,
    )
    # Final prob should be between market and AI estimate
    assert 0.40 < result.final_prob < 0.60


def test_outcome_label_team_a():
    result = compute_final_estimate(make_analysis(outcome="team_a_wins"), {})
    assert "Argentina" in result.outcome_label


def test_outcome_label_draw():
    result = compute_final_estimate(make_analysis(outcome="draw"), {})
    assert result.outcome_label == "Draw"
