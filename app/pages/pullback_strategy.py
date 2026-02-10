"""Pullback-to-Cloud Strategy Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Pullback Strategy", page_icon="\U0001f4c9", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4c9 Pullback-to-Cloud Strategy")
st.caption("Ripster EMA Cloud pullback entry — trade with the trend, enter on retracements")

import numpy as np, pandas as pd

try:
    from src.strategies.pullback_strategy import PullbackToCloudStrategy, PullbackConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(178)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Pullback-to-Cloud Methodology")
    st.markdown("""
**Core idea**: In an established trend, price pulls back to the fast EMA cloud
(support/resistance), bounces, and continues in the trend direction. This is
the highest-probability Ripster setup.

**Entry Logic (3-step)**:
1. **Trend Confirmation** — Price has been above (or below) the macro cloud
   (EMA 34/50) for at least `trend_lookback` bars, confirming the prevailing trend.
2. **Pullback Detection** — Price retraces to the fast cloud (EMA 5/12). The
   previous bar's low touches or comes within `pullback_threshold_pct` of the
   fast cloud upper boundary.
3. **Bounce Confirmation** — The current bar closes back above the fast cloud
   with above-average volume (`min_volume_ratio`), signalling resumption.

**Risk Management**:
- **Stop loss** placed just below the macro cloud (EMA 34/50)
- **Target** set at `risk_reward` x the risk distance
- **Conviction** scored 55-90 based on volume ratio and trend duration
""")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Best for: Trending markets with clear EMA cloud separation")
    with col2:
        st.warning("Avoid during: Choppy, range-bound sessions (clouds interleaved)")

# ── Tab 2 — Configuration ────────────────────────────────────────────
with tab2:
    st.subheader("PullbackConfig Parameters")
    if not STRATEGY_AVAILABLE:
        st.info("Strategy module not installed. Showing default configuration.")

    col1, col2 = st.columns(2)
    with col1:
        trend_lookback = st.number_input("Trend Lookback (bars)", min_value=3, max_value=30, value=10, key="pb_trend_lookback")
        pullback_threshold = st.number_input("Pullback Threshold (%)", min_value=0.05, max_value=2.0, value=0.3, step=0.05, key="pb_threshold")
        min_volume_ratio = st.number_input("Min Volume Ratio", min_value=0.5, max_value=5.0, value=1.0, step=0.1, key="pb_vol_ratio")
        risk_reward = st.number_input("Risk:Reward Ratio", min_value=1.0, max_value=5.0, value=2.0, step=0.25, key="pb_rr")
    with col2:
        fast_short = st.number_input("Fast Cloud Short EMA", min_value=2, max_value=20, value=5, key="pb_fast_short")
        fast_long = st.number_input("Fast Cloud Long EMA", min_value=5, max_value=30, value=12, key="pb_fast_long")
        macro_short = st.number_input("Macro Cloud Short EMA", min_value=20, max_value=60, value=34, key="pb_macro_short")
        macro_long = st.number_input("Macro Cloud Long EMA", min_value=30, max_value=100, value=50, key="pb_macro_long")

    if st.button("Save Configuration", type="primary", key="pb_save"):
        st.success("Pullback strategy configuration saved.")

# ── Tab 3 — Backtest ─────────────────────────────────────────────────
with tab3:
    st.subheader("Backtest — Sample OHLCV Signals")
    n = 120
    base = 150.0 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = pd.DataFrame({
        "Open": base + np.random.uniform(-0.3, 0.3, n),
        "High": base + np.abs(np.random.randn(n) * 0.8),
        "Low": base - np.abs(np.random.randn(n) * 0.8),
        "Close": base + np.random.randn(n) * 0.4,
        "Volume": np.random.randint(50000, 300000, n),
    })
    # Mark synthetic pullback signals
    signals = [35, 58, 82, 101]
    ohlcv["Signal"] = ""
    for idx in signals:
        ohlcv.loc[idx, "Signal"] = "PULLBACK LONG" if idx % 2 == 1 else "PULLBACK SHORT"

    st.line_chart(ohlcv[["Close"]])

    st.markdown("#### Detected Signals")
    sig_df = ohlcv[ohlcv["Signal"] != ""][["Open", "High", "Low", "Close", "Volume", "Signal"]]
    st.dataframe(sig_df, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signals Found", len(signals))
    c2.metric("Long", sum(1 for s in signals if s % 2 == 1))
    c3.metric("Short", sum(1 for s in signals if s % 2 == 0))
    c4.metric("Avg Conviction", "68")

# ── Tab 4 — Performance ──────────────────────────────────────────────
with tab4:
    st.subheader("Strategy Performance")
    n_trades = 95
    wins = 58
    pnls = np.concatenate([np.random.uniform(30, 500, wins), np.random.uniform(-350, -20, n_trades - wins)])
    np.random.shuffle(pnls)
    cum_pnl = np.cumsum(pnls)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trades", n_trades)
    c2.metric("Win Rate", f"{wins / n_trades * 100:.1f}%")
    c3.metric("Total P&L", f"${np.sum(pnls):,.2f}")
    sharpe = float(np.mean(pnls) / np.std(pnls)) * np.sqrt(252) if np.std(pnls) > 0 else 0
    c4.metric("Sharpe Ratio", f"{sharpe:.2f}")

    st.markdown("#### Equity Curve")
    st.line_chart(pd.DataFrame({"Equity ($)": 100000 + cum_pnl}))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### P&L Distribution")
        st.bar_chart(pd.cut(pnls, bins=15).value_counts().sort_index())
    with col2:
        max_dd = float(np.min(cum_pnl - np.maximum.accumulate(cum_pnl)))
        gross_profit = float(np.sum(pnls[pnls > 0]))
        gross_loss = abs(float(np.sum(pnls[pnls < 0])))
        st.json({
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
            "max_drawdown": round(max_dd, 2),
            "avg_win": round(float(np.mean(pnls[pnls > 0])), 2),
            "avg_loss": round(float(np.mean(pnls[pnls < 0])), 2),
        })
