"""Coinbase Broker Dashboard (PRD-144).

4 tabs: Connection, Crypto Portfolio, Trading, Market Data.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Coinbase", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

st.title("Coinbase Broker")
st.caption("Crypto trading via Coinbase Advanced Trade API")

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Connection",
    "Crypto Portfolio",
    "Trading",
    "Market Data",
])


# -- Tab 1: Connection ------------------------------------------------

with tab1:
    st.subheader("API Connection")

    col1, col2 = st.columns(2)
    with col1:
        api_key = st.text_input("API Key", type="password", value="")
        api_secret = st.text_input("API Secret", type="password", value="")

    with col2:
        st.write("")
        st.write("")
        if st.button("Connect", type="primary", use_container_width=True):
            st.success("Connected to Coinbase (Demo Mode)")

    st.divider()
    st.subheader("Connection Status")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Connected")
    m2.metric("Mode", "Demo")
    m3.metric("API Version", "Advanced v3")
    m4.metric("Uptime", "1h 15m")

    st.subheader("Account Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Value", "$80,990", "+$1,250")
    m2.metric("Crypto Assets", "6")
    m3.metric("USD Cash", "$10,000")
    m4.metric("24h Change", "+1.6%")


# -- Tab 2: Crypto Portfolio ------------------------------------------

with tab2:
    st.subheader("Crypto Holdings")

    holdings_data = {
        "Currency": ["BTC", "ETH", "SOL", "DOGE", "ADA", "XRP", "USD"],
        "Balance": ["0.52", "4.20", "45.0", "15,000", "5,000", "2,000", "$10,000"],
        "Price": ["$95,000", "$3,500", "$200", "$0.32", "$0.95", "$2.30", "-"],
        "Value (USD)": [
            "$49,400", "$14,700", "$9,000", "$4,800", "$4,750", "$4,600", "$10,000",
        ],
        "Allocation": ["50.9%", "15.1%", "9.3%", "4.9%", "4.9%", "4.7%", "10.3%"],
        "P&L": [
            "+$6,760", "+$2,940", "+$2,250", "+$1,050", "+$1,250", "+$1,000", "-",
        ],
    }
    st.dataframe(pd.DataFrame(holdings_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Portfolio Allocation")
        alloc_df = pd.DataFrame({
            "Currency": ["BTC", "ETH", "SOL", "DOGE", "ADA", "XRP", "USD"],
            "Value": [49400, 14700, 9000, 4800, 4750, 4600, 10000],
        }).set_index("Currency")
        st.bar_chart(alloc_df)

    with col2:
        st.subheader("Portfolio Value Over Time")
        np.random.seed(42)
        days = pd.bdate_range(start="2024-11-01", periods=60)
        values = 70000 * np.cumprod(1 + np.random.normal(0.002, 0.02, 60))
        port_df = pd.DataFrame({"Portfolio Value ($)": values}, index=days)
        st.line_chart(port_df)

    st.subheader("Unrealized P&L")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Unrealized P&L", "+$15,250", "+23.2%")
    m2.metric("Best Performer", "ETH (+25%)")
    m3.metric("Worst Performer", "DOGE (+21.9%)")


# -- Tab 3: Trading ---------------------------------------------------

with tab3:
    st.subheader("Place Order")

    col1, col2, col3 = st.columns(3)
    with col1:
        product = st.selectbox("Product", [
            "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD",
        ])
        side = st.selectbox("Side", ["Buy", "Sell"])
    with col2:
        size = st.number_input("Size", value=0.01, min_value=0.00001, format="%.5f")
        order_type = st.selectbox("Type", ["Market", "Limit"])
    with col3:
        if order_type == "Limit":
            limit_price = st.number_input("Limit Price", value=95000.0)
        if st.button("Submit Order", type="primary", use_container_width=True):
            st.success(f"Order submitted: {side} {size} {product} ({order_type})")

    st.divider()
    st.subheader("Active Orders")

    orders_data = {
        "Order ID": ["demo_001", "demo_002"],
        "Product": ["ETH-USD", "SOL-USD"],
        "Side": ["Buy", "Buy"],
        "Size": ["1.0", "10.0"],
        "Type": ["Limit", "Limit"],
        "Limit Price": ["$3,400", "$190"],
        "Status": ["Pending", "Pending"],
    }
    st.dataframe(pd.DataFrame(orders_data), use_container_width=True)

    st.subheader("Recent Fills")
    fills_data = {
        "Fill ID": ["fill_001", "fill_002", "fill_003"],
        "Product": ["BTC-USD", "ETH-USD", "SOL-USD"],
        "Side": ["Buy", "Buy", "Buy"],
        "Price": ["$94,500", "$3,450", "$195"],
        "Size": ["0.10", "2.0", "10.0"],
        "Fee": ["$56.70", "$41.40", "$11.70"],
        "Time": ["Jan 15 10:30", "Jan 15 11:00", "Jan 14 14:22"],
    }
    st.dataframe(pd.DataFrame(fills_data), use_container_width=True)


# -- Tab 4: Market Data -----------------------------------------------

with tab4:
    st.subheader("Spot Prices")

    prices_data = {
        "Pair": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD"],
        "Price": ["$95,000", "$3,500", "$200", "$0.32", "$0.95", "$2.30"],
        "24h Change": ["+2.1%", "+1.8%", "+3.5%", "-0.5%", "+1.2%", "+4.1%"],
        "24h Volume": ["$28.5B", "$14.2B", "$3.8B", "$1.2B", "$680M", "$2.1B"],
    }
    st.dataframe(pd.DataFrame(prices_data), use_container_width=True)

    st.subheader("BTC-USD Price Chart")
    np.random.seed(100)
    n_candles = 60
    base = 90000.0
    closes = [base]
    for _ in range(n_candles - 1):
        closes.append(closes[-1] * (1 + np.random.normal(0.001, 0.02)))
    chart_df = pd.DataFrame({"BTC Close ($)": closes})
    st.line_chart(chart_df)

    st.subheader("Available Products")
    products_data = {
        "Product": ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD", "XRP-USD"],
        "Base": ["BTC", "ETH", "SOL", "DOGE", "ADA", "XRP"],
        "Quote": ["USD"] * 6,
        "Min Size": ["0.00001", "0.00001", "0.01", "0.01", "0.01", "0.01"],
        "Status": ["Online"] * 6,
    }
    st.dataframe(pd.DataFrame(products_data), use_container_width=True)
