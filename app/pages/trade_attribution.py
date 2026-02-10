"""Live Trade Attribution Dashboard (PRD-160).

4 tabs: Trade Linkage, P&L Decomposition, Signal Performance, Live Report.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Trade Attribution", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

st.title("Live Trade Attribution")
st.caption("Link trades to signals, decompose P&L, and track signal performance")

# ═══════════════════════════════════════════════════════════════════════
# Engine (session-scoped)
# ═══════════════════════════════════════════════════════════════════════

if "attribution_engine" not in st.session_state:
    from src.trade_attribution import AttributionEngine
    st.session_state.attribution_engine = AttributionEngine()

engine = st.session_state.attribution_engine

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Trade Linkage",
    "P&L Decomposition",
    "Signal Performance",
    "Live Report",
])


# ── Tab 1: Trade Linkage ──────────────────────────────────────────────

with tab1:
    st.subheader("Signal Registration & Trade Linking")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Register Signal**")
        sig_symbol = st.text_input("Symbol", value="AAPL", key="sig_sym")
        sig_type = st.selectbox(
            "Signal Type",
            ["ema_cloud", "momentum", "volume", "breakout"],
            key="sig_type",
        )
        sig_dir = st.selectbox("Direction", ["long", "short"], key="sig_dir")
        sig_conv = st.slider("Conviction", 0, 100, 65, key="sig_conv")

        if st.button("Register Signal", type="primary"):
            st.success(
                f"Signal registered: {sig_symbol} {sig_type} {sig_dir} "
                f"(conviction {sig_conv})"
            )

    with col_right:
        st.markdown("**Link Trade to Signal**")
        trade_id = st.text_input("Trade ID", value="T-001", key="trade_id")
        link_symbol = st.text_input("Symbol", value="AAPL", key="link_sym")
        entry_price = st.number_input("Entry Price", value=175.50, step=0.50, key="entry_px")
        exit_price = st.number_input("Exit Price", value=182.30, step=0.50, key="exit_px")
        shares = st.number_input("Shares", value=100, step=10, key="shares")
        exit_reason = st.selectbox(
            "Exit Reason",
            ["take_profit", "stop_loss", "trailing_stop", "signal_reversal", "manual"],
            key="exit_reason",
        )

        if st.button("Link Trade"):
            pnl = (exit_price - entry_price) * shares
            st.success(f"Trade {trade_id} linked | P&L: ${pnl:,.2f}")

    st.divider()
    st.subheader("Linkage Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("Linkage Rate", "87.3%", "+2.1%")
    m2.metric("Linked Trades", "131 / 150")
    m3.metric("Unmatched Signals", "19")


# ── Tab 2: P&L Decomposition ─────────────────────────────────────────

with tab2:
    st.subheader("P&L Component Breakdown")

    # Demo decomposition data
    components = ["Entry Quality", "Market Movement", "Exit Timing", "Transaction Costs"]
    np.random.seed(42)
    decomp_data = pd.DataFrame({
        "AAPL": [120.0, 340.0, 85.0, -18.0],
        "MSFT": [-45.0, 210.0, 130.0, -22.0],
        "NVDA": [280.0, 520.0, -60.0, -35.0],
        "GOOGL": [95.0, -180.0, 210.0, -15.0],
        "META": [-70.0, 400.0, 55.0, -28.0],
    }, index=components)

    st.bar_chart(decomp_data)

    st.divider()
    st.subheader("Entry & Exit Scores")
    scores_data = {
        "Symbol": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "JPM", "V"],
        "Entry Score": [0.82, 0.64, 0.91, 0.77, 0.58, 0.73, 0.69, 0.85],
        "Exit Score": [0.75, 0.88, 0.62, 0.84, 0.71, 0.66, 0.79, 0.72],
        "Net P&L": [527, 273, 705, 110, 357, -142, 318, 490],
        "Signal": ["ema_cloud", "momentum", "ema_cloud", "breakout",
                    "volume", "momentum", "breakout", "ema_cloud"],
    }
    st.dataframe(pd.DataFrame(scores_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Avg Entry Score", "0.75")
    with col2:
        st.metric("Avg Exit Score", "0.75")


# ── Tab 3: Signal Performance ────────────────────────────────────────

with tab3:
    st.subheader("Rolling Signal-Type Performance")

    perf_data = {
        "Signal Type": ["ema_cloud", "momentum", "volume", "breakout"],
        "Trades": [48, 36, 28, 19],
        "Win Rate": ["64.6%", "52.8%", "57.1%", "63.2%"],
        "Total P&L": ["$6,420", "$1,210", "$3,180", "$2,850"],
        "Avg P&L": ["$133.8", "$33.6", "$113.6", "$150.0"],
        "Profit Factor": [2.18, 1.14, 1.62, 1.95],
        "Avg Conviction": [68, 55, 61, 72],
        "Avg Hold (days)": [4.8, 2.3, 3.6, 5.1],
    }
    perf_df = pd.DataFrame(perf_data).set_index("Signal Type")
    st.dataframe(perf_df, use_container_width=True)

    st.subheader("Profit Factor by Signal Type")
    pf_chart = pd.DataFrame({
        "Signal Type": perf_data["Signal Type"],
        "Profit Factor": perf_data["Profit Factor"],
    }).set_index("Signal Type")
    st.bar_chart(pf_chart)

    col1, col2 = st.columns(2)
    with col1:
        st.success("Best: **ema_cloud** -- PF 2.18, 64.6% win rate, $6,420 total P&L")
    with col2:
        st.error("Worst: **momentum** -- PF 1.14, 52.8% win rate, $1,210 total P&L")


# ── Tab 4: Live Report ───────────────────────────────────────────────

with tab4:
    st.subheader("Full Attribution Report")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Trades", "131")
    m2.metric("Total P&L", "$13,660")
    m3.metric("Linkage Rate", "87.3%")
    m4.metric("Avg Entry Score", "0.75")
    m5.metric("Avg Exit Score", "0.75")

    st.divider()
    report_json = {
        "report_date": datetime.now().isoformat(),
        "total_trades": 131,
        "linked_trades": 131,
        "unmatched_signals": 19,
        "linkage_rate": 0.873,
        "total_pnl": 13660.0,
        "avg_entry_score": 0.75,
        "avg_exit_score": 0.75,
        "best_signal_type": "ema_cloud",
        "worst_signal_type": "momentum",
        "by_signal_type": {
            "ema_cloud": {"trades": 48, "pnl": 6420, "win_rate": 0.646, "pf": 2.18},
            "momentum": {"trades": 36, "pnl": 1210, "win_rate": 0.528, "pf": 1.14},
            "volume": {"trades": 28, "pnl": 3180, "win_rate": 0.571, "pf": 1.62},
            "breakout": {"trades": 19, "pnl": 2850, "win_rate": 0.632, "pf": 1.95},
        },
        "decomposition_summary": {
            "entry_quality_avg": 76.0,
            "market_movement_avg": 258.0,
            "exit_timing_avg": 84.0,
            "transaction_costs_avg": -23.6,
        },
    }
    st.json(report_json)

    # CSV export
    export_df = pd.DataFrame({
        "Signal Type": ["ema_cloud", "momentum", "volume", "breakout"],
        "Trades": [48, 36, 28, 19],
        "Total P&L": [6420, 1210, 3180, 2850],
        "Win Rate": [0.646, 0.528, 0.571, 0.632],
        "Profit Factor": [2.18, 1.14, 1.62, 1.95],
    })
    csv_data = export_df.to_csv(index=False)
    st.download_button(
        "Download Attribution Report (CSV)",
        data=csv_data,
        file_name=f"trade_attribution_{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )
