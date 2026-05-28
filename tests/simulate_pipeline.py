"""
Simulación end-to-end del pipeline sin APIs externas ni .env.
Mockea: Polymarket, NewsAPI, y Claude — ejercita toda la lógica real.
"""
import sys, os, json, asyncio
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, patch, MagicMock
from processing_layer.ai_analyzer import analyze_match
from processing_layer.probability_engine import compute_final_estimate
from processing_layer.pipeline import _extract_teams_from_question

# ── Colores ANSI ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

def header(text): print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}\n{BOLD}{CYAN}  {text}{RESET}\n{BOLD}{CYAN}{'─'*60}{RESET}")
def ok(text):     print(f"  {GREEN}✓{RESET}  {text}")
def warn(text):   print(f"  {YELLOW}⚠{RESET}  {text}")
def info(text):   print(f"  {DIM}→{RESET}  {text}")

# ── Mock data ─────────────────────────────────────────────────────────────────
MOCK_MARKETS = [
    {
        "condition_id": "0xAAA001",
        "question": "Argentina vs France: Will Argentina win?",
        "prices": {"YES": 0.52, "NO": 0.48},
        "volume_24h": 280_000,
        "liquidity": 95_000,
        "end_date": "2026-07-19T22:00:00Z",
    },
    {
        "condition_id": "0xBBB002",
        "question": "Morocco vs Spain: Will Morocco win?",
        "prices": {"YES": 0.28, "NO": 0.72},
        "volume_24h": 88_000,
        "liquidity": 31_000,
        "end_date": "2026-07-15T18:00:00Z",
    },
    {
        "condition_id": "0xCCC003",
        "question": "Brazil vs Germany: Will Brazil win?",
        "prices": {"YES": 0.48, "NO": 0.52},
        "volume_24h": 195_000,
        "liquidity": 62_000,
        "end_date": "2026-07-17T22:00:00Z",
    },
]

MOCK_NEWS = {
    "Argentina": [
        {"title": "De Paul cleared to play after hamstring scare", "description": "Argentina's key midfielder passed fitness test Thursday.", "source": "ESPN", "published_at": "2026-07-12T09:00:00Z", "url": "https://espn.com/1"},
        {"title": "Messi rested in final group match, fully fit for knockout stage", "description": "Scaloni confirmed Messi is 100% available for the quarterfinal.", "source": "BBC Sport", "published_at": "2026-07-11T14:00:00Z", "url": "https://bbc.com/1"},
        {"title": "Argentina's back line: Romero and Martinez in dominant form", "description": "Only 1 goal conceded in 4 games. Defensive record best in tournament.", "source": "The Athletic", "published_at": "2026-07-10T11:00:00Z", "url": "https://theathletic.com/1"},
    ],
    "France": [
        {"title": "Giroud to miss quarterfinal with knee injury", "description": "France's target man ruled out — Thuram expected to lead the line.", "source": "L'Equipe", "published_at": "2026-07-12T07:00:00Z", "url": "https://lequipe.fr/1"},
        {"title": "France conceded 3 against Netherlands — Deschamps admits defensive issues", "description": "Upamecano caught out of position twice in the second half.", "source": "The Guardian", "published_at": "2026-07-11T20:00:00Z", "url": "https://guardian.com/1"},
    ],
    "Morocco": [
        {"title": "Morocco's defensive block ranks #1 for tackles won in tournament", "description": "Atlas Lions averaged 28 successful tackles per game — highest in Qatar 2026.", "source": "Opta", "published_at": "2026-07-12T08:00:00Z", "url": "https://opta.com/1"},
        {"title": "En-Nesyri: 'We are ready. Spain knows what we did in 2022'", "description": "Morocco's striker reminded the press of their penalty shootout win over Spain in Qatar.", "source": "AS", "published_at": "2026-07-11T16:00:00Z", "url": "https://as.com/1"},
    ],
    "Spain": [
        {"title": "Morata out — Spain's striker crisis deepens", "description": "Alvaro Morata fractured his right foot in training. Joselu called up.", "source": "Marca", "published_at": "2026-07-10T12:00:00Z", "url": "https://marca.com/1"},
    ],
    "Brazil": [
        {"title": "Vinicius Jr. carrying ankle knock — start uncertain vs Germany", "description": "Brazil's medical staff assessing the Real Madrid winger ahead of Thursday's tie.", "source": "Globo Esporte", "published_at": "2026-07-12T10:00:00Z", "url": "https://ge.com/1"},
    ],
    "Germany": [
        {"title": "Germany's gegenpressing disrupted Brazil's shape in 2014, Nagelsmann looking to repeat", "description": "Tactical analysis shows Germany's 4-2-3-1 is well-suited to nullify Brazil's wide threats.", "source": "Kicker", "published_at": "2026-07-11T09:00:00Z", "url": "https://kicker.de/1"},
    ],
}

MOCK_AI_RESPONSES = {
    "0xAAA001": {
        "team_a": "Argentina", "team_b": "France",
        "outcome": "team_a_wins",
        "market_prob": 0.52, "estimated_prob": 0.63,
        "edge": 0.11, "confidence": "high",
        "bet_direction": "YES",
        "reasoning": "De Paul fit and Messi rested = Argentina at full strength. France lost Giroud and showed defensive cracks (3 goals vs Netherlands). Market at 52% materially underprices Argentina's current form advantage.",
        "key_factors": ["De Paul cleared", "Giroud absent for France", "Argentina defense: 1 goal conceded in 4 games"],
        "data_source": "claude_analysis",
    },
    "0xBBB002": {
        "team_a": "Morocco", "team_b": "Spain",
        "outcome": "team_a_wins",
        "market_prob": 0.28, "estimated_prob": 0.40,
        "edge": 0.12, "confidence": "medium",
        "bet_direction": "YES",
        "reasoning": "Morocco defeated Spain on penalties in 2022 using the same defensive structure. Morata out removes Spain's aerial threat — their main plan B against low blocks. 28% is undervalued by 10–14 points.",
        "key_factors": ["2022 WC penalty win precedent", "Morata injury — Spain depth issue", "Morocco #1 tackles won in tournament"],
        "data_source": "claude_analysis",
    },
    "0xCCC003": {
        "team_a": "Brazil", "team_b": "Germany",
        "outcome": "unknown",
        "market_prob": 0.48, "estimated_prob": 0.46,
        "edge": -0.02, "confidence": "medium",
        "bet_direction": "SKIP",
        "reasoning": "Vinicius Jr. injury doubt materially reduces Brazil's threat but Germany's pressing suits this matchup regardless. Edge below 5% threshold — market is fairly priced here.",
        "key_factors": ["Vinicius Jr. ankle doubt", "Germany pressing neutralizes Brazil width", "Even historical record"],
        "data_source": "claude_analysis",
    },
}


# ── Simulation ─────────────────────────────────────────────────────────────────
async def simulate():
    print(f"\n{BOLD}{'═'*60}")
    print(f"  ⚽  MUNDIALFOOTBALL2026 — SIMULACIÓN DE PIPELINE")
    print(f"{'═'*60}{RESET}")

    # ── Capa 1: Extracción de equipos ─────────────────────────────────────────
    header("CAPA 1 · DATA LAYER — Parsing de mercados Polymarket")
    for m in MOCK_MARKETS:
        team_a, team_b = _extract_teams_from_question(m["question"])
        ok(f"Market {m['condition_id'][:8]}... → {team_a} vs {team_b}")
        info(f"YES: {m['prices']['YES']:.0%}  |  Liquidez: ${m['liquidity']:,}  |  Vol 24h: ${m['volume_24h']:,}")

    # ── Capa 2: Análisis IA ───────────────────────────────────────────────────
    header("CAPA 2 · PROCESSING LAYER — Análisis Claude + Probability Engine")

    results = []
    for market in MOCK_MARKETS:
        cid = market["condition_id"]
        team_a, team_b = _extract_teams_from_question(market["question"])

        # Simula Claude devolviendo el JSON mockeado
        mock_response_text = json.dumps(MOCK_AI_RESPONSES[cid])

        mock_content = MagicMock()
        mock_content.text = mock_response_text
        mock_message = MagicMock()
        mock_message.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        news_a = MOCK_NEWS.get(team_a, [])
        news_b = MOCK_NEWS.get(team_b, [])
        all_news = news_a + news_b

        with patch("processing_layer.ai_analyzer.client", mock_client):
            analysis = await analyze_match(team_a, team_b, market, all_news)

        estimate = compute_final_estimate(analysis, market, news_count=len(all_news))

        direction_color = GREEN if estimate.bet_direction == "YES" else (RED if estimate.bet_direction == "NO" else DIM)
        edge_str = f"{estimate.edge:+.1%}"

        print(f"\n  {BOLD}{team_a} vs {team_b}{RESET}")
        print(f"    Mercado:    {estimate.market_prob:.1%}")
        print(f"    IA (Claude):{estimate.ai_prob:.1%}")
        print(f"    Final:      {estimate.final_prob:.1%}  (IA weight: {estimate.ai_weight:.0%})")
        print(f"    Edge:       {BOLD}{direction_color}{edge_str}{RESET}")
        print(f"    Decisión:   {direction_color}{BOLD}{estimate.bet_direction}{RESET}  |  Confianza: {estimate.confidence}")
        print(f"    Razon:      {DIM}{estimate.reasoning[:90]}...{RESET}" if len(estimate.reasoning) > 90 else f"    Razón:      {DIM}{estimate.reasoning}{RESET}")
        print(f"    Factores:   {', '.join(estimate.key_factors)}")

        results.append({
            "match": f"{team_a} vs {team_b}",
            "edge": estimate.edge,
            "direction": estimate.bet_direction,
            "confidence": estimate.confidence,
            "final_prob": estimate.final_prob,
        })

    # ── Capa 3: Webhook ───────────────────────────────────────────────────────
    header("CAPA 3 · OUTPUT LAYER — Webhook + Dashboard")

    from execution_layer.webhook_server import start_webhook_server, get_latest_markets
    import requests, threading, time

    srv = start_webhook_server(port=8766)
    time.sleep(0.3)
    ok("Webhook server arrancado en puerto 8766")

    import httpx
    payload = [{"match": r["match"], "edge": r["edge"], "bet_direction": r["direction"]} for r in results]
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://localhost:8766/update", json=payload)
    ok(f"Pipeline → webhook POST: {resp.status_code} OK — {len(payload)} mercados enviados")

    import requests as req
    get_resp = req.get("http://localhost:8766/markets")
    received = get_resp.json()
    ok(f"Dashboard ← webhook GET: {len(received)} mercados disponibles para Streamlit")

    srv.shutdown()

    # ── Resumen ───────────────────────────────────────────────────────────────
    header("RESUMEN DE OPORTUNIDADES")

    actionable = [r for r in results if r["direction"] != "SKIP"]
    skipped    = [r for r in results if r["direction"] == "SKIP"]

    print(f"\n  {'Partido':<30} {'Dirección':<8} {'Edge':>8}  {'Confianza'}")
    print(f"  {'─'*28} {'─'*8} {'─'*8}  {'─'*10}")
    for r in sorted(results, key=lambda x: abs(x["edge"]), reverse=True):
        color = GREEN if r["direction"] == "YES" else (RED if r["direction"] == "NO" else DIM)
        flag  = "★" if abs(r["edge"]) >= 0.08 else " "
        print(f"  {r['match']:<30} {color}{r['direction']:<8}{RESET} {r['edge']:>+8.1%}  {r['confidence']}  {flag}")

    print(f"\n  {GREEN}Apuestas recomendadas: {len(actionable)}{RESET}")
    print(f"  {DIM}Skipped (edge bajo):   {len(skipped)}{RESET}")

    if actionable:
        best = max(actionable, key=lambda x: abs(x["edge"]))
        print(f"\n  {BOLD}Mayor oportunidad:{RESET} {best['match']}  →  {GREEN}{best['direction']}{RESET}  edge {best['edge']:+.1%}")

    print(f"\n{BOLD}{GREEN}  ✓ Simulación completada — todas las capas funcionando{RESET}\n")


if __name__ == "__main__":
    asyncio.run(simulate())
