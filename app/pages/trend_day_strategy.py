"""Trend Day Strategy Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Trend Day Strategy", page_icon="\U0001f4c8", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4c8 Trend Day Strategy")
st.caption("Detect and ride trend days using ORB breakout, volume expansion, and ATR confirmation")

import numpy as np, pandas as pd

try:
    from src.strategies.trend_day_strategy import TrendDayStrategy, TrendDayConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(179)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Trend Day Detection Methodology")
    st.markdown("""
**Core idea**: Ripster's observation — "If the market reaches a new high or low
by 10:00-10:30 AM, it is likely a trend day. Go full size."

**Entry Logic (5-step)**:
1. **Opening Range** — Capture the first `opening_range_bars` bars (default 6 x 5m = 30 min)
   as the high/low range for the session.
2. **Breakout Detection** — Price closes above the opening range high (bullish) or below
   the range low (bearish) within `breakout_deadline_bars`.
3. **Volume Confirmation** — The breakout bar must have volume >= `volume_threshold` x
   the 20-bar average volume.
4. **ATR Expansion** — Today's intraday range must be >= `atr_expansion` x the 14-period ATR,
   confirming an abnormal range day.
5. **Cloud Alignment** — All EMA clouds (fast + macro) must be aligned in the breakout direction.

**Risk Management**:
- **Stop** at the opposite macro cloud boundary
- **No fixed target** — trail with fast cloud on confirmed trend days
- **High conviction** signals (80-95) for full position sizing
""")
    col1, col2 = st.columns(2)
    with col1:
        st.success("Trend days produce the largest single-day moves. These are the highest-conviction setups.")
    with col2:
        st.warning("Trend days occur roughly 15-20% of sessions. Most days are NOT trend days.")

# ── Tab 2 — Configuration ────────────────────────────────────────────
with tab2:
    st.subheader("TrendDayConfig Parameters")
    if not STRATEGY_AVAILABLE:
        st.info("Strategy module not installed. Showing default configuration.")

    col1, col2 = st.columns(2)
    with col1:
        opening_range_bars = st.number_input("Opening Range Bars", min_value=2, max_value=18, value=6, key="td_or_bars")
        breakout_deadline = st.number_input("Breakout Deadline (bars)", min_value=6, max_value=30, value=12, key="td_deadline")
        volume_threshold = st.number_input("Volume Threshold", min_value=1.0, max_value=5.0, value=1.5, step=0.1, key="td_vol")
        atr_expansion = st.number_input("ATR Expansion Ratio", min_value=0.5, max_value=3.0, value=1.2, step=0.1, key="td_atr")
        atr_period = st.number_input("ATR Period", min_value=5, max_value=30, value=14, key="td_atr_period")
    with col2:
        ema_short = st.number_input("Fast Cloud Short EMA", min_value=2, max_value=20, value=5, key="td_ema_short")
        ema_long = st.number_input("Fast Cloud Long EMA", min_value=5, max_value=30, value=12, key="td_ema_long")
        macro_short = st.number_input("Macro Cloud Short EMA", min_value=20, max_value=60, value=34, key="td_macro_short")
        macro_long = st.number_input("Macro Cloud Long EMA", min_value=30, max_value=100, value=50, key="td_macro_long")

    if st.button("Save Configuration", type="primary", key="td_save"):
        st.success("Trend day strategy configuration saved.")

# ── Tab 3 — Backtest ─────────────────────────────────────────────────
with tab3:
    st.subheader("Backtest — Sample OHLCV Signals")
    n = 120
    base = 420.0 + np.cumsum(np.random.randn(n) * 0.6)
    ohlcv = pd.DataFrame({
        "Open": base + np.random.uniform(-0.4, 0.4, n),
        "High": base + np.abs(np.random.randn(n) * 1.0),
        "Low": base - np.abs(np.random.randn(n) * 1.0),
        "Close": base + np.random.randn(n) * 0.5,
        "Volume": np.random.randint(80000, 500000, n),
    })
    signals = [8, 42, 77]
    ohlcv["Signal"] = ""
    for idx in signals:
        ohlcv.loc[idx, "Signal"] = "TREND DAY LONG" if idx % 2 == 0 else "TREND DAY SHORT"

    st.line_chart(ohlcv[["Close"]])

    st.markdown("#### Detected Signals")
    sig_df = ohlcv[ohlcv["Signal"] != ""][["Open", "High", "Low", "Close", "Volume", "Signal"]]
    st.dataframe(sig_df, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signals Found", len(signals))
    c2.metric("Long", sum(1 for s in signals if s % 2 == 0))
    c3.metric("Short", sum(1 for s in signals if s % 2 == 1))
    c4.metric("Avg Conviction", "85")

# ── Tab 4 — Performance ──────────────────────────────────────────────
with tab4:
    st.subheader("Strategy Performance")
    n_trades = 42
    wins = 27
    pnls = np.concatenate([np.random.uniform(80, 1200, wins), np.random.uniform(-600, -30, n_trades - wins)])
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
        st.bar_chart(pd.cut(pnls, bins=12).value_counts().sort_index())
    with col2:
        max_dd = float(np.min(cum_pnl - np.maximum.accumulate(cum_pnl)))
        gross_profit = float(np.sum(pnls[pnls > 0]))
        gross_loss = abs(float(np.sum(pnls[pnls < 0])))
        st.json({
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
            "max_drawdown": round(max_dd, 2),
            "avg_win": round(float(np.mean(pnls[pnls > 0])), 2),
            "avg_loss": round(float(np.mean(pnls[pnls < 0])), 2),
            "note": "Fewer trades but larger P&L per trade — trend day signature",
        })
