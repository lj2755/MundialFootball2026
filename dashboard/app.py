"""
MundialFootball2026 Dashboard
Streamlit UI — elegante, dark-theme, datos en tiempo real desde el webhook.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import asyncio
import requests
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

from config.settings import WEBHOOK_PORT, EXECUTION_MODE, AUTO_THRESHOLD
from execution_layer.wallet_connector import WalletConnector
from execution_layer.bet_executor import BetExecutor

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mundial 2026 · Betting Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — dark theme with green accents ────────────────────────────────
st.markdown("""
<style>
    /* ── Base ── */
    .stApp { background-color: #0e1117; color: #f0f4f8; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    /* Todos los textos generales que Streamlit genera */
    p, span, div, li, td, th,
    .stMarkdown, .stMarkdown p, .stMarkdown span,
    [class*="stText"], [class*="css-"] > p,
    .element-container p { color: #f0f4f8 !important; }

    /* Captions y textos secundarios — más tenues pero legibles */
    .stCaption, .stCaption p,
    [data-testid="stCaptionContainer"] p { color: #a0aec0 !important; }

    /* ── Headers ── */
    h1 { color: #00e676 !important; font-size: 2rem !important; font-weight: 800 !important; letter-spacing: -0.5px; }
    h2, h3, h4 { color: #ffffff !important; }

    /* ── Metric cards ── */
    div[data-testid="metric-container"] {
        background-color: #1a1f2e;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="metric-container"] label,
    div[data-testid="metric-container"] [data-testid="stMetricLabel"] p {
        color: #94a3b8 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"],
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] *  {
        color: #00e676 !important;
        font-size: 1.9rem !important;
        font-weight: 800;
        text-shadow: 0 0 20px rgba(0,230,118,0.3);
    }
    /* Delta — la flecha de cambio */
    div[data-testid="stMetricDelta"] *  { color: #38bdf8 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { background-color: #131825 !important; border-right: 1px solid #1e2a3a; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] div { color: #e2e8f0 !important; }
    /* Labels de inputs en sidebar */
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: #94a3b8 !important; }

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input {
        background-color: #1a1f2e !important;
        border-color: #2d3748 !important;
        color: #f0f4f8 !important;
    }
    .stSelectbox div[data-baseweb="select"] { background-color: #1a1f2e !important; }
    .stSelectbox span { color: #f0f4f8 !important; }

    /* Slider labels */
    .stSlider [data-testid="stTickBarMin"],
    .stSlider [data-testid="stTickBarMax"],
    .stSlider p { color: #a0aec0 !important; }

    /* Checkbox label */
    .stCheckbox span, .stCheckbox p { color: #e2e8f0 !important; }

    /* ── Expander ── */
    details { background-color: #1a1f2e !important; border: 1px solid #2d3748 !important; border-radius: 8px; }
    details summary { color: #e2e8f0 !important; }
    details summary p { color: #e2e8f0 !important; }

    /* ── Tablas / dataframe ── */
    .dataframe td, .dataframe th { color: #f0f4f8 !important; background-color: #1a1f2e !important; }

    /* ── Match cards ── */
    .match-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
        border: 1px solid #2d3748;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        transition: border-color 0.2s;
    }
    .match-card:hover { border-color: #00e676; }
    .match-card.high-edge { border-left: 4px solid #00e676; }
    .match-card.medium-edge { border-left: 4px solid #ffd600; }
    .match-card.skip { border-left: 4px solid #546e7a; }

    /* ── Bet size guide ── */
    .bet-guide {
        background: rgba(255,255,255,0.03);
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 10px 0 6px 0;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }
    .bet-guide-amount {
        font-size: 1.6rem;
        font-weight: 800;
        color: #00e676;
        line-height: 1;
        white-space: nowrap;
    }
    .bet-guide-label {
        font-size: 0.7rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 2px;
    }
    .bet-guide-text {
        font-size: 0.85rem;
        color: #cbd5e1;
        line-height: 1.5;
    }

    /* ── Badges ── */
    .badge-yes  { background: #00e676; color: #000 !important; padding: 3px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; }
    .badge-no   { background: #ff5252; color: #fff !important; padding: 3px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; }
    .badge-skip { background: #374151; color: #9ca3af !important; padding: 3px 12px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; }

    /* ── Confidence ── */
    .conf-high   { color: #00e676 !important; font-weight: 600; }
    .conf-medium { color: #ffd600 !important; font-weight: 600; }
    .conf-low    { color: #9ca3af !important; font-weight: 600; }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #00e676, #00bfa5);
        color: #000 !important;
        border: none;
        font-weight: 700;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
    }
    .stButton > button:hover { opacity: 0.9; }

    /* ── Divider ── */
    hr { border-color: #1e2a3a !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
if "wallet_address" not in st.session_state:
    st.session_state.wallet_address = ""
if "markets" not in st.session_state:
    st.session_state.markets = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None
if "bet_history" not in st.session_state:
    st.session_state.bet_history = []


# ── Data fetch from webhook ───────────────────────────────────────────────────
def fetch_markets_from_webhook() -> list[dict]:
    try:
        resp = requests.get(f"http://localhost:{WEBHOOK_PORT}/markets", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def plain_recommendation(market: dict) -> str:
    """
    Convierte los datos de un mercado en una frase corta y directa
    que cualquier usuario entiende sin saber qué es edge o liquidez.
    """
    direction   = market.get("bet_direction", "SKIP")
    team_a      = market.get("team_a", "?")
    team_b      = market.get("team_b", "?")
    market_prob = market.get("market_prob", 0.5)
    ai_prob     = market.get("ai_prob", 0.5)
    edge        = abs(market.get("edge", 0))
    confidence  = market.get("confidence", "low")
    liquidity   = market.get("liquidity", 0)

    if direction == "SKIP":
        return f"Sin ventaja clara — el precio del mercado refleja bien las probabilidades reales. No apuestes aquí."

    winner = team_a if direction == "YES" else team_b
    loser  = team_b if direction == "YES" else team_a

    # Cuánto descuento hay respecto al precio justo
    discount_pts = round(edge * 100)

    if confidence == "high" and edge >= 0.10:
        strength = "La mejor oportunidad del tablero."
    elif confidence == "high":
        strength = "Señal sólida respaldada por noticias recientes."
    elif confidence == "medium" and edge >= 0.07:
        strength = "Buena oportunidad con algo de incertidumbre."
    else:
        strength = "Oportunidad moderada — apuesta con monto conservador."

    liq_note = ""
    if liquidity < 15_000:
        liq_note = " Mercado con poco dinero: apuesta menos de $50 para no mover el precio."
    elif liquidity > 80_000:
        liq_note = " Mercado líquido: puedes apostar montos mayores sin problema."

    return (
        f"El mercado cree que {winner} tiene {market_prob:.0%} de ganar, "
        f"pero la IA estima {ai_prob:.0%} — {discount_pts} puntos de ventaja a tu favor. "
        f"{strength}{liq_note}"
    )


def bet_size_guide(liquidity: float, edge: float, confidence: str) -> dict:
    """
    Devuelve una guía de tamaño de apuesta en lenguaje llano según liquidez, edge y confianza.
    Regla base: nunca superar el 1.5% de la liquidez disponible para no mover el precio.
    """
    max_safe = liquidity * 0.015

    # Ajuste por confianza
    confidence_factor = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(confidence, 0.3)

    # Ajuste por edge — más ventaja permite apostar un poco más
    edge_factor = 1.0 if edge >= 0.10 else (0.75 if edge >= 0.07 else 0.5)

    suggested = max_safe * confidence_factor * edge_factor
    suggested = max(5.0, round(suggested / 5) * 5)  # redondear a múltiplos de 5, mínimo $5

    # Niveles de liquidez
    if liquidity >= 80_000:
        liq_level = "alta"
        liq_icon  = "🟢"
        liq_msg   = "Mercado con mucho dinero — tu apuesta no moverá el precio."
    elif liquidity >= 20_000:
        liq_level = "media"
        liq_icon  = "🟡"
        liq_msg   = "Mercado normal — apuestas moderadas sin problema."
    else:
        liq_level = "baja"
        liq_icon  = "🔴"
        liq_msg   = "Poco dinero en este mercado — apuesta montos pequeños para no encarecer el precio."

    # Consejo de riesgo según confianza
    risk_advice = {
        "high":   "La señal es fuerte. Puedes apostar cerca del máximo sugerido.",
        "medium": "Señal moderada. Quédate en la mitad del rango sugerido.",
        "low":    "Señal débil. Si apuestas, usa el mínimo.",
    }.get(confidence, "")

    return {
        "suggested": suggested,
        "max_safe": round(max_safe),
        "liq_level": liq_level,
        "liq_icon": liq_icon,
        "liq_msg": liq_msg,
        "risk_advice": risk_advice,
    }


def load_demo_data() -> list[dict]:
    """Returns demo data when pipeline isn't running — useful for UI testing."""
    return [
        {
            "condition_id": "0xdemo1",
            "question": "Will Argentina win vs France?",
            "team_a": "Argentina", "team_b": "France",
            "outcome_label": "Argentina wins",
            "market_prob": 0.52, "ai_prob": 0.61, "final_prob": 0.57,
            "edge": 0.05, "bet_direction": "YES",
            "confidence": "high",
            "ai_weight": 0.55, "market_weight": 0.45,
            "reasoning": "De Paul está disponible tras perderse dos partidos de grupo por una sobrecarga muscular. La defensa francesa mostró grietas claras ante Países Bajos (3 goles en contra), con Upamecano fuera de posición en dos ocasiones. El mercado no está valorando suficientemente la ventaja de Argentina como favorito continental.",
            "key_factors": ["De Paul recuperado al 100%", "Defensa francesa con problemas ante Países Bajos", "Argentina sin goles en contra en 4 de 5 partidos"],
            "volume_24h": 280000, "liquidity": 95000,
            "prices": {"YES": 0.52, "NO": 0.48},
            "news_count": 12, "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "condition_id": "0xdemo2",
            "question": "Will Brazil win vs Germany?",
            "team_a": "Brazil", "team_b": "Germany",
            "outcome_label": "Brazil wins",
            "market_prob": 0.48, "ai_prob": 0.44, "final_prob": 0.46,
            "edge": -0.02, "bet_direction": "SKIP",
            "confidence": "medium",
            "ai_weight": 0.45, "market_weight": 0.55,
            "reasoning": "Vinicius Jr. arrastra una molestia en el tobillo y el cuerpo técnico brasileño no ha confirmado su titularidad. El pressing de Alemania ha anulado el juego de bandas de Brasil en sus últimos dos encuentros directos. La ventaja está por debajo del umbral mínimo para recomendar apuesta.",
            "key_factors": ["Vinicius Jr. con molestia en tobillo — titular dudoso", "Presión alemana neutraliza el juego exterior de Brasil", "Historial igualado en últimos 4 encuentros"],
            "volume_24h": 195000, "liquidity": 62000,
            "prices": {"YES": 0.48, "NO": 0.52},
            "news_count": 9, "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "condition_id": "0xdemo3",
            "question": "Will Morocco win vs Spain?",
            "team_a": "Morocco", "team_b": "Spain",
            "outcome_label": "Morocco wins",
            "market_prob": 0.28, "ai_prob": 0.39, "final_prob": 0.34,
            "edge": 0.06, "bet_direction": "YES",
            "confidence": "medium",
            "ai_weight": 0.45, "market_weight": 0.55,
            "reasoning": "Marruecos neutralizó el tiki-taka español en Qatar 2022 usando el mismo bloque defensivo bajo y ganó en penales. La baja de Morata elimina la principal amenaza aérea de España contra bloques bajos. El mercado valora a Marruecos en un 28% cuando la probabilidad real está más cerca del 38-40%.",
            "key_factors": ["Precedente directo: victoria en penales ante España en Qatar 2022", "Baja de Morata — España sin referencia en el área", "Marruecos lidera el torneo en balones recuperados por partido"],
            "volume_24h": 88000, "liquidity": 31000,
            "prices": {"YES": 0.28, "NO": 0.72},
            "news_count": 7, "updated_at": datetime.utcnow().isoformat(),
        },
    ]


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ Mundial 2026")
    st.markdown("*Betting Intelligence*")
    st.divider()

    st.divider()

    # Refresh controls
    st.markdown("### 🔄 Datos")
    if st.button("Actualizar ahora"):
        data = fetch_markets_from_webhook()
        if data:
            st.session_state.markets = data
            st.session_state.last_refresh = datetime.utcnow()
        else:
            st.warning("Pipeline no activo — mostrando demo data")
            st.session_state.markets = load_demo_data()
            st.session_state.last_refresh = datetime.utcnow()

    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)

    if st.session_state.last_refresh:
        st.caption(f"Última actualización: {st.session_state.last_refresh.strftime('%H:%M:%S')} UTC")

    st.divider()
    st.markdown("### 🎯 Filtros")
    min_edge = st.slider("Diferencia de Probabilidad Mínima (%)", 0, 20, 4) / 100
    min_liquidity = st.selectbox("Liquidez mínima", ["Cualquiera", "$10K+", "$50K+", "$100K+"])
    liquidity_map = {"Cualquiera": 0, "$10K+": 10000, "$50K+": 50000, "$100K+": 100000}
    min_liq_val = liquidity_map[min_liquidity]

    show_skips = st.checkbox("Mostrar partidos sin ventaja  (< 5% diferencia IA vs Mercado)", value=False)


# ── Initial data load ─────────────────────────────────────────────────────────
if not st.session_state.markets:
    data = fetch_markets_from_webhook()
    st.session_state.markets = data if data else load_demo_data()
    st.session_state.last_refresh = datetime.utcnow()

markets = st.session_state.markets

# Auto-refresh
if auto_refresh:
    time.sleep(60)
    data = fetch_markets_from_webhook()
    if data:
        st.session_state.markets = data
    st.rerun()


# ── Modal ¿Cómo jugar? ────────────────────────────────────────────────────────
if "show_howto" not in st.session_state:
    st.session_state.show_howto = False

@st.dialog("¿Cómo jugar?")
def show_howto_modal():
    st.markdown("""
<style>
.step-box {
    background: linear-gradient(135deg, #1a1f2e, #16213e);
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
}
.step-number {
    display: inline-block;
    background: #00e676;
    color: #000;
    font-weight: 800;
    font-size: 0.85rem;
    width: 26px;
    height: 26px;
    line-height: 26px;
    text-align: center;
    border-radius: 50%;
    margin-right: 10px;
}
.step-title { font-size: 1rem; font-weight: 700; color: #ffffff; }
.step-body  { font-size: 0.9rem; color: #cbd5e1; margin-top: 8px; line-height: 1.6; }
</style>

<div class="step-box">
  <span class="step-number">1</span><span class="step-title">Elige comprar</span>
  <p class="step-body">Compra <b>Sí</b> o <b>No</b> según tu predicción. Las probabilidades cambian en tiempo real a medida que otros participantes apuestan.</p>
</div>

<div class="step-box">
  <span class="step-number">2</span><span class="step-title">Realiza una transacción</span>
  <p class="step-body">Financia tu cuenta con criptomonedas, tarjeta de débito o transferencia bancaria. Una vez listo, conecta tu wallet y empieza a operar.</p>
</div>

<div class="step-box">
  <span class="step-number">3</span><span class="step-title">Canjea tus ganancias</span>
  <p class="step-body">Vende tu posición en cualquier momento antes de que termine el partido, o espera al resultado final para canjear tus ganancias automáticamente.</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "<p style='text-align:center; color:#94a3b8; font-size:0.85rem;'>"
        "Crea una cuenta en Polymarket y realiza tu primera operación.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Ir a Polymarket →", use_container_width=True):
        st.markdown('<meta http-equiv="refresh" content="0; url=https://polymarket.com">', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🔗 Conectar tu wallet")
    st.caption("Una vez que tengas tu cuenta en Polymarket, pega aquí tu dirección para ver tu balance y ejecutar apuestas directamente desde el dashboard.")
    wallet_input = st.text_input(
        "Dirección Polygon (0x...)",
        value=st.session_state.wallet_address,
        placeholder="0x742d35Cc...",
        label_visibility="collapsed",
    )
    if wallet_input != st.session_state.wallet_address:
        st.session_state.wallet_address = wallet_input
        st.rerun()

    if st.session_state.wallet_address:
        try:
            wc = WalletConnector()
            if wc.is_connected():
                balance = wc.get_usdc_balance(st.session_state.wallet_address)
                st.success(f"✅ Wallet conectada · Balance: **${balance:,.2f} USDC**")
            else:
                st.warning("Sin conexión a Polygon RPC")
        except Exception:
            st.caption("Balance no disponible por ahora.")

    if st.button("Cerrar", use_container_width=True):
        st.rerun()


# ── Main header ───────────────────────────────────────────────────────────────
col_title, col_status, col_howto = st.columns([3, 1, 1])
with col_title:
    st.markdown("# ⚽ Mundial Football 2026")
    st.markdown(
        "<p style='font-size:1.05rem; margin-top:-8px;'>"
        "<span style='color:#00e676; font-weight:700;'>Probabilidad según IA</span>"
        "<span style='color:#4a5568; font-weight:400; margin:0 10px;'>vs</span>"
        "<span style='color:#38bdf8; font-weight:700;'>Probabilidad real del Mercado</span>"
        "</p>",
        unsafe_allow_html=True,
    )
with col_status:
    try:
        import requests as _req
        _req.get(f"http://localhost:{WEBHOOK_PORT}/health", timeout=1)
        pipeline_status = "🟢 En vivo"
        pipeline_color = "#00e676"
    except Exception:
        pipeline_status = "🟡 Demo"
        pipeline_color = "#ffd600"
    st.markdown(
        f"<div style='padding-top:20px; text-align:center;'>"
        f"<span style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em;'>Estado</span><br>"
        f"<span style='font-size:1.1rem; font-weight:700; color:{pipeline_color};'>{pipeline_status}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
with col_howto:
    st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
    if st.button("❓ ¿Cómo jugar?", use_container_width=True):
        show_howto_modal()
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()


# ── KPI strip ─────────────────────────────────────────────────────────────────
actionable = [m for m in markets if m.get("bet_direction") != "SKIP" and abs(m.get("edge", 0)) >= min_edge]
high_edge = [m for m in actionable if abs(m.get("edge", 0)) >= 0.08]
avg_edge = sum(abs(m.get("edge", 0)) for m in actionable) / len(actionable) if actionable else 0
total_volume = sum(m.get("volume_24h", 0) for m in markets)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric(
        "Apuestas Recomendadas",
        len(actionable),
        help="Partidos donde la IA detecta una ventaja real sobre el precio del mercado.",
    )
with k2:
    st.metric(
        "Ventaja Promedio",
        f"{avg_edge:.1%}",
        help="Cuántos puntos de probabilidad separan la estimación de la IA del precio que ofrece el mercado. Más alto = mejor oportunidad.",
    )
with k3:
    st.metric(
        "Oportunidades Fuertes",
        len(high_edge),
        help="Partidos con ventaja mayor al 8% — los de mayor convicción. Si solo vas a apostar en uno, empieza aquí.",
    )
with k4:
    st.metric(
        "Dinero en juego hoy",
        f"${total_volume:,.0f}",
        help="Total apostado en Polymarket en las últimas 24h en todos los partidos del Mundial.",
    )

st.divider()


# ── Mapa de Oportunidades ─────────────────────────────────────────────────────
if markets:
    st.markdown("### 🗺️ Mapa de Oportunidades")
    st.caption("Cada burbuja es un partido. Más arriba = mayor ventaja de la IA sobre el mercado. Más grande = más dinero apostado. Las verdes son las apuestas recomendadas.")

    df = pd.DataFrame(markets)
    df["edge_pct"] = df["edge"] * 100
    df["action"] = df["bet_direction"].map({"YES": "Apuesta recomendada", "NO": "Apuesta en contra", "SKIP": "Sin ventaja"})
    df["size"] = df["volume_24h"].clip(lower=1000).apply(lambda x: max(18, min(65, x / 4000)))
    df["label"] = df["team_a"] + " vs " + df["team_b"]
    df["market_pct"] = df["market_prob"] * 100
    df["hover_market"] = df["market_prob"].apply(lambda x: f"{x:.0%}")
    df["hover_ai"] = df["ai_prob"].apply(lambda x: f"{x:.0%}")
    df["hover_edge"] = df["edge_pct"].apply(lambda x: f"{x:+.1f}%")
    df["hover_conf"] = df["confidence"].map({"high": "Alta", "medium": "Media", "low": "Baja"})

    color_map = {
        "Apuesta recomendada": "#00e676",
        "Apuesta en contra":   "#ff5252",
        "Sin ventaja":         "#4a5568",
    }

    fig = go.Figure()

    # Zona verde de oportunidad (encima del umbral)
    fig.add_hrect(y0=5, y1=35, fillcolor="rgba(0,230,118,0.05)", line_width=0)
    fig.add_hrect(y0=-35, y1=-5, fillcolor="rgba(255,82,82,0.05)", line_width=0)

    # Líneas de umbral
    fig.add_hline(
        y=5, line_dash="dot", line_color="#00e676", line_width=1.5,
        annotation_text="  Ventaja mínima para apostar",
        annotation_font_color="#00e676", annotation_font_size=11,
        annotation_position="top left",
    )
    fig.add_hline(
        y=-5, line_dash="dot", line_color="#ff5252", line_width=1.5,
        annotation_text="  Mercado sobrevalora este resultado",
        annotation_font_color="#ff5252", annotation_font_size=11,
        annotation_position="bottom left",
    )
    fig.add_hline(y=0, line_color="#4a5568", line_width=1)

    # Puntos por categoría — de menos a más visibles
    for action, color, opacity in [
        ("Sin ventaja",         "#4a5568", 0.5),
        ("Apuesta en contra",   "#ff5252", 0.9),
        ("Apuesta recomendada", "#00e676", 1.0),
    ]:
        mask = df["action"] == action
        sub = df[mask]
        if sub.empty:
            continue

        # Glow: círculo exterior semitransparente para puntos accionables
        if action != "Sin ventaja":
            fig.add_trace(go.Scatter(
                x=sub["market_pct"], y=sub["edge_pct"],
                mode="markers",
                marker=dict(
                    size=sub["size"] * 1.8,
                    color=color,
                    opacity=0.15,
                    line_width=0,
                ),
                showlegend=False,
                hoverinfo="skip",
            ))

        fig.add_trace(go.Scatter(
            x=sub["market_pct"],
            y=sub["edge_pct"],
            mode="markers+text",
            name=action,
            text=sub["label"].apply(lambda s: s.replace(" vs ", "<br>")),
            textposition="top center",
            textfont=dict(size=10, color="#e2e8f0"),
            marker=dict(
                size=sub["size"],
                color=color,
                opacity=opacity,
                line=dict(width=1.5, color="rgba(255,255,255,0.3)"),
            ),
            customdata=sub[["hover_market", "hover_ai", "hover_edge", "hover_conf"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Mercado: %{customdata[0]}<br>"
                "IA estima: %{customdata[1]}<br>"
                "Ventaja: <b>%{customdata[2]}</b><br>"
                "Confianza: %{customdata[3]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        height=420,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#111827",
        font=dict(color="#e2e8f0", family="Inter, sans-serif"),
        legend=dict(
            bgcolor="rgba(26,31,46,0.9)",
            bordercolor="#2d3748",
            borderwidth=1,
            font=dict(size=12),
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
        ),
        margin=dict(l=50, r=20, t=50, b=50),
        xaxis=dict(
            title="Probabilidad según el mercado",
            ticksuffix="%",
            gridcolor="#1e2a3a",
            linecolor="#2d3748",
            range=[0, 100],
        ),
        yaxis=dict(
            title="Ventaja de la IA (%)",
            ticksuffix="%",
            gridcolor="#1e2a3a",
            linecolor="#2d3748",
            zeroline=False,
        ),
        hoverlabel=dict(
            bgcolor="#1a1f2e",
            bordercolor="#2d3748",
            font_size=13,
            font_color="#f0f4f8",
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

st.divider()


# ── Match cards ───────────────────────────────────────────────────────────────
st.markdown("### Partidos Activos")

# Filter
filtered = []
for m in markets:
    if abs(m.get("edge", 0)) < min_edge and m.get("bet_direction") != "SKIP":
        continue
    if m.get("liquidity", 0) < min_liq_val:
        continue
    if not show_skips and m.get("bet_direction") == "SKIP":
        continue
    filtered.append(m)

# Sort by abs edge descending
filtered.sort(key=lambda x: abs(x.get("edge", 0)), reverse=True)

if not filtered:
    st.info("No hay partidos que cumplan los filtros actuales.")

for market in filtered:
    edge = market.get("edge", 0)
    direction = market.get("bet_direction", "SKIP")
    confidence = market.get("confidence", "low")

    card_class = "high-edge" if abs(edge) >= 0.08 else ("medium-edge" if abs(edge) >= 0.05 else "skip")
    badge_class = f"badge-{direction.lower()}"
    conf_class = f"conf-{confidence}"

    recommendation = plain_recommendation(market)
    direction_label = {"YES": "✅ Apuesta a favor", "NO": "❌ Apuesta en contra", "SKIP": "⏭ Pasar"}.get(direction, direction)
    confidence_label = {"high": "Alta", "medium": "Media", "low": "Baja"}.get(confidence, confidence)
    liquidity = market.get("liquidity", 0)
    liq_label = "Alta" if liquidity > 80_000 else ("Media" if liquidity > 20_000 else "Baja")
    liq_color = "#00e676" if liquidity > 80_000 else ("#ffd600" if liquidity > 20_000 else "#ff7043")

    st.markdown(f"""
    <div class="match-card {card_class}">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div>
                <span style="font-size:1.25rem; font-weight:700; color:#fff;">
                    {market.get('team_a','?')} <span style="color:#546e7a; font-weight:400;">vs</span> {market.get('team_b','?')}
                </span>
            </div>
            <div style="text-align:right; display:flex; flex-direction:column; gap:4px; align-items:flex-end;">
                <span class="{badge_class}">{direction_label}</span>
                <span style="font-size:0.78rem; color:#94a3b8;">Confianza <span class="{conf_class}">{confidence_label}</span> · Liquidez <span style="color:{liq_color}; font-weight:600;">{liq_label}</span></span>
            </div>
        </div>
        <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:10px 14px; margin-top:6px;">
            <span style="font-size:0.9rem; color:#e2e8f0; line-height:1.5;">{recommendation}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Lo que paga el mercado",
            f"{market.get('market_prob', 0):.0%}",
            help="La probabilidad implícita según el precio actual en Polymarket. Si el mercado dice 30%, por cada $1 apostado cobras $3.33 si gana.",
        )
    with col2:
        st.metric(
            "Lo que estima la IA",
            f"{market.get('ai_prob', 0):.0%}",
            help="La probabilidad calculada por la IA analizando noticias recientes. Si es mayor al precio del mercado, hay ventaja.",
        )
    with col3:
        st.metric(
            "Ventaja",
            f"{edge:+.1%}",
            delta=f"{edge:+.1%}",
            help="Diferencia entre la estimación de la IA y el precio del mercado. Positivo = el mercado está subvalorando este resultado.",
        )
    with col4:
        st.metric(
            "Dinero disponible",
            f"${market.get('liquidity', 0):,.0f}",
            help="Cuánto dinero hay para aceptar tu apuesta sin que el precio cambie. Con menos de $15K, apuesta montos pequeños.",
        )

    # ── Guía de tamaño de apuesta ─────────────────────────────────────────────
    if direction != "SKIP":
        guide = bet_size_guide(
            liquidity=market.get("liquidity", 0),
            edge=abs(edge),
            confidence=confidence,
        )
        st.markdown(f"""
        <div class="bet-guide">
            <div style="min-width:90px; text-align:center;">
                <div class="bet-guide-label">Apuesta sugerida</div>
                <div class="bet-guide-amount">${guide['suggested']:.0f}</div>
                <div style="font-size:0.72rem; color:#546e7a; margin-top:2px;">máx. seguro ${guide['max_safe']}</div>
            </div>
            <div style="border-left:1px solid #2d3748; padding-left:14px;">
                <div style="margin-bottom:4px;">{guide['liq_icon']} <span class="bet-guide-text"><b>Liquidez {guide['liq_level']}.</b> {guide['liq_msg']}</span></div>
                <div class="bet-guide-text">💡 {guide['risk_advice']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Probability comparison bar
    mp = market.get("market_prob", 0.5)
    ap = market.get("ai_prob", 0.5)

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="Mercado", x=["Mercado", "IA"], y=[mp, ap],
        marker_color=["#5c6bc0", "#00e676"],
        text=[f"{mp:.1%}", f"{ap:.1%}"],
        textposition="outside", textfont=dict(color="#e0e0e0"),
    ))
    fig_bar.update_layout(
        height=160, showlegend=False,
        paper_bgcolor="#0e1117", plot_bgcolor="#1a1f2e",
        font_color="#e0e0e0",
        margin=dict(l=5, r=5, t=5, b=5),
        yaxis=dict(range=[0, 1], tickformat=".0%", gridcolor="#2d3748"),
        xaxis=dict(gridcolor="#2d3748"),
    )
    st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_{market.get('condition_id','')}")

    with st.expander("📰 Análisis & Factores clave"):
        st.markdown(f"**Razonamiento:** {market.get('reasoning','')}")
        factors = market.get("key_factors", [])
        if factors:
            st.markdown("**Factores clave:**")
            for f in factors:
                st.markdown(f"- {f}")
        st.caption(f"Fuentes de noticias procesadas: {market.get('news_count', 0)} artículos | "
                   f"Peso IA: {market.get('ai_weight', 0):.0%} / Mercado: {market.get('market_weight', 0):.0%}")

    # Bet execution section
    if direction != "SKIP" and st.session_state.wallet_address:
        with st.expander("💸 Ejecutar apuesta"):
            bet_amount = st.number_input(
                "Cantidad USDC",
                min_value=1.0, max_value=1000.0, value=10.0, step=5.0,
                key=f"amount_{market.get('condition_id','')}",
            )
            expected_shares = bet_amount / max(market.get("prices", {}).get("YES", 0.5), 0.01)
            st.caption(f"Shares esperados: **{expected_shares:.2f}** | Pago si gana: **${expected_shares:.2f}**")

            if st.button("Ejecutar apuesta", key=f"bet_{market.get('condition_id','')}"):
                wc = WalletConnector()
                executor = BetExecutor(wc)
                token_id = market.get("prices", {}).get("YES_TOKEN_ID", "0")
                price = market.get("prices", {}).get("YES", 0.5)

                result = asyncio.run(executor.execute_bet(
                    condition_id=market.get("condition_id", ""),
                    token_id=token_id,
                    price=price,
                    size_usdc=bet_amount,
                ))

                if result.get("status") == "success":
                    st.success(f"✅ Apuesta ejecutada — Order ID: {result.get('order_id')}")
                    st.session_state.bet_history.append({
                        "match": f"{market.get('team_a')} vs {market.get('team_b')}",
                        "amount": bet_amount,
                        "price": price,
                        "direction": direction,
                        "tx": result.get("approve_tx", ""),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                elif result.get("status") == "pending_signature":
                    st.warning("🔏 Firma requerida en tu wallet")
                    st.json(result.get("approve_calldata", {}))
                    st.caption("Pega este calldata en MetaMask o tu wallet compatible con Polygon.")
                else:
                    st.error(f"Error: {result.get('message','')}")

    st.markdown("---")


# ── Bet history ───────────────────────────────────────────────────────────────
if st.session_state.bet_history:
    st.markdown("### 📋 Historial de Apuestas")
    hist_df = pd.DataFrame(st.session_state.bet_history)
    st.dataframe(hist_df, use_container_width=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"MundialFootball2026 · DevsTech · Datos: Polymarket CLOB API + NewsAPI · "
    f"Análisis: Claude {st.session_state.get('model','sonnet-4-6')} · "
    f"Última actualización: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M UTC') if st.session_state.last_refresh else 'Pendiente'}"
)
