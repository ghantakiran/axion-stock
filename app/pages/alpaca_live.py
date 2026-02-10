"""Alpaca Live Broker Dashboard (PRD-139).

4 tabs: Connection, Positions, Orders, Market Data.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Alpaca Live", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

st.title("Alpaca Live Broker")
st.caption("Real-time connection to Alpaca Trading API")

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Connection",
    "Positions",
    "Orders",
    "Market Data",
])


# ── Tab 1: Connection ─────────────────────────────────────────────────

with tab1:
    st.subheader("API Connection")

    col1, col2 = st.columns(2)
    with col1:
        env = st.selectbox("Environment", ["Paper Trading", "Live Trading"])
        api_key = st.text_input("API Key", type="password", value="")
        api_secret = st.text_input("API Secret", type="password", value="")

    with col2:
        data_feed = st.selectbox("Data Feed", ["IEX (Free)", "SIP (Paid)"])
        st.write("")
        st.write("")
        if st.button("Connect", type="primary", use_container_width=True):
            st.success("Connected to Alpaca Paper Trading (Demo Mode)")

    st.divider()
    st.subheader("Connection Status")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Connected")
    m2.metric("Mode", "Demo")
    m3.metric("Environment", "Paper")
    m4.metric("Uptime", "2h 34m")

    st.subheader("Account Summary")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Equity", "$87,400", "+$500")
    m2.metric("Cash", "$50,000")
    m3.metric("Buying Power", "$90,000")
    m4.metric("Positions", "2")
    m5.metric("Day P&L", "+$250", "+0.29%")
    m6.metric("PDT Status", "OK")


# ── Tab 2: Positions ──────────────────────────────────────────────────

with tab2:
    st.subheader("Open Positions")

    positions_data = {
        "Symbol": ["AAPL", "MSFT"],
        "Qty": [100, 50],
        "Avg Entry": ["$150.00", "$350.00"],
        "Current": ["$185.00", "$378.00"],
        "Market Value": ["$18,500", "$18,900"],
        "Cost Basis": ["$15,000", "$17,500"],
        "Unrealized P&L": ["+$3,500", "+$1,400"],
        "P&L %": ["+23.3%", "+8.0%"],
        "Today": ["+$120", "+$85"],
        "Side": ["Long", "Long"],
    }
    st.dataframe(pd.DataFrame(positions_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Portfolio Allocation")
        alloc_df = pd.DataFrame({
            "Symbol": ["AAPL", "MSFT", "Cash"],
            "Value": [18500, 18900, 50000],
        }).set_index("Symbol")
        st.bar_chart(alloc_df)

    with col2:
        st.subheader("P&L by Position")
        pnl_df = pd.DataFrame({
            "Symbol": ["AAPL", "MSFT"],
            "P&L ($)": [3500, 1400],
        }).set_index("Symbol")
        st.bar_chart(pnl_df)

    # Position performance over time
    st.subheader("Position Value Over Time")
    dates = pd.bdate_range(start="2024-01-01", periods=60)
    np.random.seed(42)
    aapl_vals = 15000 * np.cumprod(1 + np.random.normal(0.001, 0.015, 60))
    msft_vals = 17500 * np.cumprod(1 + np.random.normal(0.0008, 0.012, 60))
    perf_df = pd.DataFrame({
        "AAPL": aapl_vals,
        "MSFT": msft_vals,
    }, index=dates)
    st.line_chart(perf_df)


# ── Tab 3: Orders ─────────────────────────────────────────────────────

with tab3:
    st.subheader("Place Order")

    col1, col2, col3 = st.columns(3)
    with col1:
        order_symbol = st.text_input("Symbol", value="AAPL")
        order_side = st.selectbox("Side", ["Buy", "Sell", "Short Sell", "Buy to Cover"])
    with col2:
        order_qty = st.number_input("Quantity", value=10, min_value=1)
        order_type = st.selectbox("Type", ["Market", "Limit", "Stop", "Stop Limit", "Trailing Stop"])
    with col3:
        order_tif = st.selectbox("Time in Force", ["Day", "GTC", "IOC", "FOK"])
        if order_type in ["Limit", "Stop Limit"]:
            limit_price = st.number_input("Limit Price", value=185.0)
        if order_type in ["Stop", "Stop Limit"]:
            stop_price = st.number_input("Stop Price", value=180.0)
        extended = st.checkbox("Extended Hours")

    if st.button("Submit Order", type="primary", use_container_width=True):
        st.success(f"Order submitted: {order_side} {order_qty} {order_symbol} ({order_type})")

    st.divider()
    st.subheader("Order History")

    orders_data = {
        "Order ID": ["abc123", "def456", "ghi789", "jkl012", "mno345"],
        "Symbol": ["AAPL", "MSFT", "AAPL", "NVDA", "GOOGL"],
        "Side": ["Buy", "Buy", "Sell", "Buy", "Buy"],
        "Qty": [10, 25, 10, 15, 20],
        "Type": ["Market", "Limit", "Market", "Market", "Limit"],
        "Status": ["Filled", "Filled", "Filled", "Open", "Canceled"],
        "Fill Price": ["$185.00", "$370.50", "$188.20", "-", "-"],
        "Submitted": ["10:30 AM", "11:15 AM", "2:45 PM", "3:00 PM", "9:31 AM"],
    }
    st.dataframe(pd.DataFrame(orders_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orders Today", "5")
        st.metric("Filled", "3")
    with col2:
        st.metric("Open", "1")
        st.metric("Canceled", "1")


# ── Tab 4: Market Data ───────────────────────────────────────────────

with tab4:
    st.subheader("Market Data")

    col1, col2 = st.columns([1, 3])
    with col1:
        md_symbol = st.text_input("Symbol", value="AAPL", key="md_symbol")
        md_timeframe = st.selectbox("Timeframe", ["1Min", "5Min", "15Min", "1Hour", "1Day"])
        md_days = st.slider("Lookback Days", 5, 252, 60)

    with col2:
        st.subheader(f"{md_symbol} Snapshot")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Last", "$185.00", "+$1.20")
        m2.metric("Bid", "$184.50")
        m3.metric("Ask", "$185.00")
        m4.metric("Volume", "52.3M")
        m5.metric("VWAP", "$184.85")

    # OHLCV chart
    st.subheader(f"{md_symbol} Price History ({md_timeframe})")
    np.random.seed(hash(md_symbol) % 2**31)
    n_bars = min(md_days * 7 if md_timeframe == "1Min" else md_days, 200)
    base = 185.0
    closes = [base]
    for _ in range(n_bars - 1):
        closes.append(closes[-1] * (1 + np.random.normal(0.0003, 0.012)))
    chart_df = pd.DataFrame({"Close": closes})
    st.line_chart(chart_df)

    # Volume
    st.subheader("Volume")
    vol_data = np.random.randint(20_000_000, 80_000_000, n_bars)
    vol_df = pd.DataFrame({"Volume": vol_data})
    st.bar_chart(vol_df)

    # Market status
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Market Status", "Open")
    with col2:
        st.metric("Next Close", "4:00 PM ET")
    with col3:
        st.metric("Data Feed", "IEX")
