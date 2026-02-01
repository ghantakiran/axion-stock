"""Liquidity Analysis Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Liquidity Analysis", layout="wide")
st.title("Liquidity Analysis")

# --- Sidebar ---
st.sidebar.header("Liquidity Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
window = st.sidebar.selectbox("Window", ["1 Week", "1 Month", "3 Months"], index=1)
trade_size = st.sidebar.number_input("Trade Size (shares)", value=10000, step=1000)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "Spread", "Impact", "Scoring",
])

# --- Tab 1: Overview ---
with tab1:
    st.subheader("Liquidity Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Liquidity Score", "87/100")
    col2.metric("Level", "Very High")
    col3.metric("Avg Spread", "0.02 (1.3 bps)")
    col4.metric("Avg Daily Volume", "52.3M")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Dollar Volume", "$7.8B")
    col6.metric("VWAP", "$150.23")
    col7.metric("Max Safe Size", "523,000 shares")
    col8.metric("Impact (10k)", "0.8 bps")

    st.markdown("#### Liquidity Summary")
    summary_data = pd.DataFrame([
        {"Metric": "Average Spread", "Value": "$0.02", "Assessment": "Excellent"},
        {"Metric": "Relative Spread", "Value": "1.3 bps", "Assessment": "Excellent"},
        {"Metric": "Avg Daily Volume", "Value": "52.3M shares", "Assessment": "Very High"},
        {"Metric": "Dollar Volume", "Value": "$7.8B/day", "Assessment": "Very High"},
        {"Metric": "Market Impact (10k)", "Value": "0.8 bps", "Assessment": "Minimal"},
        {"Metric": "Max Safe Size (10%)", "Value": "523,000 shares", "Assessment": "Large"},
    ])
    st.dataframe(summary_data, use_container_width=True, hide_index=True)

# --- Tab 2: Spread ---
with tab2:
    st.subheader("Spread Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Spread", "$0.02")
    col2.metric("Median Spread", "$0.01")
    col3.metric("Spread Vol", "$0.008")
    col4.metric("Effective Spread", "$0.02")

    st.markdown("#### Spread Statistics")
    spread_data = pd.DataFrame([
        {"Metric": "Average Absolute Spread", "Value": "$0.020"},
        {"Metric": "Median Absolute Spread", "Value": "$0.015"},
        {"Metric": "Spread Volatility", "Value": "$0.008"},
        {"Metric": "Relative Spread (bps)", "Value": "1.3"},
        {"Metric": "Effective Spread", "Value": "$0.018"},
        {"Metric": "Observations", "Value": "21"},
    ])
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 3: Impact ---
with tab3:
    st.subheader("Market Impact Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trade Size", "10,000 shares")
    col2.metric("Participation Rate", "0.02%")
    col3.metric("Total Cost", "0.8 bps")
    col4.metric("Execution Days", "1")

    st.markdown("#### Impact Breakdown")
    impact_data = pd.DataFrame([
        {"Component": "Spread Cost", "Value": "0.7 bps", "Fraction": "85%"},
        {"Component": "Impact Cost", "Value": "0.1 bps", "Fraction": "15%"},
        {"Component": "Total Cost", "Value": "0.8 bps", "Fraction": "100%"},
    ])
    st.dataframe(impact_data, use_container_width=True, hide_index=True)

    st.markdown("#### Size Sensitivity")
    size_data = pd.DataFrame([
        {"Trade Size": "1,000", "Participation": "0.002%", "Impact (bps)": 0.3, "Days": 1},
        {"Trade Size": "10,000", "Participation": "0.019%", "Impact (bps)": 0.8, "Days": 1},
        {"Trade Size": "100,000", "Participation": "0.191%", "Impact (bps)": 2.5, "Days": 1},
        {"Trade Size": "500,000", "Participation": "0.956%", "Impact (bps)": 5.6, "Days": 1},
        {"Trade Size": "1,000,000", "Participation": "1.913%", "Impact (bps)": 7.9, "Days": 2},
        {"Trade Size": "5,000,000", "Participation": "9.564%", "Impact (bps)": 17.8, "Days": 10},
    ])
    st.dataframe(size_data, use_container_width=True, hide_index=True)

# --- Tab 4: Scoring ---
with tab4:
    st.subheader("Liquidity Scoring")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite Score", "87/100")
    col2.metric("Spread Score", "95/100")
    col3.metric("Volume Score", "90/100")
    col4.metric("Impact Score", "82/100")

    st.markdown("#### Universe Ranking")
    ranking_data = pd.DataFrame([
        {"Rank": 1, "Symbol": "SPY", "Score": 98, "Level": "Very High", "Spread (bps)": 0.3},
        {"Rank": 2, "Symbol": "AAPL", "Score": 87, "Level": "Very High", "Spread (bps)": 1.3},
        {"Rank": 3, "Symbol": "MSFT", "Score": 86, "Level": "Very High", "Spread (bps)": 1.5},
        {"Rank": 4, "Symbol": "GOOGL", "Score": 84, "Level": "Very High", "Spread (bps)": 2.0},
        {"Rank": 5, "Symbol": "TSLA", "Score": 82, "Level": "Very High", "Spread (bps)": 2.5},
        {"Rank": 6, "Symbol": "NVDA", "Score": 80, "Level": "Very High", "Spread (bps)": 2.8},
        {"Rank": 7, "Symbol": "JPM", "Score": 78, "Level": "High", "Spread (bps)": 3.0},
        {"Rank": 8, "Symbol": "META", "Score": 75, "Level": "High", "Spread (bps)": 3.5},
    ])
    st.dataframe(ranking_data, use_container_width=True, hide_index=True)
