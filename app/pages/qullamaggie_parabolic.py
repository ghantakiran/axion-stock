"""Qullamaggie Parabolic Short Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Qullamaggie Parabolic Short", page_icon="\U0001f4a8", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4a8 Qullamaggie Parabolic Short")
st.caption("Shorting vertical exhaustion moves \u2014 VWAP failure entry, target 10/20 SMA")

import numpy as np, pandas as pd

try:
    from src.qullamaggie.parabolic_short_strategy import ParabolicShortStrategy
    from src.qullamaggie.config import ParabolicShortConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(202)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Parabolic Short Methodology")
    st.markdown("""
**Core idea**: A stock goes parabolic \u2014 surging 100%+ in under 20 bars with
3+ consecutive green days. This is unsustainable. When the first red candle
prints or price fails at VWAP, short the exhaustion.

**Entry Criteria**:
1. **Surge** \u2014 Price up \u2265100% within the last 20 bars.
2. **Consecutive Up Days** \u2014 \u22653 green candles in a row before exhaustion.
3. **Exhaustion Signal** \u2014 First red candle OR close below VWAP.
4. **Short entry** at the close of the exhaustion bar.

**Risk Management**:
- **Stop** at the high of the exhaustion day
- **Target** the 10 or 20 SMA (gravity pulls price back to mean)
- Higher win rate than long setups (~40-50%) but smaller R-multiples
""")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Best for: Small-cap runners, meme stocks, parabolic crypto names")
    with col2:
        st.warning("Danger: Unlimited risk on shorts \u2014 size small, stop tight")

# ── Tab 2 — Configuration ─────────────────────────────────────────────
with tab2:
    st.subheader("Strategy Configuration")
    if STRATEGY_AVAILABLE:
        cfg = ParabolicShortConfig()
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Surge Min %", value=cfg.surge_min_pct, key="ps_surge")
            st.number_input("Surge Max Bars", value=cfg.surge_max_bars, key="ps_bars")
            st.number_input("Consecutive Up Days", value=cfg.consecutive_up_days, key="ps_up_days")
            st.number_input("Target SMA Period", value=cfg.target_sma_period, key="ps_sma")
        with col2:
            st.checkbox("VWAP Entry", value=cfg.vwap_entry, key="ps_vwap")
            st.checkbox("Stop at HOD", value=cfg.stop_at_hod, key="ps_stop")
            st.number_input("Risk Per Trade", value=cfg.risk_per_trade, format="%.4f", key="ps_risk")
    else:
        st.warning("Qullamaggie module not available.")

# ── Tab 3 — Backtest ──────────────────────────────────────────────────
with tab3:
    st.subheader("Synthetic Parabolic Backtest")
    # Simulate parabolic surge then exhaustion
    base_phase = 10.0 + np.random.normal(0, 0.2, 20)
    surge = np.linspace(10, 25, 15) + np.random.normal(0, 0.3, 15)
    exhaustion = np.linspace(25, 18, 10) + np.random.normal(0, 0.5, 10)
    synthetic = np.concatenate([base_phase, surge, exhaustion])
    dates = pd.date_range("2025-07-01", periods=len(synthetic), freq="B")
    df = pd.DataFrame({"Date": dates, "Close": synthetic})
    st.line_chart(df.set_index("Date")["Close"])
    st.caption("Synthetic: base (20 bars) \u2192 parabolic surge (15 bars) \u2192 exhaustion/reversal (10 bars)")

    if STRATEGY_AVAILABLE:
        strategy = ParabolicShortStrategy()
        highs = (synthetic + np.random.uniform(0.2, 0.8, len(synthetic))).tolist()
        lows = (synthetic - np.random.uniform(0.2, 0.8, len(synthetic))).tolist()
        opens = synthetic.tolist()
        volumes = np.random.randint(500000, 2000000, len(synthetic)).tolist()
        signal = strategy.analyze("PARA_SYNTH", opens, highs, lows, synthetic.tolist(), volumes)
        if signal:
            st.success(f"Signal: {signal.direction} at ${signal.entry_price:.2f}, stop ${signal.stop_loss:.2f}")
        else:
            st.info("No signal on synthetic data (parameters may need adjustment)")

# ── Tab 4 — Performance ───────────────────────────────────────────────
with tab4:
    st.subheader("Parabolic Short Performance")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", "40-50%")
    col2.metric("Avg Winner", "10-20%")
    col3.metric("Avg Loser", "-8-15%")
    col4.metric("Profit Factor", "1.5-2.5x")

    st.markdown("""
**Parabolic Short characteristics**:
- Higher win rate than long setups (gravity on your side)
- Smaller R-multiples (targets are closer than breakout targets)
- Requires strict discipline \u2014 never average into a losing short
- Size positions smaller than long setups (unlimited theoretical loss)
- Best after 3-5 consecutive green days with accelerating volume
""")
    trades = np.random.choice([-2, -1, 1, 2, 3], size=40, p=[0.15, 0.35, 0.10, 0.25, 0.15])
    equity = np.cumsum(trades) + 100
    eq_df = pd.DataFrame({"Trade #": range(1, 41), "Equity": equity})
    st.line_chart(eq_df.set_index("Trade #"))
    st.caption("Simulated equity curve: higher win rate, modest winners")
