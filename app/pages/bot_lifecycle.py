"""Bot Lifecycle Dashboard — PRD-171.

4-tab dashboard for monitoring bot lifecycle hardening:
1. Signal Guard Stats — freshness/dedup rejection rates
2. Position Lifecycle — live prices, unrealized P&L, exit status
3. Exit Monitor — exit signals, exit types, exit frequency
4. Emergency Controls — kill switch, emergency close, daily limit status
"""

import streamlit as st
from datetime import datetime, timezone

st.set_page_config(page_title="Bot Lifecycle", page_icon=":material/cycle:", layout="wide")
st.title("Bot Lifecycle Hardening")
st.caption("PRD-171 — Signal guard, position lifecycle, exit monitoring & emergency controls")

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Guard Stats",
    "Position Lifecycle",
    "Exit Monitor",
    "Emergency Controls",
])

# ── Tab 1: Signal Guard Stats ────────────────────────────────────
with tab1:
    st.subheader("Signal Freshness & Deduplication")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Max Signal Age", "120s", help="Signals older than this are rejected")
    with col2:
        st.metric("Dedup Window", "300s", help="Same signal within this window is rejected")
    with col3:
        st.metric("Active Dedup Entries", "0")
    with col4:
        st.metric("Guard Rejections", "0")

    st.divider()

    st.subheader("Rejection Log")
    st.info("Connect to a running BotOrchestrator to see live signal guard statistics.")

    with st.expander("Configuration"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.number_input("Max Signal Age (seconds)", value=120.0, min_value=10.0, step=10.0)
        with col_b:
            st.number_input("Dedup Window (seconds)", value=300.0, min_value=30.0, step=30.0)

# ── Tab 2: Position Lifecycle ────────────────────────────────────
with tab2:
    st.subheader("Open Positions")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open Positions", "0")
    with col2:
        st.metric("Total Unrealized P&L", "$0.00")
    with col3:
        st.metric("Total Exposure", "$0.00")
    with col4:
        st.metric("Daily Realized P&L", "$0.00")

    st.divider()

    st.subheader("Position Details")
    st.info(
        "Connect to a running LifecycleManager to see real-time position "
        "data with live price updates."
    )

    st.subheader("Price Update Status")
    st.caption("Prices are updated via LifecycleManager.update_prices() on each tick")

# ── Tab 3: Exit Monitor ──────────────────────────────────────────
with tab3:
    st.subheader("Exit Monitor Status")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stop Losses Hit", "0")
    with col2:
        st.metric("Targets Hit", "0")
    with col3:
        st.metric("Time Stops", "0")
    with col4:
        st.metric("Emergency Closes", "0")

    st.divider()

    st.subheader("Exit Strategies")
    exit_types = [
        ("Stop Loss", "Price closes beyond stop level", 1),
        ("Momentum Exhaustion", "3+ candles outside fast cloud", 2),
        ("Cloud Flip", "Fast cloud (5/12) flips against direction", 3),
        ("Profit Target", "2:1 reward-to-risk reached", 4),
        ("Time Stop", "Position held too long with no progress", 5),
        ("EOD Close", "Day trades closed by 3:55 PM ET", 6),
        ("Trailing Stop", "Price breaks below pullback cloud (8/9)", 7),
    ]
    for name, desc, priority in exit_types:
        st.markdown(f"**{priority}. {name}** — {desc}")

    st.info("Exit monitor runs via LifecycleManager.check_exits() on each price update cycle.")

# ── Tab 4: Emergency Controls ────────────────────────────────────
with tab4:
    st.subheader("Emergency Controls")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Kill Switch", "INACTIVE", delta="Safe")
        st.metric("Circuit Breaker", "Closed")
        st.metric("Daily Loss Limit", "10%", help="Auto-kill triggers at this daily loss level")

    with col2:
        st.metric("Lifetime Realized P&L", "$0.00")
        st.metric("Last Signal", "N/A")
        st.metric("Last Trade", "N/A")

    st.divider()

    st.warning("Emergency actions require a running bot instance.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Emergency Close All", type="primary", use_container_width=True):
            st.error("Not connected to a running bot instance.")
    with col_b:
        if st.button("Activate Kill Switch", use_container_width=True):
            st.error("Not connected to a running bot instance.")
    with col_c:
        if st.button("Reset Kill Switch", use_container_width=True):
            st.error("Not connected to a running bot instance.")

    st.divider()

    st.subheader("Daily Loss Auto-Kill")
    st.caption(
        "When enabled, the kill switch automatically activates if the daily "
        "realized P&L exceeds the configured daily_loss_limit (default: 10% of equity)."
    )

    st.subheader("Instrument Routing")
    routing_modes = {
        "Options": "Scalp signals → options, day/swing → stocks",
        "Leveraged ETF": "All signals → sector-matched leveraged ETFs",
        "Both": "Scalp → options, day → leveraged ETFs, swing → stocks",
    }
    for mode, desc in routing_modes.items():
        st.markdown(f"- **{mode}**: {desc}")
