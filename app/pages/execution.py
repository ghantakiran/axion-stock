"""Execution Analytics Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Execution Analytics", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Execution Analytics")

# --- Sidebar ---
st.sidebar.header("Analysis Settings")
period = st.sidebar.selectbox("Period", ["Today", "This Week", "This Month", "YTD"], index=2)
broker_filter = st.sidebar.multiselect("Broker", ["All", "Alpaca", "IBKR", "Paper"], default=["All"])

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Transaction Cost Analysis", "Execution Scheduling",
    "Broker Comparison", "Fill Quality",
])

# --- Tab 1: TCA ---
with tab1:
    st.subheader("Implementation Shortfall Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Cost", "8.5 bps")
    col2.metric("Total Cost", "$4,250")
    col3.metric("Spread Cost", "2.8 bps")
    col4.metric("Impact Cost", "3.2 bps")

    st.markdown("#### Cost Decomposition")
    tca_data = pd.DataFrame([
        {"Symbol": "AAPL", "Side": "Buy", "Qty": "1,000", "Decision": "$182.50",
         "Execution": "$182.68", "Spread": "2.5 bps", "Timing": "1.8 bps",
         "Impact": "3.4 bps", "Total": "9.2 bps"},
        {"Symbol": "MSFT", "Side": "Buy", "Qty": "500", "Decision": "$378.00",
         "Execution": "$378.15", "Spread": "2.1 bps", "Timing": "0.9 bps",
         "Impact": "2.8 bps", "Total": "6.5 bps"},
        {"Symbol": "GOOGL", "Side": "Sell", "Qty": "800", "Decision": "$141.20",
         "Execution": "$141.05", "Spread": "3.2 bps", "Timing": "2.1 bps",
         "Impact": "4.1 bps", "Total": "10.6 bps"},
    ])
    st.dataframe(tca_data, use_container_width=True, hide_index=True)

    st.markdown("#### Aggregate Statistics")
    agg_data = pd.DataFrame([
        {"Metric": "Average Cost (bps)", "Value": "8.5"},
        {"Metric": "Median Cost (bps)", "Value": "7.8"},
        {"Metric": "Std Dev Cost (bps)", "Value": "3.2"},
        {"Metric": "Cost per $1M", "Value": "$850"},
        {"Metric": "% Positive Alpha", "Value": "25%"},
        {"Metric": "Total Notional", "Value": "$5.2M"},
    ])
    st.dataframe(agg_data, use_container_width=True, hide_index=True)

# --- Tab 2: Execution Scheduling ---
with tab2:
    st.subheader("Optimal Execution Scheduling")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Strategy", "VWAP")
    col2.metric("Slices", "13")
    col3.metric("Est. Impact", "4.2 bps")
    col4.metric("Duration", "Full Day")

    st.markdown("#### Strategy Comparison")
    strategy_data = pd.DataFrame([
        {"Strategy": "TWAP", "Est. Impact (bps)": "5.1",
         "Timing Risk": "Medium", "Best For": "Low urgency"},
        {"Strategy": "VWAP", "Est. Impact (bps)": "4.2",
         "Timing Risk": "Low", "Best For": "Normal conditions"},
        {"Strategy": "IS (Aggressive)", "Est. Impact (bps)": "6.8",
         "Timing Risk": "Very Low", "Best For": "High urgency / volatile"},
    ])
    st.dataframe(strategy_data, use_container_width=True, hide_index=True)

    st.markdown("#### VWAP Schedule")
    schedule_data = pd.DataFrame([
        {"Time": "9:30-10:00", "% of Order": "12%", "Qty": "1,200",
         "Cum %": "12%", "Impact": "1.2 bps"},
        {"Time": "10:00-10:30", "% of Order": "9%", "Qty": "900",
         "Cum %": "21%", "Impact": "0.9 bps"},
        {"Time": "10:30-11:00", "% of Order": "7%", "Qty": "700",
         "Cum %": "28%", "Impact": "0.5 bps"},
        {"Time": "11:00-11:30", "% of Order": "6%", "Qty": "600",
         "Cum %": "34%", "Impact": "0.4 bps"},
        {"Time": "3:30-4:00", "% of Order": "13%", "Qty": "1,300",
         "Cum %": "100%", "Impact": "1.4 bps"},
    ])
    st.dataframe(schedule_data, use_container_width=True, hide_index=True)

# --- Tab 3: Broker Comparison ---
with tab3:
    st.subheader("Broker Execution Quality")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Best Broker", "Alpaca (85)")
    col2.metric("Avg Fill Rate", "98.5%")
    col3.metric("Avg Slippage", "4.2 bps")
    col4.metric("Brokers Tracked", "3")

    st.markdown("#### Broker Scorecard")
    broker_data = pd.DataFrame([
        {"Broker": "Alpaca", "Orders": "245", "Fill Rate": "99.2%",
         "Avg Slippage": "3.8 bps", "Avg Commission": "0.0 bps",
         "Price Improvement": "32%", "Latency": "45ms", "Score": "85"},
        {"Broker": "IBKR", "Orders": "180", "Fill Rate": "98.9%",
         "Avg Slippage": "3.2 bps", "Avg Commission": "1.5 bps",
         "Price Improvement": "38%", "Latency": "28ms", "Score": "82"},
        {"Broker": "Paper", "Orders": "520", "Fill Rate": "100%",
         "Avg Slippage": "5.0 bps", "Avg Commission": "0.0 bps",
         "Price Improvement": "0%", "Latency": "1ms", "Score": "78"},
    ])
    st.dataframe(broker_data, use_container_width=True, hide_index=True)

    st.info(
        "Alpaca ranks highest overall due to zero commissions and competitive "
        "fill rates. IBKR shows better price improvement but higher commission costs."
    )

# --- Tab 4: Fill Quality ---
with tab4:
    st.subheader("Fill Quality Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Effective Spread", "5.2 bps")
    col2.metric("Price Improvement", "28%")
    col3.metric("Avg Fill Rate", "98.8%")
    col4.metric("Quality Score", "82")

    st.markdown("#### Fill Distribution")
    dist_data = pd.DataFrame([
        {"Metric": "Avg Effective Spread", "Value": "5.2 bps"},
        {"Metric": "Spread P25", "Value": "2.8 bps"},
        {"Metric": "Spread P50 (Median)", "Value": "4.5 bps"},
        {"Metric": "Spread P75", "Value": "7.1 bps"},
        {"Metric": "Spread P95", "Value": "12.3 bps"},
        {"Metric": "Avg Price Improvement", "Value": "1.8 bps"},
        {"Metric": "Avg Adverse Selection", "Value": "0.9 bps"},
        {"Metric": "% Fully Filled", "Value": "95.2%"},
    ])
    st.dataframe(dist_data, use_container_width=True, hide_index=True)

    st.markdown("#### Quality by Symbol")
    symbol_data = pd.DataFrame([
        {"Symbol": "AAPL", "Orders": "85", "Fill Rate": "99.1%",
         "Eff. Spread": "4.1 bps", "Price Improv.": "2.1 bps",
         "Quality Score": "88"},
        {"Symbol": "MSFT", "Orders": "62", "Fill Rate": "98.8%",
         "Eff. Spread": "3.8 bps", "Price Improv.": "1.9 bps",
         "Quality Score": "86"},
        {"Symbol": "GOOGL", "Orders": "48", "Fill Rate": "98.2%",
         "Eff. Spread": "6.5 bps", "Price Improv.": "1.2 bps",
         "Quality Score": "78"},
    ])
    st.dataframe(symbol_data, use_container_width=True, hide_index=True)
