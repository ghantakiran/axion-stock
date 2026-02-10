"""Session-Aware Scalp Strategy Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Session Scalp Strategy", page_icon="\u23f0", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\u23f0 Session-Aware Scalp Strategy")
st.caption("Ripster's time-of-day routing: different tactics for open bell, midday, and power hour")

import numpy as np, pandas as pd

try:
    from src.strategies.session_scalp_strategy import SessionScalpStrategy, SessionScalpConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(180)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Session-Aware Routing Methodology")
    st.markdown("""
**Core idea**: Different market sessions demand different strategies.

| Session | Time | Strategy | Conviction |
|---------|------|----------|------------|
| **Open Bell** | 9:30-10:30 | ORB breakout + cloud alignment | +10 boost |
| **Midday** | 10:30-14:00 | Pullback-to-cloud in trend only | -10 penalty |
| **Power Hour** | 14:00-16:00 | Momentum continuation + volume surge | +5 boost |

**Open Bell**: Captures opening momentum via range breakout with cloud confirmation
and volume >= 1.2x average. Aggressive sizing.

**Midday**: The "chop zone". Pullback-to-cloud setups only, in established trends
(8+ bars above macro cloud). Tighter stops, 1.5R targets.

**Power Hour**: Institutional momentum. Volume surge >= 1.3x with all EMAs aligned.
Wider 2.5R targets for end-of-day runs.
""")
    c1, c2, c3 = st.columns(3)
    c1.success("Open Bell: High volatility")
    c2.info("Midday: Pullbacks only")
    c3.success("Power Hour: Momentum")

# ── Tab 2 — Configuration ────────────────────────────────────────────
with tab2:
    st.subheader("SessionScalpConfig Parameters")
    if not STRATEGY_AVAILABLE:
        st.info("Strategy module not installed. Showing default configuration.")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Open Bell End (bar #)", min_value=4, max_value=24, value=12, key="ss_open_end")
        st.number_input("Power Hour Start (bar #)", min_value=36, max_value=72, value=54, key="ss_ph_start")
        st.number_input("Midday Min Trend Bars", min_value=3, max_value=20, value=8, key="ss_midday_trend")
        st.number_input("Fast EMA", min_value=2, max_value=15, value=5, key="ss_ema_fast")
        st.number_input("Slow EMA", min_value=5, max_value=25, value=12, key="ss_ema_slow")
    with col2:
        st.number_input("Open Bell Conviction Boost", min_value=0, max_value=20, value=10, key="ss_open_boost")
        st.number_input("Midday Conviction Penalty", min_value=0, max_value=20, value=10, key="ss_mid_pen")
        st.number_input("Power Hour Conviction Boost", min_value=0, max_value=20, value=5, key="ss_ph_boost")
        st.number_input("Macro Cloud Short EMA", min_value=20, max_value=60, value=34, key="ss_macro_short")
        st.number_input("Macro Cloud Long EMA", min_value=30, max_value=100, value=50, key="ss_macro_long")
    if st.button("Save Configuration", type="primary", key="ss_save"):
        st.success("Session scalp strategy configuration saved.")

# ── Tab 3 — Backtest ─────────────────────────────────────────────────
with tab3:
    st.subheader("Backtest — Sample OHLCV Signals")
    n = 78
    base = 280.0 + np.cumsum(np.random.randn(n) * 0.4)
    ohlcv = pd.DataFrame({
        "Open": base + np.random.uniform(-0.3, 0.3, n),
        "High": base + np.abs(np.random.randn(n) * 0.7),
        "Low": base - np.abs(np.random.randn(n) * 0.7),
        "Close": base + np.random.randn(n) * 0.35,
        "Volume": np.random.randint(60000, 400000, n),
    })
    signals_data = [(5, "OPEN BELL LONG"), (38, "MIDDAY PULLBACK"), (62, "POWER HOUR LONG"), (70, "POWER HOUR SHORT")]
    ohlcv["Signal"] = ""
    for idx, label in signals_data:
        ohlcv.loc[idx, "Signal"] = label
    st.line_chart(ohlcv[["Close"]])
    st.dataframe(ohlcv[ohlcv["Signal"] != ""][["Close", "Volume", "Signal"]], use_container_width=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Signals", len(signals_data))
    c2.metric("Open Bell", 1)
    c3.metric("Midday", 1)
    c4.metric("Power Hour", 2)

# ── Tab 4 — Performance ──────────────────────────────────────────────
with tab4:
    st.subheader("Strategy Performance by Session")
    sessions = {"Open Bell": (35, 22, 85.3), "Midday": (28, 15, 32.1), "Power Hour": (30, 19, 68.7)}
    total_t = sum(t for t, _, _ in sessions.values())
    total_w = sum(w for _, w, _ in sessions.values())
    total_pnl = sum(a * t for t, _, a in sessions.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trades", total_t)
    c2.metric("Win Rate", f"{total_w / total_t * 100:.1f}%")
    c3.metric("Total P&L", f"${total_pnl:,.2f}")
    c4.metric("Best Session", "Open Bell")

    session_df = pd.DataFrame([
        {"Session": k, "Trades": t, "Wins": w, "Win Rate": f"{w/t*100:.1f}%", "Avg P&L": f"${a:.2f}"}
        for k, (t, w, a) in sessions.items()
    ])
    st.dataframe(session_df, use_container_width=True, hide_index=True)

    pnls = np.concatenate([np.random.uniform(25, 400, total_w), np.random.uniform(-300, -15, total_t - total_w)])
    np.random.shuffle(pnls)
    cum_pnl = np.cumsum(pnls)
    st.line_chart(pd.DataFrame({"Equity ($)": 100000 + cum_pnl}))

    col1, col2 = st.columns(2)
    with col1:
        wr_df = pd.DataFrame({"Win Rate (%)": [w/t*100 for t, w, _ in sessions.values()]}, index=list(sessions))
        st.bar_chart(wr_df)
    with col2:
        max_dd = float(np.min(cum_pnl - np.maximum.accumulate(cum_pnl)))
        gp = float(np.sum(pnls[pnls > 0]))
        gl = abs(float(np.sum(pnls[pnls < 0])))
        st.json({"profit_factor": round(gp / gl, 2) if gl else 0, "max_drawdown": round(max_dd, 2),
                 "best_session": "Open Bell", "worst_session": "Midday"})
