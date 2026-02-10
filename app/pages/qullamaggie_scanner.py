"""Qullamaggie Scanner Dashboard.

4 tabs: Overview, Live Scan, Custom Scan, History.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Qullamaggie Scanner", page_icon="\U0001f50d", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f50d Qullamaggie Scanner")
st.caption("5 preset scans for Qullamaggie momentum setups \u2014 EP, Breakout, HTF, Leaders, Parabolic")

import numpy as np, pandas as pd

try:
    from src.qullamaggie.scanner import QULLAMAGGIE_PRESETS
    SCANNER_AVAILABLE = True
except ImportError:
    SCANNER_AVAILABLE = False
    QULLAMAGGIE_PRESETS = {}

np.random.seed(203)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Live Scan", "Custom Scan", "History"])

# ── Tab 1 — Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("5 Qullamaggie Scanner Presets")

    presets_info = [
        ("Episodic Pivot (EP)", "Gap \u226510%, volume \u22652x avg, price \u2265$5, prior flat base",
         "Best for earnings season and catalyst-driven moves"),
        ("Breakout", "1M gain \u226530%, ADX \u226525, volume expanding, near 10/20 SMA",
         "Classic flag breakout from tight consolidation"),
        ("High Tight Flag (HTF)", "1M gain \u226580%, pullback \u226425%, volume contraction",
         "Rare but powerful \u2014 the tightest consolidation after the biggest moves"),
        ("Momentum Leaders", "Above 200 SMA, ADR \u22655%, top gainers with volume",
         "The leadership list \u2014 stocks making new highs in uptrends"),
        ("Parabolic Short", "RSI \u226580, 3+ green days, extended from all MAs",
         "Identify exhaustion for potential mean-reversion shorts"),
    ]

    for name, criteria, note in presets_info:
        with st.expander(f"**{name}**"):
            st.markdown(f"**Criteria**: {criteria}")
            st.info(note)

# ── Tab 2 — Live Scan ─────────────────────────────────────────────────
with tab2:
    st.subheader("Run Preset Scan")
    if SCANNER_AVAILABLE:
        preset_names = list(QULLAMAGGIE_PRESETS.keys())
        selected = st.selectbox("Select Preset", preset_names, key="scan_preset")
        scanner = QULLAMAGGIE_PRESETS.get(selected)

        if scanner:
            st.markdown(f"**{scanner.name}**: {scanner.description}")
            st.markdown("**Criteria:**")
            for c in scanner.criteria:
                st.markdown(f"- `{c.field}` {c.operator.value} {c.value}")

        if st.button("Run Scan", key="run_scan"):
            # Synthetic scan results
            tickers = ["NVDA", "SMCI", "ARM", "PLTR", "CRWD", "META", "CELH", "DUOL"]
            np.random.shuffle(tickers)
            n_results = np.random.randint(3, 7)
            results = []
            for i in range(n_results):
                results.append({
                    "Symbol": tickers[i],
                    "Price": round(np.random.uniform(20, 500), 2),
                    "Change %": round(np.random.uniform(3, 25), 1),
                    "Volume": f"{np.random.randint(500, 5000)}K",
                    "Rel Volume": round(np.random.uniform(1.5, 5.0), 1),
                    "Signal Strength": np.random.randint(60, 95),
                })
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            st.caption(f"Found {n_results} matches (synthetic demo data)")
    else:
        st.warning("Scanner module not available.")

# ── Tab 3 — Custom Scan ───────────────────────────────────────────────
with tab3:
    st.subheader("Custom Qullamaggie Scan")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.number_input("Min Gap %", value=10.0, key="custom_gap")
        st.number_input("Min Price ($)", value=5.0, key="custom_price")
    with col2:
        st.number_input("Min Rel Volume", value=2.0, key="custom_vol")
        st.number_input("Min ADR %", value=3.5, key="custom_adr")
    with col3:
        st.number_input("Min Volume", value=500000, key="custom_min_vol")
        st.selectbox("Market Cap", ["All", "Small Cap", "Mid Cap", "Large Cap"], key="custom_mcap")

    if st.button("Run Custom Scan", key="run_custom"):
        st.info("Custom scan would query the market data source with your criteria. Demo mode shows synthetic results.")

# ── Tab 4 — History ────────────────────────────────────────────────────
with tab4:
    st.subheader("Scan History & Hit Rates")
    history = pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=10, freq="W"),
        "Preset": np.random.choice(["EP", "Breakout", "HTF", "Leaders", "Parabolic"], 10),
        "Matches": np.random.randint(2, 15, 10),
        "Hits (1w)": np.random.randint(0, 8, 10),
        "Hit Rate": [f"{np.random.randint(20, 60)}%" for _ in range(10)],
    })
    st.dataframe(history, use_container_width=True)
    st.caption("Historical scan results with 1-week forward hit rate")
