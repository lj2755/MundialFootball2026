"""
AI analysis layer — uses Claude to synthesize news + market data into a betting recommendation.

Flow:
  1. Receive news articles + market prices for a match
  2. Build a structured prompt with all context
  3. Claude returns a JSON object: { estimated_prob, market_prob, edge, recommendation, reasoning }
  4. Recommendation is passed to the dashboard via the output layer
"""
import json
import re
import anthropic
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_ANALYSIS_MAX_TOKENS

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """Eres un analista profesional de apuestas deportivas especializado en fútbol internacional.
Tu trabajo es estimar la probabilidad real de un resultado en base a:
- Noticias recientes de ambos equipos (lesiones, forma, cambios en la convocatoria, estado anímico)
- Contexto histórico si está disponible
- La probabilidad implícita del mercado en Polymarket

Devuelve ÚNICAMENTE un objeto JSON válido. Sin markdown, sin texto fuera del JSON.

Esquema JSON:
{
  "team_a": "<string>",
  "team_b": "<string>",
  "outcome": "<team_a_wins | team_b_wins | draw>",
  "market_prob": <float 0-1>,
  "estimated_prob": <float 0-1>,
  "edge": <float, estimated_prob - market_prob>,
  "confidence": <"low" | "medium" | "high">,
  "bet_direction": <"YES" | "NO" | "SKIP">,
  "reasoning": "<2-3 oraciones en español: qué dicen las noticias, por qué existe o no la ventaja>",
  "key_factors": ["<factor1 en español>", "<factor2 en español>", "<factor3 en español>"]
}

Reglas:
- Si el edge en valor absoluto es < 0.05, pon bet_direction en SKIP sin excepción
- Si la confianza es baja, pon bet_direction en SKIP
- Sé conservador — un SKIP honesto vale más que una recomendación forzada
- El reasoning debe ser específico: "el equipo está en buena forma" no sirve — di qué forma, de qué fuente, en qué fecha
- Escribe reasoning y key_factors siempre en español
"""


def _build_user_prompt(
    team_a: str,
    team_b: str,
    market_data: dict,
    news_articles: list[dict],
) -> str:
    market_prob_a = market_data.get("prices", {}).get(team_a.upper(), 0)
    if not market_prob_a:
        # Try generic YES price
        market_prob_a = market_data.get("prices", {}).get("YES", 0)

    news_text = ""
    for i, art in enumerate(news_articles[:10], 1):
        news_text += f"\n[{i}] {art['source']} — {art['published_at'][:10] if art.get('published_at') else 'unknown'}\n"
        news_text += f"    Title: {art['title']}\n"
        if art.get("description"):
            news_text += f"    Summary: {art['description']}\n"

    return f"""Match: {team_a} vs {team_b}
Question on Polymarket: {market_data.get('question', f'Will {team_a} win?')}
Market-implied probability for {team_a}: {market_prob_a:.3f}
24h volume: ${market_data.get('volume_24h', 0):,.0f}
Liquidity: ${market_data.get('liquidity', 0):,.0f}

Recent news ({len(news_articles)} articles):
{news_text if news_text else "No news available."}

Analyze the above and return the JSON recommendation."""


async def analyze_match(
    team_a: str,
    team_b: str,
    market_data: dict,
    news_articles: list[dict],
) -> dict:
    """
    Main entry point. Returns structured analysis dict.
    Falls back to market-only estimate if Claude call fails.
    """
    user_prompt = _build_user_prompt(team_a, team_b, market_data, news_articles)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_ANALYSIS_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip accidental markdown code fences if Claude wraps output
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        result["data_source"] = "claude_analysis"
        return result

    except (json.JSONDecodeError, IndexError, anthropic.APIError) as e:
        # Graceful fallback: return market prices as-is with no recommendation
        market_prob = market_data.get("prices", {}).get("YES", 0.5)
        return {
            "team_a": team_a,
            "team_b": team_b,
            "outcome": "unknown",
            "market_prob": market_prob,
            "estimated_prob": market_prob,
            "edge": 0.0,
            "confidence": "low",
            "bet_direction": "SKIP",
            "reasoning": f"Analysis unavailable — using market price only. Error: {str(e)[:100]}",
            "key_factors": [],
            "data_source": "market_only_fallback",
        }
