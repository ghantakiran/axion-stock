"""Schwab Broker Dashboard (PRD-145).

4 tabs: Accounts, Portfolio, Trading, Research.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Schwab Broker", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

st.title("Schwab Broker")
st.caption("Schwab/Fidelity API integration with OAuth2 authentication")

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Accounts",
    "Portfolio",
    "Trading",
    "Research",
])


# -- Tab 1: Accounts --------------------------------------------------

with tab1:
    st.subheader("Connection Status")

    col1, col2 = st.columns(2)
    with col1:
        app_key = st.text_input("App Key", type="password", value="")
        app_secret = st.text_input("App Secret", type="password", value="")
        callback_url = st.text_input("Callback URL", value="https://127.0.0.1:8182/callback")

    with col2:
        st.write("")
        st.write("")
        if st.button("Connect", type="primary", use_container_width=True):
            st.success("Connected to Schwab API (Demo Mode)")

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Connected")
    m2.metric("Mode", "Demo")
    m3.metric("Account Type", "Individual")
    m4.metric("Uptime", "1h 15m")

    st.subheader("Account Summary")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Equity", "$142,500", "+$1,250")
    m2.metric("Cash", "$65,000")
    m3.metric("Buying Power", "$130,000")
    m4.metric("Positions", "3")
    m5.metric("Day P&L", "+$420", "+0.30%")
    m6.metric("PDT Status", "OK")

    st.subheader("Linked Accounts")
    accounts_data = {
        "Account #": ["DEMO-12345678"],
        "Type": ["Individual"],
        "Equity": ["$142,500"],
        "Cash": ["$65,000"],
        "Buying Power": ["$130,000"],
        "Positions": [3],
    }
    st.dataframe(pd.DataFrame(accounts_data), use_container_width=True)


# -- Tab 2: Portfolio --------------------------------------------------

with tab2:
    st.subheader("Open Positions")

    positions_data = {
        "Symbol": ["SPY", "AAPL", "MSFT"],
        "Qty": [50, 100, 60],
        "Avg Entry": ["$575.00", "$218.00", "$405.00"],
        "Current": ["$590.50", "$230.75", "$415.30"],
        "Market Value": ["$29,525", "$23,075", "$24,918"],
        "Cost Basis": ["$28,750", "$21,800", "$24,300"],
        "Unrealized P&L": ["+$775", "+$1,275", "+$618"],
        "P&L %": ["+2.70%", "+5.85%", "+2.54%"],
        "Day P&L": ["+$150", "+$185", "+$85"],
        "Side": ["Long", "Long", "Long"],
    }
    st.dataframe(pd.DataFrame(positions_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Portfolio Allocation")
        alloc_df = pd.DataFrame({
            "Symbol": ["SPY", "AAPL", "MSFT", "Cash"],
            "Value": [29525, 23075, 24918, 65000],
        }).set_index("Symbol")
        st.bar_chart(alloc_df)

    with col2:
        st.subheader("P&L by Position")
        pnl_df = pd.DataFrame({
            "Symbol": ["SPY", "AAPL", "MSFT"],
            "P&L ($)": [775, 1275, 618],
        }).set_index("Symbol")
        st.bar_chart(pnl_df)

    st.subheader("Position Value Over Time")
    dates = pd.bdate_range(start="2024-06-01", periods=60)
    np.random.seed(145)
    spy_vals = 28750 * np.cumprod(1 + np.random.normal(0.0008, 0.012, 60))
    aapl_vals = 21800 * np.cumprod(1 + np.random.normal(0.001, 0.015, 60))
    msft_vals = 24300 * np.cumprod(1 + np.random.normal(0.0007, 0.011, 60))
    perf_df = pd.DataFrame({
        "SPY": spy_vals,
        "AAPL": aapl_vals,
        "MSFT": msft_vals,
    }, index=dates)
    st.line_chart(perf_df)


# -- Tab 3: Trading ----------------------------------------------------

with tab3:
    st.subheader("Place Order")

    col1, col2, col3 = st.columns(3)
    with col1:
        order_symbol = st.text_input("Symbol", value="AAPL")
        order_side = st.selectbox("Instruction", ["BUY", "SELL", "SHORT", "BUY_TO_COVER"])
    with col2:
        order_qty = st.number_input("Quantity", value=10, min_value=1)
        order_type = st.selectbox("Type", ["MARKET", "LIMIT", "STOP", "STOP_LIMIT", "TRAILING_STOP"])
    with col3:
        order_duration = st.selectbox("Duration", ["DAY", "GTC", "FOK"])
        if order_type in ["LIMIT", "STOP_LIMIT"]:
            limit_price = st.number_input("Limit Price", value=230.0)
        if order_type in ["STOP", "STOP_LIMIT"]:
            stop_price = st.number_input("Stop Price", value=225.0)

    if st.button("Submit Order", type="primary", use_container_width=True):
        st.success(f"Order submitted: {order_side} {order_qty} {order_symbol} ({order_type})")

    st.divider()
    st.subheader("Order History")

    orders_data = {
        "Order ID": ["DEMO-ORD-001", "DEMO-ORD-002", "DEMO-ORD-003"],
        "Symbol": ["AAPL", "SPY", "MSFT"],
        "Side": ["BUY", "BUY", "BUY"],
        "Qty": [100, 50, 60],
        "Type": ["MARKET", "LIMIT", "MARKET"],
        "Status": ["FILLED", "FILLED", "FILLED"],
        "Fill Price": ["$218.00", "$575.00", "$405.00"],
        "Entered": ["Jan 15 10:30", "Jan 14 09:45", "Jan 13 11:00"],
    }
    st.dataframe(pd.DataFrame(orders_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orders", "3")
        st.metric("Filled", "3")
    with col2:
        st.metric("Open", "0")
        st.metric("Canceled", "0")


# -- Tab 4: Research ---------------------------------------------------

with tab4:
    st.subheader("Fundamentals Lookup")

    col1, col2 = st.columns([1, 3])
    with col1:
        research_symbol = st.text_input("Symbol", value="AAPL", key="research_sym")
        if st.button("Lookup", type="primary"):
            st.info(f"Fetching fundamentals for {research_symbol}")

    with col2:
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("P/E Ratio", "31.2")
        m2.metric("EPS", "$7.40")
        m3.metric("Market Cap", "$3.56T")
        m4.metric("Div Yield", "0.44%")
        m5.metric("Beta", "1.21")
        m6.metric("Profit Margin", "25.6%")

        st.write("**Sector:** Technology | **Industry:** Consumer Electronics")
        st.write("**Analyst Consensus:** Buy (30 Buy / 10 Hold / 2 Sell)")
        st.write("**Price Target:** $250.00 (High: $275 / Low: $200)")

    st.divider()
    st.subheader("Stock Screener")

    col1, col2, col3 = st.columns(3)
    with col1:
        scr_sector = st.selectbox("Sector", ["All", "Technology", "Healthcare", "Financial Services", "Consumer Cyclical"])
    with col2:
        scr_min_cap = st.number_input("Min Market Cap ($B)", value=100.0)
    with col3:
        scr_max_pe = st.number_input("Max P/E Ratio", value=50.0)

    screener_data = {
        "Symbol": ["NVDA", "AAPL", "MSFT", "GOOGL", "META"],
        "Description": ["NVIDIA Corp", "Apple Inc", "Microsoft Corp", "Alphabet Inc", "Meta Platforms"],
        "Price": ["$875.20", "$230.75", "$415.30", "$185.40", "$580.30"],
        "Volume": ["42.0M", "55.2M", "22.1M", "28.3M", "18.5M"],
        "Market Cap": ["$2.15T", "$3.56T", "$3.09T", "$2.28T", "$1.48T"],
        "P/E": [65.0, 31.2, 36.8, 25.1, 27.9],
        "Change": ["+1.45%", "+0.81%", "-0.17%", "+0.49%", "+0.94%"],
    }
    st.dataframe(pd.DataFrame(screener_data), use_container_width=True)

    st.divider()
    st.subheader("Market Movers ($SPX)")

    movers_data = {
        "Symbol": ["NVDA", "AAPL", "TSLA", "META", "AMZN"],
        "Description": ["NVIDIA Corp", "Apple Inc", "Tesla Inc", "Meta Platforms", "Amazon.com"],
        "Last Price": ["$875.20", "$230.75", "$382.50", "$580.30", "$202.10"],
        "Change": ["+$12.50", "+$1.85", "-$8.20", "+$5.40", "+$2.10"],
        "% Change": ["+1.45%", "+0.81%", "-2.10%", "+0.94%", "+1.05%"],
        "Volume": ["42.0M", "55.2M", "38.0M", "18.5M", "30.2M"],
    }
    st.dataframe(pd.DataFrame(movers_data), use_container_width=True)
