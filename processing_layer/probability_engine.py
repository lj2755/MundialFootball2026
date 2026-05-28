"""
Probability engine — combines AI estimate with market price using a weighted blend.

Market prices on Polymarket are reasonably efficient but can lag news by hours.
The AI model ingests fresh news and adjusts the estimate.

Blend formula:
  final_prob = (ai_weight * ai_prob) + (market_weight * market_prob)

Weights adjust based on:
  - News volume (more news → trust AI more)
  - Market liquidity (more liquidity → trust market more)
  - AI confidence level
"""
from dataclasses import dataclass


CONFIDENCE_AI_WEIGHT = {
    "high": 0.65,
    "medium": 0.45,
    "low": 0.20,
}

# Minimum USD liquidity to give market its maximum weight
LIQUIDITY_FULL_TRUST_THRESHOLD = 50_000


@dataclass
class ProbabilityEstimate:
    team_a: str
    team_b: str
    market_prob: float
    ai_prob: float
    final_prob: float
    edge: float           # final_prob - market_prob
    bet_direction: str    # YES / NO / SKIP
    confidence: str
    ai_weight: float
    market_weight: float
    reasoning: str
    key_factors: list[str]
    outcome_label: str


def compute_final_estimate(
    ai_analysis: dict,
    market_data: dict,
    news_count: int = 0,
) -> ProbabilityEstimate:
    """
    Takes raw AI analysis dict + market data and returns a blended ProbabilityEstimate.
    """
    confidence = ai_analysis.get("confidence", "low")
    ai_prob = float(ai_analysis.get("estimated_prob", 0.5))
    market_prob = float(ai_analysis.get("market_prob", 0.5))

    # Base AI weight from confidence
    ai_weight = CONFIDENCE_AI_WEIGHT.get(confidence, 0.20)

    # Scale down AI weight if there's very little news
    if news_count < 3:
        ai_weight = min(ai_weight, 0.25)

    # Scale down AI weight if market is very liquid (market knows more)
    liquidity = market_data.get("liquidity", 0)
    if liquidity > LIQUIDITY_FULL_TRUST_THRESHOLD:
        # High liquidity market → cap AI weight at 50%
        ai_weight = min(ai_weight, 0.50)

    market_weight = 1.0 - ai_weight
    final_prob = ai_weight * ai_prob + market_weight * market_prob
    edge = final_prob - market_prob

    # Re-evaluate direction based on blended edge
    if abs(edge) < 0.05 or confidence == "low":
        bet_direction = "SKIP"
    elif edge > 0:
        bet_direction = "YES"
    else:
        bet_direction = "NO"

    team_a = ai_analysis.get("team_a", "Team A")
    team_b = ai_analysis.get("team_b", "Team B")
    raw_outcome = ai_analysis.get("outcome", "unknown")

    outcome_label_map = {
        "team_a_wins": f"{team_a} wins",
        "team_b_wins": f"{team_b} wins",
        "draw": "Draw",
    }
    outcome_label = outcome_label_map.get(raw_outcome, raw_outcome)

    return ProbabilityEstimate(
        team_a=team_a,
        team_b=team_b,
        market_prob=market_prob,
        ai_prob=ai_prob,
        final_prob=final_prob,
        edge=edge,
        bet_direction=bet_direction,
        confidence=confidence,
        ai_weight=ai_weight,
        market_weight=market_weight,
        reasoning=ai_analysis.get("reasoning", ""),
        key_factors=ai_analysis.get("key_factors", []),
        outcome_label=outcome_label,
    )
