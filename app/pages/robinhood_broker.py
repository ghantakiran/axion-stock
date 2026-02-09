"""Robinhood Broker Dashboard (PRD-143).

4 tabs: Connection, Portfolio, Orders, Crypto.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Robinhood Broker", layout="wide")
except Exception:
    import streamlit as st

import numpy as np
import pandas as pd

st.title("Robinhood Broker")
st.caption("Robinhood trading integration with demo mode fallback")

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Connection",
    "Portfolio",
    "Orders",
    "Crypto",
])


# -- Tab 1: Connection ------------------------------------------------

with tab1:
    st.subheader("API Connection")

    col1, col2 = st.columns(2)
    with col1:
        rh_username = st.text_input("Robinhood Email", value="")
        rh_password = st.text_input("Password", type="password", value="")
        rh_mfa = st.text_input("MFA Code (optional)", value="")

    with col2:
        st.write("")
        st.write("")
        st.write("")
        if st.button("Connect", type="primary", use_container_width=True):
            st.success("Connected to Robinhood (Demo Mode)")
        if st.button("Disconnect", use_container_width=True):
            st.info("Disconnected from Robinhood")

    st.divider()
    st.subheader("Connection Status")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Connected")
    m2.metric("Mode", "Demo")
    m3.metric("Account Type", "Margin")
    m4.metric("Uptime", "1h 12m")

    st.subheader("Account Summary")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Equity", "$92,350", "+$1,250")
    m2.metric("Cash", "$45,000")
    m3.metric("Buying Power", "$45,000")
    m4.metric("Positions", "3")
    m5.metric("Day P&L", "+$1,250", "+1.37%")
    m6.metric("Withdrawable", "$40,000")

    st.info("Running in **Demo Mode** — no real API credentials provided. "
            "All data shown is simulated for demonstration purposes.")


# -- Tab 2: Portfolio --------------------------------------------------

with tab2:
    st.subheader("Open Positions")

    positions_data = {
        "Symbol": ["AAPL", "NVDA", "TSLA"],
        "Qty": [100, 25, 40],
        "Avg Cost": ["$152.30", "$480.00", "$220.50"],
        "Current": ["$187.50", "$624.00", "$325.00"],
        "Market Value": ["$18,750", "$15,600", "$13,000"],
        "Unrealized P&L": ["+$3,520", "+$3,600", "+$4,180"],
        "P&L %": ["+23.1%", "+30.0%", "+47.4%"],
        "Side": ["Long", "Long", "Long"],
    }
    st.dataframe(pd.DataFrame(positions_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Portfolio Allocation")
        alloc_df = pd.DataFrame({
            "Category": ["AAPL", "NVDA", "TSLA", "Cash"],
            "Value": [18750, 15600, 13000, 45000],
        }).set_index("Category")
        st.bar_chart(alloc_df)

    with col2:
        st.subheader("P&L by Position")
        pnl_df = pd.DataFrame({
            "Symbol": ["AAPL", "NVDA", "TSLA"],
            "P&L ($)": [3520, 3600, 4180],
        }).set_index("Symbol")
        st.bar_chart(pnl_df)

    # Portfolio value over time
    st.subheader("Portfolio Value Over Time")
    dates = pd.bdate_range(start="2024-06-01", periods=90)
    np.random.seed(143)
    values = 85000 * np.cumprod(1 + np.random.normal(0.0008, 0.012, 90))
    perf_df = pd.DataFrame({"Portfolio Value": values}, index=dates)
    st.line_chart(perf_df)

    # Summary metrics
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Value", "$92,350")
    m2.metric("Total P&L", "+$11,300", "+13.9%")
    m3.metric("Best Position", "TSLA (+47.4%)")
    m4.metric("Position Count", "3")


# -- Tab 3: Orders ----------------------------------------------------

with tab3:
    st.subheader("Place Order")

    col1, col2, col3 = st.columns(3)
    with col1:
        order_symbol = st.text_input("Symbol", value="AAPL")
        order_side = st.selectbox("Side", ["Buy", "Sell"])
    with col2:
        order_qty = st.number_input("Quantity", value=10, min_value=1)
        order_type = st.selectbox("Type", ["Market", "Limit", "Stop", "Stop Limit"])
    with col3:
        order_tif = st.selectbox("Time in Force", ["Good for Day", "Good till Cancel", "IOC"])
        if order_type in ["Limit", "Stop Limit"]:
            limit_price = st.number_input("Limit Price", value=185.0)
        if order_type in ["Stop", "Stop Limit"]:
            stop_price = st.number_input("Stop Price", value=180.0)

    if st.button("Submit Order", type="primary", use_container_width=True):
        st.success(f"Order submitted: {order_side} {order_qty} {order_symbol} ({order_type})")

    st.divider()
    st.subheader("Order History")

    orders_data = {
        "Order ID": ["rh_ord_001", "rh_ord_002", "rh_ord_003", "rh_ord_004"],
        "Symbol": ["AAPL", "NVDA", "TSLA", "MSFT"],
        "Side": ["Buy", "Buy", "Sell", "Buy"],
        "Qty": [10, 5, 10, 15],
        "Type": ["Market", "Limit", "Market", "Limit"],
        "Status": ["Filled", "Confirmed", "Filled", "Cancelled"],
        "Fill Price": ["$187.50", "-", "$328.00", "-"],
        "Submitted": ["10:30 AM", "11:15 AM", "2:45 PM", "9:31 AM"],
    }
    st.dataframe(pd.DataFrame(orders_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orders Today", "4")
        st.metric("Filled", "2")
    with col2:
        st.metric("Pending", "1")
        st.metric("Cancelled", "1")


# -- Tab 4: Crypto ----------------------------------------------------

with tab4:
    st.subheader("Crypto Portfolio")

    crypto_positions = {
        "Symbol": ["BTC", "ETH", "DOGE"],
        "Qty": ["0.5000", "5.0000", "10,000"],
        "Avg Cost": ["$58,200", "$2,900", "$0.120"],
        "Current": ["$67,300", "$3,460", "$0.163"],
        "Market Value": ["$33,650", "$17,300", "$1,630"],
        "Unrealized P&L": ["+$4,550", "+$2,800", "+$430"],
        "P&L %": ["+15.6%", "+19.3%", "+35.8%"],
    }
    st.dataframe(pd.DataFrame(crypto_positions), use_container_width=True)

    st.divider()
    st.subheader("Crypto Quotes")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("BTC", "$67,300", "+$500 (+0.75%)")
        st.caption("24h Vol: 25,000 BTC")
    with col2:
        st.metric("ETH", "$3,460", "+$60 (+1.76%)")
        st.caption("24h Vol: 150,000 ETH")
    with col3:
        st.metric("DOGE", "$0.163", "+$0.005 (+3.16%)")
        st.caption("24h Vol: 2.5B DOGE")

    # Crypto price chart
    st.subheader("BTC Price History (30d)")
    np.random.seed(99)
    btc_dates = pd.bdate_range(start="2024-12-01", periods=30)
    btc_prices = 60000 * np.cumprod(1 + np.random.normal(0.002, 0.025, 30))
    btc_df = pd.DataFrame({"BTC Price": btc_prices}, index=btc_dates)
    st.line_chart(btc_df)

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Crypto Value", "$52,580")
    with col2:
        st.metric("Total Crypto P&L", "+$7,780")
    with col3:
        st.metric("Crypto % of Portfolio", "36.3%")
