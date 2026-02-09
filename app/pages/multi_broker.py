"""Multi-Broker Dashboard (PRD-146).

4 tabs: Broker Status, Unified Portfolio, Order Routing, Configuration.
"""

try:
    import streamlit as st
    st.set_page_config(page_title="Multi-Broker", layout="wide")
except Exception:
    import streamlit as st

import json
from datetime import datetime

import numpy as np
import pandas as pd

st.title("Smart Multi-Broker Execution")
st.caption("Unified routing layer across Alpaca, Robinhood, Coinbase, and Schwab")

# =====================================================================
# Tabs
# =====================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "Broker Status",
    "Unified Portfolio",
    "Order Routing",
    "Configuration",
])


# -- Tab 1: Broker Status -----------------------------------------------

with tab1:
    st.subheader("Connection Status")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Brokers", "4")
    m2.metric("Connected", "4", "+4")
    m3.metric("Avg Latency", "70ms")
    m4.metric("Last Sync", "Just now")

    status_data = {
        "Broker": ["Alpaca", "Robinhood", "Coinbase", "Schwab"],
        "Status": ["Connected", "Connected", "Connected", "Connected"],
        "Mode": ["Paper", "Demo", "Demo", "Demo"],
        "Assets": ["Stocks, Options", "Stocks, Crypto, Options", "Crypto", "Stocks, Options, Mutual Funds"],
        "Latency": ["50ms", "80ms", "60ms", "90ms"],
        "Priority": [0, 1, 0, 2],
        "Last Sync": ["2 min ago", "5 min ago", "1 min ago", "3 min ago"],
    }
    st.dataframe(pd.DataFrame(status_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Latency by Broker")
        latency_df = pd.DataFrame({
            "Broker": ["Alpaca", "Robinhood", "Coinbase", "Schwab"],
            "Latency (ms)": [50, 80, 60, 90],
        }).set_index("Broker")
        st.bar_chart(latency_df)

    with col2:
        st.subheader("Asset Coverage")
        coverage = {
            "Asset": ["Stocks", "Options", "Crypto", "Mutual Funds"],
            "Brokers": ["Alpaca, Robinhood, Schwab", "Alpaca, Robinhood, Schwab", "Robinhood, Coinbase", "Schwab"],
            "Count": [3, 3, 2, 1],
        }
        st.dataframe(pd.DataFrame(coverage), use_container_width=True)


# -- Tab 2: Unified Portfolio -------------------------------------------

with tab2:
    st.subheader("Aggregated Portfolio")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Value", "$422,500", "+$8,250")
    m2.metric("Total P&L", "+$8,250", "+2.0%")
    m3.metric("Total Cash", "$145,000")
    m4.metric("Positions", "5")
    m5.metric("Brokers Active", "4")
    m6.metric("Last Sync", "Just now")

    positions_data = {
        "Symbol": ["AAPL", "SPY", "MSFT", "BTC-USD", "ETH-USD"],
        "Total Qty": [150, 80, 50, 0.5, 5.0],
        "Avg Cost": ["$210.00", "$575.00", "$400.00", "$65,000", "$3,200"],
        "Market Value": ["$34,612", "$47,240", "$20,765", "$33,750", "$17,500"],
        "P&L": ["+$3,112", "+$1,240", "+$765", "+$1,250", "+$1,500"],
        "P&L %": ["+9.9%", "+2.7%", "+3.8%", "+3.8%", "+9.4%"],
        "Brokers": ["Alpaca (100), Schwab (50)", "Alpaca (50), Schwab (30)", "Alpaca (50)", "Coinbase", "Coinbase"],
    }
    st.dataframe(pd.DataFrame(positions_data), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Allocation by Broker")
        alloc_df = pd.DataFrame({
            "Broker": ["Alpaca", "Schwab", "Coinbase", "Robinhood"],
            "Value ($)": [150000, 122500, 51250, 98750],
        }).set_index("Broker")
        st.bar_chart(alloc_df)

    with col2:
        st.subheader("P&L by Position")
        pnl_df = pd.DataFrame({
            "Symbol": ["AAPL", "SPY", "MSFT", "BTC-USD", "ETH-USD"],
            "P&L ($)": [3112, 1240, 765, 1250, 1500],
        }).set_index("Symbol")
        st.bar_chart(pnl_df)

    st.subheader("Portfolio Value Over Time")
    dates = pd.bdate_range(start="2024-06-01", periods=60)
    np.random.seed(146)
    total_vals = 400000 * np.cumprod(1 + np.random.normal(0.0005, 0.008, 60))
    perf_df = pd.DataFrame({"Portfolio Value": total_vals}, index=dates)
    st.line_chart(perf_df)


# -- Tab 3: Order Routing -----------------------------------------------

with tab3:
    st.subheader("Route & Execute Order")

    col1, col2, col3 = st.columns(3)
    with col1:
        rt_symbol = st.text_input("Symbol", value="AAPL")
        rt_asset = st.selectbox("Asset Type", ["stock", "crypto", "options", "mutual_funds"])
    with col2:
        rt_side = st.selectbox("Side", ["buy", "sell"])
        rt_qty = st.number_input("Quantity", value=10, min_value=1)
    with col3:
        rt_type = st.selectbox("Order Type", ["market", "limit"])
        rt_fractional = st.checkbox("Fractional Shares")

    if st.button("Route & Preview", type="primary", use_container_width=True):
        if rt_asset == "crypto":
            broker = "Coinbase"
            reason = "Smart default: crypto -> Coinbase"
        elif rt_fractional:
            broker = "Robinhood"
            reason = "Smart default: fractional -> Robinhood"
        elif rt_asset == "options":
            broker = "Schwab"
            reason = "Smart default: options -> Schwab"
        else:
            broker = "Alpaca"
            reason = "Smart default: stock -> Alpaca (lowest cost)"

        st.success(f"Routed to **{broker}**: {reason}")
        st.write(f"Estimated fee: $0.00 | Estimated latency: 50ms")
        st.write(f"Fallback chain: Schwab -> Robinhood")

    if st.button("Execute Order", use_container_width=True):
        st.success(f"Order executed: {rt_side.upper()} {rt_qty} {rt_symbol}")

    st.divider()
    st.subheader("Recent Route Decisions")

    routes_data = {
        "Time": ["10:30:15", "10:29:42", "10:28:05", "10:25:30", "10:22:10"],
        "Symbol": ["AAPL", "BTC-USD", "SPY_C590", "MSFT", "ETH-USD"],
        "Asset": ["stock", "crypto", "options", "stock", "crypto"],
        "Routed To": ["Alpaca", "Coinbase", "Schwab", "Alpaca", "Coinbase"],
        "Reason": [
            "Smart default: stock -> Alpaca",
            "Smart default: crypto -> Coinbase",
            "Smart default: options -> Schwab",
            "Scored best (0.85): cost, speed",
            "Smart default: crypto -> Coinbase",
        ],
        "Fee": ["$0.00", "$0.48", "$0.65", "$0.00", "$0.36"],
        "Latency": ["45ms", "55ms", "82ms", "48ms", "58ms"],
        "Status": ["Filled", "Filled", "Filled", "Filled", "Filled"],
    }
    st.dataframe(pd.DataFrame(routes_data), use_container_width=True)


# -- Tab 4: Configuration -----------------------------------------------

with tab4:
    st.subheader("Routing Rules")

    st.write("Define custom routing rules per asset type. Rules override smart defaults.")

    rules_data = {
        "Asset Type": ["stock", "crypto", "options", "mutual_funds", "fractional"],
        "Preferred Broker": ["Alpaca", "Coinbase", "Schwab", "Schwab", "Robinhood"],
        "Fallbacks": [
            "Schwab, Robinhood",
            "Robinhood",
            "Alpaca, Robinhood",
            "-",
            "Alpaca",
        ],
        "Criteria": ["Cost", "Speed", "Fill Quality", "Cost", "Cost"],
    }
    st.dataframe(pd.DataFrame(rules_data), use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        new_asset = st.selectbox("Asset Type", ["stock", "crypto", "options", "mutual_funds"], key="new_rule_asset")
    with col2:
        new_broker = st.selectbox("Preferred Broker", ["alpaca", "robinhood", "coinbase", "schwab"], key="new_rule_broker")
    with col3:
        new_criteria = st.selectbox("Criteria", ["cost", "speed", "fill_quality"], key="new_rule_criteria")

    if st.button("Add/Update Rule", use_container_width=True):
        st.success(f"Rule updated: {new_asset} -> {new_broker} (criteria: {new_criteria})")

    st.divider()
    st.subheader("Broker Priority Ordering")

    priority_data = {
        "Priority": [0, 1, 2, 3],
        "Broker": ["Alpaca", "Coinbase", "Robinhood", "Schwab"],
        "Latency": ["50ms", "60ms", "80ms", "90ms"],
        "Status": ["Connected", "Connected", "Connected", "Connected"],
    }
    st.dataframe(pd.DataFrame(priority_data), use_container_width=True)

    st.divider()
    st.subheader("Fee Schedules")

    fee_data = {
        "Broker": ["Alpaca", "Robinhood", "Coinbase", "Schwab"],
        "Stock Commission": ["$0.00", "$0.00", "N/A", "$0.00"],
        "Options/Contract": ["$0.65", "$0.00", "N/A", "$0.65"],
        "Crypto Fee": ["N/A", "0.50% spread", "0.40%", "N/A"],
        "Mutual Fund Fee": ["N/A", "N/A", "N/A", "$0.00"],
    }
    st.dataframe(pd.DataFrame(fee_data), use_container_width=True)

    st.divider()
    st.subheader("Scoring Weights")

    col1, col2, col3 = st.columns(3)
    with col1:
        w_cost = st.slider("Cost Weight", 0.0, 1.0, 0.4, 0.05)
    with col2:
        w_speed = st.slider("Speed Weight", 0.0, 1.0, 0.3, 0.05)
    with col3:
        w_fill = st.slider("Fill Quality Weight", 0.0, 1.0, 0.3, 0.05)

    if st.button("Update Weights", use_container_width=True):
        st.success(f"Weights updated: cost={w_cost}, speed={w_speed}, fill={w_fill}")
