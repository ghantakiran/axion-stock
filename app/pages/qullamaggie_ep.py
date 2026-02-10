"""Qullamaggie Episodic Pivot Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Qullamaggie EP", page_icon="\U0001f4a5", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4a5 Qullamaggie Episodic Pivot")
st.caption("Earnings gap-up from a flat base \u2014 the highest-conviction catalyst play")

import numpy as np, pandas as pd

try:
    from src.qullamaggie.episodic_pivot_strategy import EpisodicPivotStrategy
    from src.qullamaggie.config import EpisodicPivotConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(201)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Episodic Pivot Methodology")
    st.markdown("""
**Core idea**: A stock that nobody cares about (flat, boring base for months)
suddenly gets a catalyst (earnings beat, FDA approval, major contract) and
gaps up 10%+ on massive volume. This is a paradigm shift \u2014 the market is
repricing the stock, and the move often continues for weeks.

**Entry Criteria**:
1. **Gap-Up** \u2014 Open \u226510% above previous close.
2. **Volume Explosion** \u2014 Volume \u22652x the 20-day average.
3. **Prior Flatness** \u2014 Price range over the prior 60 bars \u226430%.
4. **ADR** \u2014 \u22653.5% (stock is volatile enough to be worth trading).

**Key Rules**:
- Entry above the opening range high (high of the gap day)
- Stop at the low of the gap day
- Trail with 10/20 EMA as the stock trends
- The flatter the prior base, the stronger the EP
""")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Best for: Earnings season, FDA events, contract announcements")
    with col2:
        st.warning("Avoid: Gap-ups into overhead resistance, extended stocks")

# ── Tab 2 — Configuration ─────────────────────────────────────────────
with tab2:
    st.subheader("Strategy Configuration")
    if STRATEGY_AVAILABLE:
        cfg = EpisodicPivotConfig()
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Gap Min %", value=cfg.gap_min_pct, key="ep_gap")
            st.number_input("Volume Mult Min", value=cfg.volume_mult_min, key="ep_vol")
            st.number_input("Prior Flat Bars", value=cfg.prior_flat_bars, key="ep_flat")
            st.number_input("Prior Flat Max Range %", value=cfg.prior_flat_max_range_pct, key="ep_range")
        with col2:
            st.number_input("ADR Min %", value=cfg.adr_min_pct, key="ep_adr")
            st.checkbox("Stop at LOD", value=cfg.stop_at_lod, key="ep_stop_lod")
            st.number_input("Risk Per Trade", value=cfg.risk_per_trade, format="%.4f", key="ep_risk")
            st.checkbox("Earnings Only", value=cfg.earnings_only, key="ep_earn_only")
    else:
        st.warning("Qullamaggie module not available.")

# ── Tab 3 — Backtest ──────────────────────────────────────────────────
with tab3:
    st.subheader("Synthetic EP Backtest")
    # Simulate flat base then gap-up
    flat_base = 30.0 + np.random.normal(0, 0.5, 62)
    gap_day_open = flat_base[-1] * 1.15  # 15% gap
    post_gap = np.linspace(gap_day_open, gap_day_open * 1.20, 20) + np.random.normal(0, 0.3, 20)
    synthetic = np.concatenate([flat_base, [gap_day_open], post_gap])
    dates = pd.date_range("2025-04-01", periods=len(synthetic), freq="B")
    df = pd.DataFrame({"Date": dates, "Close": synthetic})
    st.line_chart(df.set_index("Date")["Close"])
    st.caption("Synthetic: flat base (62 bars) \u2192 gap-up \u2192 trend continuation (20 bars)")

    if STRATEGY_AVAILABLE:
        strategy = EpisodicPivotStrategy()
        highs = (synthetic + np.random.uniform(0.3, 1.0, len(synthetic))).tolist()
        lows = (synthetic - np.random.uniform(0.3, 1.0, len(synthetic))).tolist()
        opens = synthetic.tolist()
        opens[-21] = gap_day_open  # Ensure gap in opens
        volumes = np.random.randint(200000, 500000, len(synthetic)).tolist()
        volumes[-21] = 1500000  # Volume spike on gap day
        signal = strategy.analyze("EP_SYNTH", opens, highs, lows, synthetic.tolist(), volumes)
        if signal:
            st.success(f"Signal: {signal.direction} at ${signal.entry_price:.2f}, gap {signal.metadata.get('gap_pct', 0):.1f}%")
        else:
            st.info("No signal on synthetic data (parameters may need adjustment for demo)")

# ── Tab 4 — Performance ───────────────────────────────────────────────
with tab4:
    st.subheader("EP Performance Characteristics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", "30-40%")
    col2.metric("Avg Winner", "20-50%")
    col3.metric("Avg Loser", "-5-8%")
    col4.metric("Profit Factor", "3.0-5.0x")

    st.markdown("""
**Why EPs work so well**:
- Paradigm shift: institutional money reprices the stock over weeks
- Gap = immediate edge; flat base = no overhead resistance
- Volume explosion confirms institutional participation
- The flatter the prior base, the fewer sellers to absorb
- Often the best trades of the year come from EPs
""")
    trades = np.random.choice([-1, -1, -1, 4, 7, 12], size=40, p=[0.30, 0.18, 0.12, 0.20, 0.12, 0.08])
    equity = np.cumsum(trades) + 100
    eq_df = pd.DataFrame({"Trade #": range(1, 41), "Equity": equity})
    st.line_chart(eq_df.set_index("Trade #"))
    st.caption("Simulated EP equity curve: few trades, large winners")
