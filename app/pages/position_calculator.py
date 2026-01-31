"""Position Calculator Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Position Calculator", layout="wide")
st.title("Position Calculator")

# --- Sidebar ---
st.sidebar.header("Position Calculator")
account_value = st.sidebar.number_input("Account Value ($)", value=100_000, step=10_000)
risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.25, 5.0, 1.0, 0.25)
sizing_method = st.sidebar.selectbox(
    "Sizing Method", ["Fixed Risk", "Kelly Criterion", "Half Kelly", "Fixed Dollar"],
)
instrument = st.sidebar.selectbox("Instrument", ["Stock", "Option", "Future"])

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Size Calculator", "Portfolio Heat", "Drawdown Monitor", "History",
])

# --- Tab 1: Size Calculator ---
with tab1:
    st.subheader("Position Size Calculator")

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", "AAPL")
        entry = st.number_input("Entry Price", value=185.00, step=0.50)
    with col2:
        stop = st.number_input("Stop Price", value=180.00, step=0.50)
        target = st.number_input("Target Price", value=200.00, step=0.50)
    with col3:
        st.markdown("#### Result")
        st.metric("Position Size", "200 shares")
        st.metric("Risk Amount", "$1,000")

    st.markdown("---")

    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Position Value", "$37,000")
    col5.metric("Risk %", "1.00%")
    col6.metric("Risk/Reward", "3.0:1")
    col7.metric("R-Multiple", "1.0R")

    st.markdown("#### Sizing Details")
    details_data = pd.DataFrame([
        {"Parameter": "Account Value", "Value": "$100,000"},
        {"Parameter": "Risk Per Trade", "Value": "1.00%"},
        {"Parameter": "Dollar Risk", "Value": "$1,000"},
        {"Parameter": "Risk Per Share", "Value": "$5.00"},
        {"Parameter": "Position Size", "Value": "200 shares"},
        {"Parameter": "Max Position (15%)", "Value": "666 shares"},
        {"Parameter": "Method", "Value": "Fixed Risk"},
    ])
    st.dataframe(details_data, use_container_width=True, hide_index=True)

# --- Tab 2: Portfolio Heat ---
with tab2:
    st.subheader("Portfolio Heat Monitor")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Heat", "2.8%", delta=None)
    col2.metric("Heat Limit", "6.0%")
    col3.metric("Available", "3.2%")
    col4.metric("Positions", "4")

    st.markdown("#### Position Risk Breakdown")
    heat_data = pd.DataFrame([
        {"Symbol": "AAPL", "Qty": 200, "Entry": "$185.00", "Stop": "$180.00",
         "Current": "$188.50", "Risk $": "$1,700", "Heat %": "1.70%"},
        {"Symbol": "MSFT", "Qty": 50, "Entry": "$410.00", "Stop": "$400.00",
         "Current": "$415.00", "Risk $": "$750", "Heat %": "0.75%"},
        {"Symbol": "GOOGL", "Qty": 100, "Entry": "$148.00", "Stop": "$145.00",
         "Current": "$149.50", "Risk $": "$450", "Heat %": "0.45%"},
        {"Symbol": "META", "Qty": 15, "Entry": "$520.00", "Stop": "$510.00",
         "Current": "$528.00", "Risk $": "$270", "Heat %": "0.27%"},
    ])
    st.dataframe(heat_data, use_container_width=True, hide_index=True)

    st.markdown("#### Heat Summary")
    summary_data = pd.DataFrame([
        {"Metric": "Total Dollar Risk", "Value": "$3,170"},
        {"Metric": "Total Heat %", "Value": "3.17%"},
        {"Metric": "Largest Position Risk", "Value": "AAPL (1.70%)"},
        {"Metric": "Max Additional Risk", "Value": "$2,830"},
    ])
    st.dataframe(summary_data, use_container_width=True, hide_index=True)

# --- Tab 3: Drawdown Monitor ---
with tab3:
    st.subheader("Drawdown Monitor")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Drawdown", "-3.2%")
    col2.metric("Peak Value", "$103,500")
    col3.metric("Current Value", "$100,200")
    col4.metric("Size Multiplier", "1.0x")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Max Drawdown Limit", "10.0%")
    col6.metric("Reduce At", "8.0%")
    col7.metric("Block At", "10.0%")
    col8.metric("Status", "Normal")

    st.markdown("#### Drawdown History")
    dd_data = pd.DataFrame([
        {"Date": "2026-01-31", "Account": "$100,200", "Peak": "$103,500",
         "Drawdown %": "-3.2%", "Status": "Normal", "Multiplier": "1.0x"},
        {"Date": "2026-01-28", "Account": "$101,800", "Peak": "$103,500",
         "Drawdown %": "-1.6%", "Status": "Normal", "Multiplier": "1.0x"},
        {"Date": "2026-01-25", "Account": "$103,500", "Peak": "$103,500",
         "Drawdown %": "0.0%", "Status": "New Peak", "Multiplier": "1.0x"},
        {"Date": "2026-01-22", "Account": "$102,100", "Peak": "$102,800",
         "Drawdown %": "-0.7%", "Status": "Normal", "Multiplier": "1.0x"},
    ])
    st.dataframe(dd_data, use_container_width=True, hide_index=True)

# --- Tab 4: History ---
with tab4:
    st.subheader("Sizing History")

    history_data = pd.DataFrame([
        {"Time": "2026-01-31 10:15", "Symbol": "AAPL", "Method": "Fixed Risk",
         "Size": "200 shares", "Risk": "$1,000", "R:R": "3.0:1"},
        {"Time": "2026-01-30 14:30", "Symbol": "MSFT", "Method": "Fixed Risk",
         "Size": "50 shares", "Risk": "$500", "R:R": "2.5:1"},
        {"Time": "2026-01-28 09:45", "Symbol": "TSLA", "Method": "Half Kelly",
         "Size": "30 shares", "Risk": "$750", "R:R": "2.0:1"},
        {"Time": "2026-01-25 11:00", "Symbol": "META", "Method": "Fixed Risk",
         "Size": "15 shares", "Risk": "$300", "R:R": "4.0:1"},
    ])
    st.dataframe(history_data, use_container_width=True, hide_index=True)

    st.markdown("#### Statistics")
    stats_data = pd.DataFrame([
        {"Metric": "Total Calculations", "Value": "47"},
        {"Metric": "Average Risk %", "Value": "1.12%"},
        {"Metric": "Average R:R", "Value": "2.8:1"},
        {"Metric": "Most Sized Symbol", "Value": "AAPL (12x)"},
    ])
    st.dataframe(stats_data, use_container_width=True, hide_index=True)
