"""Portfolio Rebalancing Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Portfolio Rebalancing", layout="wide")
st.title("Portfolio Rebalancing")

# --- Sidebar ---
st.sidebar.header("Rebalance Settings")
trigger = st.sidebar.selectbox("Trigger", ["Combined", "Calendar", "Threshold", "Manual"])
frequency = st.sidebar.selectbox("Frequency", ["Weekly", "Monthly", "Quarterly", "Annual"], index=2)
threshold = st.sidebar.slider("Drift Threshold", 0.01, 0.20, 0.05, 0.01)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Drift", "Plan", "Schedule", "History",
])

# --- Tab 1: Drift ---
with tab1:
    st.subheader("Portfolio Drift Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Max Drift", "8.2%")
    col2.metric("Mean Drift", "4.1%")
    col3.metric("Assets Over Threshold", "3 of 8")
    col4.metric("Status", "Rebalance Needed")

    st.markdown("#### Per-Asset Drift")
    drift_data = pd.DataFrame([
        {"Symbol": "AAPL", "Target": "12.5%", "Current": "15.2%",
         "Drift": "+2.7%", "Status": "OK"},
        {"Symbol": "MSFT", "Target": "12.5%", "Current": "20.7%",
         "Drift": "+8.2%", "Status": "Critical"},
        {"Symbol": "GOOGL", "Target": "12.5%", "Current": "8.3%",
         "Drift": "-4.2%", "Status": "Threshold"},
        {"Symbol": "AMZN", "Target": "12.5%", "Current": "10.8%",
         "Drift": "-1.7%", "Status": "OK"},
        {"Symbol": "META", "Target": "12.5%", "Current": "7.2%",
         "Drift": "-5.3%", "Status": "Threshold"},
        {"Symbol": "TSLA", "Target": "12.5%", "Current": "18.8%",
         "Drift": "+6.3%", "Status": "Threshold"},
        {"Symbol": "NVDA", "Target": "12.5%", "Current": "11.5%",
         "Drift": "-1.0%", "Status": "OK"},
        {"Symbol": "JPM", "Target": "12.5%", "Current": "7.5%",
         "Drift": "-5.0%", "Status": "Threshold"},
    ])
    st.dataframe(drift_data, use_container_width=True, hide_index=True)

# --- Tab 2: Plan ---
with tab2:
    st.subheader("Rebalance Plan")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trades", "6")
    col2.metric("Turnover", "$12,450")
    col3.metric("Est. Cost", "$1.25")
    col4.metric("Drift Reduction", "85%")

    st.markdown("#### Proposed Trades")
    plan_data = pd.DataFrame([
        {"Symbol": "MSFT", "Side": "Sell", "Shares": 15, "Value": "$5,250",
         "From": "20.7%", "To": "12.5%", "Tax": "$0"},
        {"Symbol": "TSLA", "Side": "Sell", "Shares": 20, "Value": "$3,600",
         "From": "18.8%", "To": "12.5%", "Tax": "$0"},
        {"Symbol": "GOOGL", "Side": "Buy", "Shares": 25, "Value": "$3,000",
         "From": "8.3%", "To": "12.5%", "Tax": "N/A"},
        {"Symbol": "META", "Side": "Buy", "Shares": 12, "Value": "$2,400",
         "From": "7.2%", "To": "12.5%", "Tax": "N/A"},
        {"Symbol": "JPM", "Side": "Buy", "Shares": 18, "Value": "$2,700",
         "From": "7.5%", "To": "12.5%", "Tax": "N/A"},
        {"Symbol": "AAPL", "Side": "Sell", "Shares": 8, "Value": "$1,200",
         "From": "15.2%", "To": "12.5%", "Tax": "$0"},
    ])
    st.dataframe(plan_data, use_container_width=True, hide_index=True)

# --- Tab 3: Schedule ---
with tab3:
    st.subheader("Rebalance Schedule")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trigger", "Combined")
    col2.metric("Frequency", "Quarterly")
    col3.metric("Next Scheduled", "2026-04-01")
    col4.metric("Days Until", "59")

    col5, col6 = st.columns(2)
    col5.metric("Last Rebalance", "2026-01-02")
    col6.metric("Threshold Breached", "Yes")

    st.markdown("#### Schedule Configuration")
    sched_data = pd.DataFrame([
        {"Setting": "Trigger Type", "Value": "Combined (Calendar OR Threshold)"},
        {"Setting": "Calendar Frequency", "Value": "Quarterly"},
        {"Setting": "Drift Threshold", "Value": "5.0%"},
        {"Setting": "Critical Threshold", "Value": "10.0%"},
        {"Setting": "Min Trade Size", "Value": "$100"},
        {"Setting": "Tax-Aware", "Value": "Enabled"},
    ])
    st.dataframe(sched_data, use_container_width=True, hide_index=True)

# --- Tab 4: History ---
with tab4:
    st.subheader("Rebalance History")

    history_data = pd.DataFrame([
        {"Date": "2026-01-02", "Trigger": "Calendar", "Trades": 5,
         "Turnover": "$8,200", "Cost": "$0.82", "Drift Before": "6.5%",
         "Drift After": "0.3%", "Status": "Executed"},
        {"Date": "2025-10-01", "Trigger": "Calendar", "Trades": 4,
         "Turnover": "$5,800", "Cost": "$0.58", "Drift Before": "4.8%",
         "Drift After": "0.2%", "Status": "Executed"},
        {"Date": "2025-08-15", "Trigger": "Threshold", "Trades": 3,
         "Turnover": "$9,500", "Cost": "$0.95", "Drift Before": "11.2%",
         "Drift After": "1.0%", "Status": "Executed"},
        {"Date": "2025-07-01", "Trigger": "Calendar", "Trades": 6,
         "Turnover": "$7,100", "Cost": "$0.71", "Drift Before": "5.2%",
         "Drift After": "0.1%", "Status": "Executed"},
    ])
    st.dataframe(history_data, use_container_width=True, hide_index=True)
