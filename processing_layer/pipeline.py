"""
Main data pipeline orchestrator.
Runs data fetch + AI analysis + probability blending for all active WC2026 markets.
Pushes results to the webhook server for the dashboard to consume.
"""
import asyncio
import json
import logging
from datetime import datetime

import httpx

from data_layer import PolymarketClient, NewsClient
from processing_layer.ai_analyzer import analyze_match
from processing_layer.probability_engine import compute_final_estimate
from config.settings import WEBHOOK_PORT, POLYMARKET_REFRESH, NEWS_REFRESH

logger = logging.getLogger(__name__)

# Simple team name extraction from Polymarket question text
def _extract_teams_from_question(question: str) -> tuple[str, str]:
    """
    Polymarket questions look like: 'Will Brazil win vs Argentina?'
    or 'Brazil vs Argentina: Who wins?'
    This is a best-effort parser — adjust if Polymarket changes their format.
    """
    import re
    # Pattern: "Team A vs Team B"
    match = re.search(r"([A-Za-z\s]+)\s+vs\.?\s+([A-Za-z\s]+)", question)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Team A", "Team B"


async def run_pipeline_once(pm_client: PolymarketClient, news_client: NewsClient) -> list[dict]:
    """
    Single pipeline run — returns list of analysis results ready for dashboard.
    """
    markets = await pm_client.get_all_wc_markets_with_prices()
    if not markets:
        logger.warning("No World Cup markets found on Polymarket.")
        return []

    results = []
    for market in markets:
        question = market.get("question", "")
        condition_id = market.get("condition_id", market.get("id", ""))
        team_a, team_b = _extract_teams_from_question(question)

        # Fetch news for both teams
        news = await news_client.get_match_news(team_a, team_b)

        # AI analysis
        analysis = await analyze_match(team_a, team_b, market, news)

        # Blend probabilities
        estimate = compute_final_estimate(analysis, market, news_count=len(news))

        result = {
            "condition_id": condition_id,
            "question": question,
            "team_a": estimate.team_a,
            "team_b": estimate.team_b,
            "outcome_label": estimate.outcome_label,
            "market_prob": round(estimate.market_prob, 4),
            "ai_prob": round(estimate.ai_prob, 4),
            "final_prob": round(estimate.final_prob, 4),
            "edge": round(estimate.edge, 4),
            "bet_direction": estimate.bet_direction,
            "confidence": estimate.confidence,
            "ai_weight": round(estimate.ai_weight, 2),
            "market_weight": round(estimate.market_weight, 2),
            "reasoning": estimate.reasoning,
            "key_factors": estimate.key_factors,
            "volume_24h": market.get("volume_24h", 0),
            "liquidity": market.get("liquidity", 0),
            "prices": market.get("prices", {}),
            "end_date": market.get("end_date", ""),
            "news_count": len(news),
            "updated_at": datetime.utcnow().isoformat(),
        }
        results.append(result)
        logger.info(f"Processed: {team_a} vs {team_b} | edge={estimate.edge:.3f} | {estimate.bet_direction}")

    return results


async def push_to_webhook(results: list[dict]):
    """POST results to the local webhook server so the dashboard picks them up."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0)) as client:
        try:
            await client.post(
                f"http://localhost:{WEBHOOK_PORT}/update",
                content=json.dumps(results),
                headers={"Content-Type": "application/json"},
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            logger.warning("Webhook server not reachable — dashboard recibirá datos en el próximo ciclo.")


async def run_continuous(interval_seconds: int = POLYMARKET_REFRESH):
    """
    Continuous loop that refreshes data and pushes updates to the dashboard.
    Run this independently from the Streamlit dashboard.
    """
    pm_client = PolymarketClient()
    news_client = NewsClient()

    logger.info(f"Pipeline started — refreshing every {interval_seconds}s")

    try:
        while True:
            try:
                results = await run_pipeline_once(pm_client, news_client)
                await push_to_webhook(results)
                logger.info(f"Pipeline cycle complete — {len(results)} markets processed.")
            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)
    finally:
        await pm_client.close()
        await news_client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_continuous())
