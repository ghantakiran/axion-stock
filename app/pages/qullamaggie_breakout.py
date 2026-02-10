"""Qullamaggie Breakout Strategy Dashboard.

4 tabs: Overview, Configuration, Backtest, Performance.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Qullamaggie Breakout", page_icon="\U0001f4c8", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4c8 Qullamaggie Breakout Strategy")
st.caption("Flag/consolidation breakout after a prior move \u2014 Kristjan Kullamagi's core setup")

import numpy as np, pandas as pd

try:
    from src.qullamaggie.breakout_strategy import QullamaggieBreakoutStrategy
    from src.qullamaggie.config import BreakoutConfig
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False

np.random.seed(200)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Configuration", "Backtest", "Performance"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Breakout Methodology")
    st.markdown("""
**Core idea**: A stock makes a large move (30%+ in 1-3 months), then consolidates
in a tight flag pattern with contracting volume. When it breaks out of the
consolidation on high volume, enter long.

**3-Step Entry Logic**:
1. **Prior Move** \u2014 Stock has gained \u226530% in the past 1-3 months, establishing
   momentum leadership.
2. **Consolidation** \u2014 2-8 weeks of tight, orderly price action with higher lows,
   volume contraction (<0.7x average), and price surfing the 10/20 SMA.
3. **Breakout** \u2014 Price closes above the consolidation high with volume \u22651.5x
   the 20-day average.

**Risk Management**:
- **Stop loss** at the low of the breakout day, capped at 1x ATR from entry
- **Trail** with the 10 or 20 SMA (whichever holds as support)
- **Risk per trade**: 0.3-0.5% of equity
""")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Best for: Trending markets, growth/momentum stocks, mid/small caps")
    with col2:
        st.warning("Avoid during: Broad market corrections, bear regimes, low-ADR names")

# ── Tab 2 — Configuration ─────────────────────────────────────────────
with tab2:
    st.subheader("Strategy Configuration")
    if STRATEGY_AVAILABLE:
        cfg = BreakoutConfig()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("Prior Gain %", value=cfg.prior_gain_pct, key="bo_prior_gain")
            st.number_input("Consolidation Min Bars", value=cfg.consolidation_min_bars, key="bo_cons_min")
            st.number_input("Consolidation Max Bars", value=cfg.consolidation_max_bars, key="bo_cons_max")
            st.number_input("Max Pullback %", value=cfg.pullback_max_pct, key="bo_pullback")
        with col2:
            st.number_input("Volume Contraction Ratio", value=cfg.volume_contraction_ratio, key="bo_vol_ratio")
            st.number_input("Breakout Volume Mult", value=cfg.breakout_volume_mult, key="bo_vol_mult")
            st.number_input("ADR Min %", value=cfg.adr_min_pct, key="bo_adr")
            st.number_input("Stop ATR Mult", value=cfg.stop_atr_mult, key="bo_stop_atr")
        with col3:
            st.number_input("Risk Per Trade", value=cfg.risk_per_trade, format="%.4f", key="bo_risk")
            st.number_input("Max Position %", value=cfg.max_position_pct, key="bo_max_pos")
            st.number_input("Min Price ($)", value=cfg.price_min, key="bo_min_price")
            st.number_input("Min Avg Volume", value=cfg.avg_volume_min, key="bo_min_vol")
    else:
        st.warning("Qullamaggie module not available. Install dependencies.")

# ── Tab 3 — Backtest ──────────────────────────────────────────────────
with tab3:
    st.subheader("Synthetic Backtest")
    n_bars = 120
    base = 50.0
    # Simulate prior move + consolidation + breakout
    prior_move = np.linspace(base, base * 1.5, 40) + np.random.normal(0, 0.5, 40)
    consolidation = prior_move[-1] + np.random.normal(0, 1.0, 50)
    breakout = np.linspace(consolidation[-1], consolidation[-1] * 1.15, 30) + np.random.normal(0, 0.5, 30)
    synthetic_closes = np.concatenate([prior_move, consolidation, breakout])
    dates = pd.date_range("2025-06-01", periods=len(synthetic_closes), freq="B")
    df = pd.DataFrame({"Date": dates, "Close": synthetic_closes})
    st.line_chart(df.set_index("Date")["Close"])
    st.caption("Synthetic: prior move (40 bars) \u2192 consolidation (50 bars) \u2192 breakout (30 bars)")

    if STRATEGY_AVAILABLE:
        strategy = QullamaggieBreakoutStrategy()
        highs = (synthetic_closes + np.random.uniform(0.5, 1.5, len(synthetic_closes))).tolist()
        lows = (synthetic_closes - np.random.uniform(0.5, 1.5, len(synthetic_closes))).tolist()
        opens = (synthetic_closes + np.random.uniform(-0.5, 0.5, len(synthetic_closes))).tolist()
        volumes = np.random.randint(300000, 800000, len(synthetic_closes)).tolist()
        volumes[-1] = int(np.mean(volumes) * 2)  # Breakout volume spike
        signal = strategy.analyze("SYNTH", opens, highs, lows, synthetic_closes.tolist(), volumes)
        if signal:
            st.success(f"Signal: {signal.direction} at ${signal.entry_price:.2f}, stop ${signal.stop_loss:.2f}, conviction {signal.conviction}")
        else:
            st.info("No signal on synthetic data (adjust parameters for demonstration)")

# ── Tab 4 — Performance ───────────────────────────────────────────────
with tab4:
    st.subheader("Historical Performance Characteristics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", "25-35%")
    col2.metric("Avg Winner", "15-30%")
    col3.metric("Avg Loser", "-5-7%")
    col4.metric("Profit Factor", "2.5-4.0x")

    st.markdown("""
**Key characteristics** (from Qullamaggie's documented results):
- Low win rate (~25-35%) compensated by large winners (big R multiples)
- Most of the annual P&L comes from a few monster trades (5-10 per year)
- Requires discipline to cut losses quickly and let winners run
- Best performance in bull/trending markets; drawdowns in choppy markets
""")
    # Equity curve simulation
    trades = np.random.choice([-1, -1, -1, 3, 5, 8], size=50, p=[0.35, 0.20, 0.15, 0.15, 0.10, 0.05])
    equity = np.cumsum(trades) + 100
    eq_df = pd.DataFrame({"Trade #": range(1, 51), "Equity": equity})
    st.line_chart(eq_df.set_index("Trade #"))
    st.caption("Simulated equity curve: low win rate, high payoff ratio")
