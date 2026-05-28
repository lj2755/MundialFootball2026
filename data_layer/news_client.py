"""
News aggregator for World Cup 2026 teams.
Primary source: NewsAPI.org — grabs recent articles per team to feed the AI analysis layer.
"""
import httpx
from datetime import datetime, timedelta
from config.settings import NEWS_API_KEY

NEWSAPI_BASE = "https://newsapi.org/v2/everything"

# Map common team names to search queries that actually return relevant news
TEAM_SEARCH_QUERIES: dict[str, str] = {
    "Argentina": "Argentina selección fútbol mundial 2026",
    "Brazil": "Brasil seleccion futbol mundial 2026",
    "France": "France equipe nationale football coupe monde 2026",
    "England": "England national football team World Cup 2026",
    "Germany": "Germany Nationalmannschaft WM 2026",
    "Spain": "España seleccion futbol mundial 2026",
    "Portugal": "Portugal selecao futebol mundial 2026",
    "Netherlands": "Netherlands Oranje football World Cup 2026",
    "Uruguay": "Uruguay seleccion futbol mundial 2026",
    "Mexico": "Mexico seleccion futbol mundial 2026",
    "USA": "United States USMNT World Cup 2026",
    "Canada": "Canada soccer World Cup 2026",
    "Morocco": "Morocco Atlas Lions World Cup 2026",
    "Japan": "Japan national team World Cup 2026",
    "South Korea": "South Korea national team World Cup 2026",
    "Senegal": "Senegal national team World Cup 2026",
}


class NewsClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        )

    async def get_team_news(self, team_name: str, days_back: int = 7) -> list[dict]:
        """
        Returns up to 10 recent articles for a given team.
        Uses the team's search query or falls back to a generic one.
        """
        if not NEWS_API_KEY:
            return []

        query = TEAM_SEARCH_QUERIES.get(team_name, f"{team_name} football World Cup 2026")
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        try:
            resp = await self._client.get(
                NEWSAPI_BASE,
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "relevancy",
                    "language": "en",
                    "pageSize": 10,
                    "apiKey": NEWS_API_KEY,
                },
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
            return []

        if resp.status_code != 200:
            return []

        articles = resp.json().get("articles", [])
        return [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "source": a.get("source", {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
                "url": a.get("url", ""),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

    async def get_match_news(self, team_a: str, team_b: str) -> list[dict]:
        """News specifically about the matchup between two teams."""
        articles_a = await self.get_team_news(team_a, days_back=5)
        articles_b = await self.get_team_news(team_b, days_back=5)

        # Combine and sort by published date, deduplicate by URL
        seen_urls = set()
        combined = []
        for article in articles_a + articles_b:
            url = article.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                combined.append(article)

        combined.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        return combined[:15]

    async def close(self):
        await self._client.aclose()
