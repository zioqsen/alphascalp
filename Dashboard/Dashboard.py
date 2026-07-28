import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

st.set_page_config(
    page_title="ScalpBot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0d1117; }
    .block-container { padding: 1.5rem 2rem; }
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-label { font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { font-size: 26px; font-weight: 600; margin-top: 4px; }
    .metric-green { color: #3fb950; }
    .metric-red { color: #f85149; }
    .metric-blue { color: #58a6ff; }
    .metric-yellow { color: #e3b341; }
    .section-title { font-size: 14px; font-weight: 500; color: #8b949e; text-transform: uppercase;
                     letter-spacing: 0.08em; margin: 1.5rem 0 0.75rem; }
    .trade-win { color: #3fb950; }
    .trade-loss { color: #f85149; }
    .disclaimer {
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 0.75rem 1rem; font-size: 11px; color: #6e7681; margin-top: 2rem;
    }
    [data-testid="stDataFrame"] { border: 1px solid #30363d; border-radius: 8px; }
    h1, h2, h3 { color: #e6edf3 !important; }
    p, li { color: #c9d1d9; }
</style>
""", unsafe_allow_html=True)


# ─── LOAD DATA ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data(file):
    import os
    df_raw = pd.read_excel(file, header=None)
    trades_raw = df_raw.iloc[7:].copy()
    trades_raw.columns = [
        "open_time", "position_id", "symbol", "type",
        "volume", "open_price", "sl", "tp",
        "close_time", "close_price", "commission", "swap", "profit", "extra"
    ]
    # Garder seulement les lignes avec un profit numérique ET un volume numérique
    trades_raw["profit"] = pd.to_numeric(trades_raw["profit"], errors="coerce")
    trades_raw["volume"] = pd.to_numeric(trades_raw["volume"], errors="coerce")
    
    trades = trades_raw[
        trades_raw["profit"].notna() & 
        trades_raw["volume"].notna() &
        trades_raw["volume"] > 0
    ].copy()
    
    trades["open_time"] = pd.to_datetime(trades["open_time"], errors="coerce")
    trades["close_time"] = pd.to_datetime(trades["close_time"], errors="coerce")
    trades = trades[trades["open_time"].notna() & trades["close_time"].notna()]
    trades["win"] = trades["profit"] > 0
    trades["duration_min"] = (trades["close_time"] - trades["open_time"]).dt.total_seconds() / 60
    trades = trades.sort_values("close_time").reset_index(drop=True)
    trades["equity"] = 1000 + trades["profit"].cumsum()
    return trades
    
# ─── HEADER ────────────────────────────────────────────────────────────────────
col_logo, col_title, col_upload = st.columns([1, 5, 2])
with col_logo:
    st.markdown("## 📈")
with col_title:
    st.markdown("## ScalpBot — Performance Dashboard")
    st.markdown("<p style='color:#8b949e;font-size:13px;margin-top:-8px'>Compte démo · MetaQuotes · USD</p>", unsafe_allow_html=True)
with col_upload:
    uploaded = st.file_uploader("Charger un rapport MT5 (.xlsx)", type=["xlsx"], label_visibility="collapsed")

# Use uploaded file or fallback to default path
import os
DATA_PATH = os.path.join(os.path.dirname(__file__), "ReportHistory.xlsx")
if uploaded:
    trades = load_data(uploaded)
else:
    trades = load_data(DATA_PATH)

# ─── FILTERS ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Filtres</div>', unsafe_allow_html=True)
f1, f2, f3 = st.columns(3)
with f1:
    symbols = ["Tous"] + sorted(trades["symbol"].unique().tolist())
    sym_filter = st.selectbox("Symbole", symbols)
with f2:
    types = ["Tous", "buy", "sell"]
    type_filter = st.selectbox("Direction", types)
with f3:
    date_range = st.date_input(
        "Période",
        value=(trades["close_time"].min().date(), trades["close_time"].max().date())
    )

# Apply filters
df = trades.copy()
if sym_filter != "Tous":
    df = df[df["symbol"] == sym_filter]
if type_filter != "Tous":
    df = df[df["type"] == type_filter]
if len(date_range) == 2:
    df = df[(df["close_time"].dt.date >= date_range[0]) & (df["close_time"].dt.date <= date_range[1])]

df["equity"] = 1000 + df["profit"].cumsum()

# ─── KPI CARDS ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Métriques clés</div>', unsafe_allow_html=True)

total_profit = df["profit"].sum()
win_rate = df["win"].mean() * 100 if len(df) > 0 else 0
nb_trades = len(df)
gross_win = df[df["profit"] > 0]["profit"].sum()
gross_loss = abs(df[df["profit"] < 0]["profit"].sum())
profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
avg_win = df[df["profit"] > 0]["profit"].mean() if df["win"].sum() > 0 else 0
avg_loss = abs(df[df["profit"] < 0]["profit"].mean()) if (~df["win"]).sum() > 0 else 0
rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0

# Drawdown
equity_curve = df["equity"]
roll_max = equity_curve.cummax()
drawdown = (equity_curve - roll_max) / roll_max * 100
max_dd = drawdown.min() if len(drawdown) > 0 else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
def kpi(col, label, value, cls):
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {cls}">{value}</div>
    </div>""", unsafe_allow_html=True)

profit_cls = "metric-green" if total_profit >= 0 else "metric-red"
kpi(c1, "Profit Net", f"${total_profit:+.2f}", profit_cls)
kpi(c2, "Win Rate", f"{win_rate:.1f}%", "metric-blue")
kpi(c3, "Nb Trades", str(nb_trades), "metric-yellow")
kpi(c4, "Profit Factor", f"{profit_factor:.2f}", "metric-green" if profit_factor > 1 else "metric-red")
kpi(c5, "Ratio R/R", f"{rr_ratio:.2f}", "metric-blue")
kpi(c6, "Max Drawdown", f"{max_dd:.1f}%", "metric-red")

# ─── CHARTS ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Equity Curve</div>', unsafe_allow_html=True)

fig_equity = go.Figure()
fig_equity.add_trace(go.Scatter(
    x=df["close_time"], y=df["equity"],
    mode="lines", name="Equity",
    line=dict(color="#58a6ff", width=2),
    fill="tozeroy", fillcolor="rgba(88,166,255,0.07)"
))
fig_equity.update_layout(
    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
    font=dict(color="#c9d1d9"), height=280,
    margin=dict(l=0, r=0, t=10, b=0),
    xaxis=dict(gridcolor="#21262d", showgrid=True),
    yaxis=dict(gridcolor="#21262d", showgrid=True, tickprefix="$"),
    showlegend=False
)
st.plotly_chart(fig_equity, use_container_width=True)

ch1, ch2 = st.columns(2)

with ch1:
    st.markdown('<div class="section-title">Profit par trade</div>', unsafe_allow_html=True)
    colors = ["#3fb950" if p > 0 else "#f85149" for p in df["profit"]]
    fig_bar = go.Figure(go.Bar(
        x=list(range(1, len(df)+1)),
        y=df["profit"],
        marker_color=colors,
    ))
    fig_bar.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"), height=220,
        margin=dict(l=0, r=0, t=5, b=0),
        xaxis=dict(gridcolor="#21262d", title="Trade #"),
        yaxis=dict(gridcolor="#21262d", tickprefix="$"),
        showlegend=False
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with ch2:
    st.markdown('<div class="section-title">Répartition Win / Loss</div>', unsafe_allow_html=True)
    wins = df["win"].sum()
    losses = len(df) - wins
    fig_pie = go.Figure(go.Pie(
        labels=["Gagnants", "Perdants"],
        values=[wins, losses],
        marker_colors=["#3fb950", "#f85149"],
        hole=0.5,
        textinfo="label+percent"
    ))
    fig_pie.update_layout(
        paper_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"), height=220,
        margin=dict(l=0, r=0, t=5, b=0),
        showlegend=False
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# Profit by symbol
if len(df["symbol"].unique()) > 1:
    st.markdown('<div class="section-title">Profit par symbole</div>', unsafe_allow_html=True)
    by_sym = df.groupby("symbol")["profit"].sum().reset_index()
    fig_sym = px.bar(by_sym, x="symbol", y="profit",
                     color="profit", color_continuous_scale=["#f85149","#3fb950"],
                     color_continuous_midpoint=0)
    fig_sym.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"), height=200,
        margin=dict(l=0, r=0, t=5, b=0),
        coloraxis_showscale=False,
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", tickprefix="$"),
    )
    st.plotly_chart(fig_sym, use_container_width=True)

# ─── TRADE HISTORY TABLE ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Historique des trades</div>', unsafe_allow_html=True)

table = df[["open_time","close_time","symbol","type","volume","open_price","close_price","profit","duration_min"]].copy()
table.columns = ["Ouverture","Clôture","Symbole","Direction","Volume","Prix entrée","Prix sortie","Profit ($)","Durée (min)"]
table["Profit ($)"] = table["Profit ($)"].round(2)
table["Durée (min)"] = table["Durée (min)"].round(1)
table["Ouverture"] = table["Ouverture"].dt.strftime("%d/%m %H:%M")
table["Clôture"] = table["Clôture"].dt.strftime("%d/%m %H:%M")

st.dataframe(
    table.sort_values("Clôture", ascending=False).reset_index(drop=True),
    use_container_width=True,
    height=300
)

# ─── DISCLAIMER ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ <strong>Avertissement :</strong> Ce dashboard présente des résultats obtenus sur compte démo. Les performances passées ne préjugent pas des performances futures. 
Le trading comporte un risque de perte en capital. Cet outil est un logiciel d'automatisation et ne constitue pas un conseil financier.
</div>
""", unsafe_allow_html=True)