"""
Polymarket CLOB API client.
Fetches World Cup markets, prices, and order book data.

Docs: https://docs.polymarket.com/#clob-api
"""
import asyncio
import httpx
from typing import Optional
from config.settings import POLYMARKET_API_BASE, POLYMARKET_GAMMA_API, WC2026_SLUG_KEYWORDS


class PolymarketClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        )

    async def get_wc2026_markets(self) -> list[dict]:
        """
        Pull all active Polymarket markets related to World Cup 2026.
        Uses the Gamma API (market metadata) instead of CLOB (order execution).
        """
        markets = []
        for keyword in WC2026_SLUG_KEYWORDS:
            try:
                resp = await self._client.get(
                    f"{POLYMARKET_GAMMA_API}/markets",
                    params={"slug": keyword, "active": "true", "closed": "false"},
                )
                if resp.status_code == 200:
                    markets.extend(resp.json().get("markets", []))
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
                continue

        # Deduplicate by condition_id
        seen = set()
        unique = []
        for m in markets:
            cid = m.get("condition_id") or m.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                unique.append(m)
        return unique

    async def get_market_prices(self, condition_id: str) -> Optional[dict]:
        """
        Returns current YES/NO prices for a binary market from the CLOB.
        Price = implied probability (0–1).
        """
        try:
            resp = await self._client.get(
                f"{POLYMARKET_API_BASE}/markets/{condition_id}"
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
            return None
        if resp.status_code != 200:
            return None

        data = resp.json()
        tokens = data.get("tokens", [])
        prices = {}
        for token in tokens:
            outcome = token.get("outcome", "").upper()
            prices[outcome] = float(token.get("price", 0))

        return {
            "condition_id": condition_id,
            "question": data.get("question", ""),
            "prices": prices,
            "volume_24h": data.get("volume24hr", 0),
            "liquidity": data.get("liquidity", 0),
            "end_date": data.get("end_date_iso", ""),
            "status": data.get("active", False),
        }

    async def get_order_book(self, token_id: str) -> dict:
        """
        Raw order book for a specific token (YES or NO side).
        Useful to estimate slippage before executing a bet.
        """
        resp = await self._client.get(
            f"{POLYMARKET_API_BASE}/book",
            params={"token_id": token_id},
        )
        if resp.status_code != 200:
            return {}
        return resp.json()

    async def get_all_wc_markets_with_prices(self) -> list[dict]:
        """Full pipeline: markets + prices in one call."""
        markets = await self.get_wc2026_markets()
        enriched = []
        tasks = [self.get_market_prices(m.get("condition_id", m.get("id", ""))) for m in markets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for market, price_data in zip(markets, results):
            if isinstance(price_data, dict):
                market.update(price_data)
                enriched.append(market)

        return enriched

    async def close(self):
        await self._client.aclose()
