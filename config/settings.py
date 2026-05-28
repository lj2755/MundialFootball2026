"""
Central config — lee secrets desde Streamlit Cloud o desde .env local.
Streamlit Cloud tiene prioridad; .env es el fallback para desarrollo.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


def _secret(key: str, default: str = "") -> str:
    """
    Lee un secret en este orden:
    1. st.secrets (Streamlit Cloud)
    2. Variable de entorno / .env (local)
    3. Valor por defecto
    """
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")
NEWS_API_KEY      = _secret("NEWS_API_KEY")
ODDS_API_KEY      = _secret("ODDS_API_KEY")

# ── Polymarket ────────────────────────────────────────────────────────────────
POLYMARKET_API_BASE  = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
POLYGON_RPC_URL      = _secret("POLYGON_RPC_URL", "https://polygon-rpc.com")
USDC_CONTRACT        = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE         = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# ── Execution mode ────────────────────────────────────────────────────────────
EXECUTION_MODE = _secret("EXECUTION_MODE", "manual")
AUTO_THRESHOLD = float(_secret("AUTO_THRESHOLD", "0.08"))

# ── AI model ──────────────────────────────────────────────────────────────────
CLAUDE_MODEL                = "claude-sonnet-4-6"
CLAUDE_ANALYSIS_MAX_TOKENS  = 1024

# ── Refresh intervals (segundos) ──────────────────────────────────────────────
POLYMARKET_REFRESH = 60
NEWS_REFRESH       = 300

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_PORT = int(_secret("WEBHOOK_PORT", "8765"))

# ── Filtro de mercados World Cup 2026 ─────────────────────────────────────────
WC2026_SLUG_KEYWORDS = ["2026-world-cup", "world-cup-2026", "fifa-2026", "mundial-2026"]
