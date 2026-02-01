"""Pairs Trading Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Pairs Trading", layout="wide")
st.title("Pairs Trading")

# --- Sidebar ---
st.sidebar.header("Pairs Settings")
asset_a = st.sidebar.text_input("Asset A", "AAPL")
asset_b = st.sidebar.text_input("Asset B", "MSFT")
lookback = st.sidebar.selectbox("Lookback", ["6 months", "1 year", "2 years"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Cointegration", "Spread", "Pair Selection", "Signals",
])

# --- Tab 1: Cointegration ---
with tab1:
    st.subheader("Cointegration Test")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", "Cointegrated")
    col2.metric("P-Value", "0.012")
    col3.metric("Hedge Ratio", "1.32")
    col4.metric("Correlation", "0.87")

    st.markdown("#### Test History")
    coint_data = pd.DataFrame([
        {"Date": "2026-01-31", "ADF Stat": -3.82, "P-Value": 0.012,
         "Hedge Ratio": 1.32, "Correlation": 0.87, "Status": "Cointegrated"},
        {"Date": "2026-01-24", "ADF Stat": -3.65, "P-Value": 0.018,
         "Hedge Ratio": 1.30, "Correlation": 0.86, "Status": "Cointegrated"},
        {"Date": "2026-01-17", "ADF Stat": -2.95, "P-Value": 0.042,
         "Hedge Ratio": 1.28, "Correlation": 0.85, "Status": "Cointegrated"},
        {"Date": "2026-01-10", "ADF Stat": -2.70, "P-Value": 0.065,
         "Hedge Ratio": 1.25, "Correlation": 0.84, "Status": "Weak"},
    ])
    st.dataframe(coint_data, use_container_width=True, hide_index=True)

# --- Tab 2: Spread ---
with tab2:
    st.subheader("Spread Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Z-Score", "1.85")
    col2.metric("Half-Life", "12.3 days")
    col3.metric("Hurst", "0.38")
    col4.metric("Signal", "No Signal")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Current Spread", "$2.45")
    col6.metric("Mean Spread", "$0.82")
    col7.metric("Spread Std", "$0.88")
    col8.metric("Mean-Reverting?", "Yes")

    st.markdown("#### Spread History")
    spread_data = pd.DataFrame([
        {"Date": "2026-01-31", "Spread": 2.45, "Z-Score": 1.85,
         "Signal": "No Signal", "Half-Life": 12.3},
        {"Date": "2026-01-30", "Spread": 2.20, "Z-Score": 1.57,
         "Signal": "No Signal", "Half-Life": 12.5},
        {"Date": "2026-01-29", "Spread": 2.80, "Z-Score": 2.25,
         "Signal": "Short Spread", "Half-Life": 11.8},
        {"Date": "2026-01-28", "Spread": 1.50, "Z-Score": 0.77,
         "Signal": "No Signal", "Half-Life": 12.1},
    ])
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 3: Pair Selection ---
with tab3:
    st.subheader("Top Pairs")

    st.markdown("#### Ranked Pairs")
    pairs_data = pd.DataFrame([
        {"Rank": 1, "Asset A": "AAPL", "Asset B": "MSFT", "Score": 82.5,
         "Coint Score": 90.0, "HL Score": 85.0, "Corr Score": 87.0, "Hurst Score": 70.0},
        {"Rank": 2, "Asset A": "KO", "Asset B": "PEP", "Score": 78.3,
         "Coint Score": 85.0, "HL Score": 80.0, "Corr Score": 82.0, "Hurst Score": 65.0},
        {"Rank": 3, "Asset A": "XOM", "Asset B": "CVX", "Score": 75.1,
         "Coint Score": 80.0, "HL Score": 75.0, "Corr Score": 78.0, "Hurst Score": 60.0},
        {"Rank": 4, "Asset A": "JPM", "Asset B": "BAC", "Score": 71.8,
         "Coint Score": 75.0, "HL Score": 70.0, "Corr Score": 75.0, "Hurst Score": 62.0},
        {"Rank": 5, "Asset A": "HD", "Asset B": "LOW", "Score": 68.2,
         "Coint Score": 70.0, "HL Score": 68.0, "Corr Score": 72.0, "Hurst Score": 55.0},
    ])
    st.dataframe(pairs_data, use_container_width=True, hide_index=True)

# --- Tab 4: Signals ---
with tab4:
    st.subheader("Active Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Entries", "2")
    col2.metric("Pending Exits", "1")
    col3.metric("Avg Confidence", "78%")
    col4.metric("Open P&L", "+$1,250")

    st.markdown("#### Current Signals")
    signal_data = pd.DataFrame([
        {"Pair": "AAPL/MSFT", "Signal": "Short Spread", "Z-Score": 2.25,
         "Hedge Ratio": 1.32, "Confidence": "85%", "Spread": "$2.80"},
        {"Pair": "KO/PEP", "Signal": "Long Spread", "Z-Score": -2.10,
         "Hedge Ratio": 0.95, "Confidence": "78%", "Spread": "-$1.50"},
        {"Pair": "XOM/CVX", "Signal": "Exit", "Z-Score": 0.35,
         "Hedge Ratio": 1.15, "Confidence": "80%", "Spread": "$0.20"},
    ])
    st.dataframe(signal_data, use_container_width=True, hide_index=True)
