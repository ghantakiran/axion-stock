"""Trade Executor Dashboard (PRD-135).

Autonomous trade execution engine control center.
4 tabs: Active Positions, Order Book, Risk Dashboard, Trade Journal.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Trade Executor", layout="wide")
except Exception:
    import streamlit as st

import json
from datetime import date, datetime, timedelta, timezone

st.title("Trade Executor")
st.caption("Autonomous trade execution engine — validate, size, route, monitor, exit")

# ── Sidebar Controls ────────────────────────────────────────────

with st.sidebar:
    st.subheader("Executor Settings")
    instrument_mode = st.selectbox(
        "Instrument Mode",
        ["Both", "Options Only", "Leveraged ETF Only"],
        help="Choose how signals are routed to instruments",
    )
    paper_mode = st.toggle("Paper Mode", value=True)
    primary_broker = st.selectbox("Primary Broker", ["Alpaca", "IBKR"])
    max_risk = st.slider("Max Risk/Trade (%)", 1, 10, 5) / 100
    max_positions = st.slider("Max Positions", 1, 20, 10)
    daily_loss_limit = st.slider("Daily Loss Limit (%)", 1, 20, 10) / 100

    st.divider()
    kill_switch = st.toggle("Kill Switch", value=False, help="Emergency halt all trading")
    if kill_switch:
        st.error("KILL SWITCH ACTIVE — All trading halted")

# ── Tabs ────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "Active Positions",
    "Order Book",
    "Risk Dashboard",
    "Trade Journal",
])

# ── Tab 1: Active Positions ────────────────────────────────────

with tab1:
    st.subheader("Open Positions")

    # Demo data
    demo_positions = [
        {
            "Ticker": "TQQQ", "Direction": "Long", "Type": "Leveraged ETF",
            "Entry": "$48.50", "Current": "$49.20", "Shares": 200,
            "P&L": "+$140.00", "P&L %": "+1.44%", "Stop": "$47.00",
            "Trade Type": "Day", "Leverage": "3x",
        },
        {
            "Ticker": "AAPL", "Direction": "Long", "Type": "Stock",
            "Entry": "$178.50", "Current": "$180.20", "Shares": 50,
            "P&L": "+$85.00", "P&L %": "+0.95%", "Stop": "$175.00",
            "Trade Type": "Swing", "Leverage": "1x",
        },
    ]

    if demo_positions:
        st.dataframe(demo_positions, use_container_width=True)
    else:
        st.info("No open positions")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Open Positions", "2 / 10")
    with col2:
        st.metric("Total Exposure", "$18,710", "+2.1%")
    with col3:
        st.metric("Unrealized P&L", "+$225.00", "+1.2%")

    st.divider()
    st.subheader("Exit Monitoring")
    exit_checks = {
        "Stop Loss": "Monitoring",
        "Momentum Exhaustion": "Clear",
        "Cloud Flip": "Clear",
        "Profit Target": "TQQQ approaching target",
        "Time Stop": "TQQQ: 45m remaining",
        "EOD Close": "2h 5m to close",
        "Trailing Stop": "Active for AAPL (swing)",
    }
    for check_name, status in exit_checks.items():
        icon = "🟢" if status == "Clear" or status == "Monitoring" else "🟡"
        st.text(f"{icon} {check_name}: {status}")


# ── Tab 2: Order Book ──────────────────────────────────────────

with tab2:
    st.subheader("Recent Orders")

    demo_orders = [
        {
            "Time": "10:15:32", "Ticker": "TQQQ", "Side": "Buy",
            "Qty": 200, "Type": "Market", "Status": "Filled",
            "Price": "$48.50", "Broker": "Paper",
        },
        {
            "Time": "09:45:10", "Ticker": "AAPL", "Side": "Buy",
            "Qty": 50, "Type": "Limit", "Status": "Filled",
            "Price": "$178.50", "Broker": "Paper",
        },
        {
            "Time": "09:32:05", "Ticker": "SOXL", "Side": "Buy",
            "Qty": 100, "Type": "Market", "Status": "Rejected",
            "Price": "—", "Broker": "Paper",
        },
    ]

    st.dataframe(demo_orders, use_container_width=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Orders Today", "3")
    with col2:
        st.metric("Filled", "2")
    with col3:
        st.metric("Rejected", "1")
    with col4:
        st.metric("Avg Fill Time", "< 1s")

    st.divider()
    st.subheader("Instrument Routing")

    mode_label = instrument_mode
    st.info(f"Mode: **{mode_label}** — Scalp→Options | Day→ETFs | Swing→Stocks")

    etf_catalog = {
        "NASDAQ-100": {"Bull": "TQQQ (3x)", "Bear": "SQQQ (3x)"},
        "S&P 500": {"Bull": "SPXL (3x)", "Bear": "SPXS (3x)"},
        "Semiconductors": {"Bull": "SOXL (3x)", "Bear": "SOXS (3x)"},
        "Technology": {"Bull": "TECL (3x)", "Bear": "TECS (3x)"},
        "Financials": {"Bull": "FAS (3x)", "Bear": "FAZ (3x)"},
    }
    st.dataframe(
        [{"Sector": k, **v} for k, v in etf_catalog.items()],
        use_container_width=True,
    )


# ── Tab 3: Risk Dashboard ─────────────────────────────────────

with tab3:
    st.subheader("Risk Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Daily P&L", "+$225.00", "+0.23%")
    with col2:
        st.metric("Daily Loss Limit", f"{daily_loss_limit:.0%}", "OK")
    with col3:
        st.metric("Account Equity", "$100,225")
    with col4:
        st.metric("Buying Power", "$81,290")

    st.divider()
    st.subheader("Risk Gate Checks")

    risk_checks = {
        "Daily P&L Limit": ("PASS", "green"),
        "Max Positions (2/10)": ("PASS", "green"),
        "Duplicate Ticker": ("PASS", "green"),
        "Conflicting Signals": ("PASS", "green"),
        "Sector Exposure": ("PASS", "green"),
        "Market Hours": ("PASS", "green"),
        "Min Equity (PDT)": ("PASS", "green"),
        "Buying Power": ("PASS", "green"),
    }

    for check, (status, _) in risk_checks.items():
        icon = "✅" if status == "PASS" else "❌"
        st.text(f"{icon} {check}")

    st.divider()
    st.subheader("Kill Switch Status")

    if kill_switch:
        st.error("KILL SWITCH IS ACTIVE — All new trades blocked")
        st.text(f"Reason: Manual activation via dashboard")
    else:
        st.success("Kill switch inactive — trading enabled")
        st.text("Triggers: Daily loss >10% | Equity <$25K | 3 consecutive losses >3%")


# ── Tab 4: Trade Journal ──────────────────────────────────────

with tab4:
    st.subheader("Today's Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", "5")
    with col2:
        st.metric("Win Rate", "60%")
    with col3:
        st.metric("Net P&L", "+$342.50")
    with col4:
        st.metric("Avg Hold Time", "47 min")

    st.divider()
    st.subheader("Trade History")

    demo_trades = [
        {
            "Time": "14:20", "Ticker": "SOXL", "Direction": "Long",
            "Entry": "$32.10", "Exit": "$33.45", "Shares": 150,
            "P&L": "+$202.50", "Exit Reason": "Target",
            "Conviction": 85, "Type": "Day",
        },
        {
            "Time": "11:45", "Ticker": "TQQQ", "Direction": "Long",
            "Entry": "$47.80", "Exit": "$48.20", "Shares": 200,
            "P&L": "+$80.00", "Exit Reason": "Exhaustion",
            "Conviction": 72, "Type": "Scalp",
        },
        {
            "Time": "10:30", "Ticker": "SPXS", "Direction": "Short",
            "Entry": "$15.20", "Exit": "$15.50", "Shares": 300,
            "P&L": "-$90.00", "Exit Reason": "Stop Loss",
            "Conviction": 65, "Type": "Day",
        },
    ]

    st.dataframe(demo_trades, use_container_width=True)

    st.divider()
    st.subheader("Performance by Exit Reason")

    exit_stats = [
        {"Exit Reason": "Target", "Count": 2, "Win Rate": "100%", "Avg P&L": "+$141.25"},
        {"Exit Reason": "Exhaustion", "Count": 1, "Win Rate": "100%", "Avg P&L": "+$80.00"},
        {"Exit Reason": "Stop Loss", "Count": 1, "Win Rate": "0%", "Avg P&L": "-$90.00"},
        {"Exit Reason": "Cloud Flip", "Count": 1, "Win Rate": "100%", "Avg P&L": "+$60.00"},
    ]
    st.dataframe(exit_stats, use_container_width=True)
