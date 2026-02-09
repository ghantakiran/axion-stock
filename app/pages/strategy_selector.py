"""Strategy Selector Dashboard (PRD-165).

4 tabs: Strategy Router, Mean Reversion Signals, ADX Analysis, A/B Comparison.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Strategy Selector", page_icon="🔀", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🔀 Strategy Selector")
st.caption("Dynamic routing between EMA Cloud and mean-reversion based on ADX trend strength")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(165)

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]

adx_values = np.random.uniform(5, 50, len(TICKERS))
rsi_values = np.random.uniform(20, 80, len(TICKERS))
conviction_scores = np.random.randint(30, 91, len(TICKERS))
z_scores = np.random.uniform(-2.5, 2.5, len(TICKERS))
bb_positions = np.random.uniform(0, 1, len(TICKERS))
prices = np.random.uniform(100, 600, len(TICKERS))


def classify_trend(adx):
    if adx >= 35:
        return "Strong"
    elif adx >= 20:
        return "Moderate"
    else:
        return "Weak"


def select_strategy(adx):
    if adx >= 25:
        return "ema_cloud"
    else:
        return "mean_reversion"


def strategy_reasoning(adx, strategy):
    if strategy == "ema_cloud":
        return f"ADX {adx:.1f} indicates trending market; EMA Cloud preferred"
    else:
        return f"ADX {adx:.1f} indicates range-bound market; mean-reversion preferred"


trend_strengths = [classify_trend(a) for a in adx_values]
strategies = [select_strategy(a) for a in adx_values]
confidences = [min(95, int(abs(a - 25) * 2 + 50)) for a in adx_values]
reasonings = [strategy_reasoning(a, s) for a, s in zip(adx_values, strategies)]

# Mean-reversion signal data
directions = np.where(rsi_values < 40, "Long", np.where(rsi_values > 60, "Short", "Neutral"))
entry_prices = prices.copy()
target_prices = np.where(
    directions == "Long",
    prices * (1 + np.random.uniform(0.02, 0.08, len(TICKERS))),
    np.where(
        directions == "Short",
        prices * (1 - np.random.uniform(0.02, 0.08, len(TICKERS))),
        prices,
    ),
)
stop_prices = np.where(
    directions == "Long",
    prices * (1 - np.random.uniform(0.01, 0.04, len(TICKERS))),
    np.where(
        directions == "Short",
        prices * (1 + np.random.uniform(0.01, 0.04, len(TICKERS))),
        prices,
    ),
)

# A/B comparison data
np.random.seed(1650)
n_ema_trades = 85
n_mr_trades = 65
ema_pnls = np.concatenate([
    np.random.uniform(50, 500, int(n_ema_trades * 0.62)),
    np.random.uniform(-300, -30, int(n_ema_trades * 0.38)),
])
mr_pnls = np.concatenate([
    np.random.uniform(50, 400, int(n_mr_trades * 0.58)),
    np.random.uniform(-250, -30, int(n_mr_trades * 0.42)),
])
np.random.shuffle(ema_pnls)
np.random.shuffle(mr_pnls)

# ═══════════════════════════════════════════════════════════════════════
# Dashboard Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Strategy Router",
    "Mean Reversion Signals",
    "ADX Analysis",
    "A/B Comparison",
])


# ── Tab 1: Strategy Router ─────────────────────────────────────────────

with tab1:
    st.subheader("Current Strategy Selection")

    m1, m2, m3 = st.columns(3)
    ema_count = sum(1 for s in strategies if s == "ema_cloud")
    mr_count = sum(1 for s in strategies if s == "mean_reversion")
    m1.metric("EMA Cloud Routed", ema_count)
    m2.metric("Mean Reversion Routed", mr_count)
    m3.metric("Avg ADX", f"{np.mean(adx_values):.1f}")

    regime_override = st.selectbox(
        "Regime Override",
        ["None (Auto)", "Force EMA Cloud", "Force Mean Reversion"],
        key="regime_override",
    )

    st.divider()

    router_df = pd.DataFrame({
        "Ticker": TICKERS,
        "ADX Value": [f"{a:.1f}" for a in adx_values],
        "Trend Strength": trend_strengths,
        "Selected Strategy": strategies if regime_override == "None (Auto)"
            else ["ema_cloud"] * len(TICKERS) if regime_override == "Force EMA Cloud"
            else ["mean_reversion"] * len(TICKERS),
        "Confidence": [f"{c}%" for c in confidences],
        "Reasoning": reasonings,
    })
    st.dataframe(router_df, use_container_width=True)


# ── Tab 2: Mean Reversion Signals ──────────────────────────────────────

with tab2:
    st.subheader("Mean Reversion Signal Scanner")

    mr_df = pd.DataFrame({
        "Ticker": TICKERS,
        "Direction": directions,
        "Conviction": conviction_scores,
        "RSI": [f"{r:.1f}" for r in rsi_values],
        "Z-Score": [f"{z:+.2f}" for z in z_scores],
        "BB Position": [f"{b:.2f}" for b in bb_positions],
        "Entry Price": [f"${p:.2f}" for p in entry_prices],
        "Target Price": [f"${t:.2f}" for t in target_prices],
        "Stop Price": [f"${s:.2f}" for s in stop_prices],
    })
    st.dataframe(mr_df, use_container_width=True)

    st.divider()
    st.subheader("Conviction Scores")
    conv_chart_df = pd.DataFrame({
        "Conviction": conviction_scores,
    }, index=TICKERS)
    st.bar_chart(conv_chart_df)

    col1, col2 = st.columns(2)
    with col1:
        long_count = sum(1 for d in directions if d == "Long")
        st.metric("Long Signals", long_count)
    with col2:
        short_count = sum(1 for d in directions if d == "Short")
        st.metric("Short Signals", short_count)


# ── Tab 3: ADX Analysis ───────────────────────────────────────────────

with tab3:
    st.subheader("ADX Values Across Universe")

    adx_chart_df = pd.DataFrame({
        "ADX": adx_values,
    }, index=TICKERS)
    st.bar_chart(adx_chart_df)

    st.divider()
    st.subheader("Trend Strength Distribution")

    strong_count = sum(1 for t in trend_strengths if t == "Strong")
    moderate_count = sum(1 for t in trend_strengths if t == "Moderate")
    weak_count = sum(1 for t in trend_strengths if t == "Weak")

    col1, col2, col3 = st.columns(3)
    col1.metric("Strong (ADX >= 35)", strong_count)
    col2.metric("Moderate (20-35)", moderate_count)
    col3.metric("Weak (ADX < 20)", weak_count)

    dist_df = pd.DataFrame({
        "Count": [strong_count, moderate_count, weak_count],
    }, index=["Strong", "Moderate", "Weak"])
    st.bar_chart(dist_df)

    st.divider()
    st.subheader("ADX Summary Statistics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Mean ADX", f"{np.mean(adx_values):.1f}")
    m2.metric("Median ADX", f"{np.median(adx_values):.1f}")
    m3.metric("Max ADX", f"{np.max(adx_values):.1f}")
    m4.metric("Min ADX", f"{np.min(adx_values):.1f}")


# ── Tab 4: A/B Comparison ─────────────────────────────────────────────

with tab4:
    st.subheader("Strategy Performance Comparison")

    ema_wins = sum(1 for p in ema_pnls if p > 0)
    mr_wins = sum(1 for p in mr_pnls if p > 0)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**EMA Cloud Strategy**")
        st.metric("Total Signals", len(ema_pnls))
        st.metric("Wins", ema_wins)
        st.metric("Win Rate", f"{ema_wins / len(ema_pnls) * 100:.1f}%")
        st.metric("Total P&L", f"${sum(ema_pnls):,.2f}")
        st.metric("Avg P&L", f"${np.mean(ema_pnls):,.2f}")

    with col2:
        st.markdown("**Mean Reversion Strategy**")
        st.metric("Total Signals", len(mr_pnls))
        st.metric("Wins", mr_wins)
        st.metric("Win Rate", f"{mr_wins / len(mr_pnls) * 100:.1f}%")
        st.metric("Total P&L", f"${sum(mr_pnls):,.2f}")
        st.metric("Avg P&L", f"${np.mean(mr_pnls):,.2f}")

    st.divider()
    st.subheader("Cumulative P&L")

    max_len = max(len(ema_pnls), len(mr_pnls))
    ema_cumulative = np.cumsum(np.pad(ema_pnls, (0, max_len - len(ema_pnls)), constant_values=0))
    mr_cumulative = np.cumsum(np.pad(mr_pnls, (0, max_len - len(mr_pnls)), constant_values=0))

    cumulative_df = pd.DataFrame({
        "EMA Cloud": ema_cumulative,
        "Mean Reversion": mr_cumulative,
    })
    st.line_chart(cumulative_df)

    # Summary
    better = "EMA Cloud" if sum(ema_pnls) > sum(mr_pnls) else "Mean Reversion"
    st.success(f"**{better}** has higher total P&L in this comparison period")
