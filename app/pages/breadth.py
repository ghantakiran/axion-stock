"""Market Breadth Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Market Breadth", layout="wide")
st.title("Market Breadth")

# --- Sidebar ---
st.sidebar.header("Market Breadth")
market = st.sidebar.selectbox("Market", ["NYSE + NASDAQ", "NYSE", "NASDAQ", "S&P 500"])
timeframe = st.sidebar.selectbox("Timeframe", ["Daily", "Weekly", "Monthly"])

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "McClellan", "Sector Breadth", "Signals",
])

# --- Tab 1: Overview ---
with tab1:
    st.subheader("Market Breadth Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Market Health", "72 / 100", "+5")
    col2.metric("Health Level", "Bullish")
    col3.metric("AD Ratio", "1.65")
    col4.metric("Net Advances", "+920")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Advancing", "2,200")
    col6.metric("Declining", "1,300")
    col7.metric("New Highs", "85")
    col8.metric("New Lows", "12")

    st.markdown("#### Cumulative AD Line")
    ad_data = pd.DataFrame([
        {"Date": "2026-01-27", "AD Line": 12450},
        {"Date": "2026-01-28", "AD Line": 13100},
        {"Date": "2026-01-29", "AD Line": 13850},
        {"Date": "2026-01-30", "AD Line": 14200},
        {"Date": "2026-01-31", "AD Line": 15120},
    ])
    st.dataframe(ad_data, use_container_width=True, hide_index=True)

    st.markdown("#### New Highs vs New Lows")
    nhnl_data = pd.DataFrame([
        {"Date": "2026-01-27", "New Highs": 72, "New Lows": 18, "Net": 54},
        {"Date": "2026-01-28", "New Highs": 68, "New Lows": 22, "Net": 46},
        {"Date": "2026-01-29", "New Highs": 91, "New Lows": 14, "Net": 77},
        {"Date": "2026-01-30", "New Highs": 78, "New Lows": 16, "Net": 62},
        {"Date": "2026-01-31", "New Highs": 85, "New Lows": 12, "Net": 73},
    ])
    st.dataframe(nhnl_data, use_container_width=True, hide_index=True)

# --- Tab 2: McClellan ---
with tab2:
    st.subheader("McClellan Oscillator & Summation Index")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Oscillator", "+62.4")
    col2.metric("Summation Index", "+1,245")
    col3.metric("19-EMA", "+185.2")
    col4.metric("39-EMA", "+122.8")

    st.markdown("#### McClellan History")
    mc_data = pd.DataFrame([
        {"Date": "2026-01-27", "Oscillator": 45.2, "Summation": 1120, "Signal": "—"},
        {"Date": "2026-01-28", "Oscillator": 38.1, "Summation": 1158, "Signal": "—"},
        {"Date": "2026-01-29", "Oscillator": 72.5, "Summation": 1231, "Signal": "—"},
        {"Date": "2026-01-30", "Oscillator": 55.8, "Summation": 1187, "Signal": "—"},
        {"Date": "2026-01-31", "Oscillator": 62.4, "Summation": 1245, "Signal": "—"},
    ])
    st.dataframe(mc_data, use_container_width=True, hide_index=True)

    st.markdown("#### Breadth Thrust")
    col5, col6, col7 = st.columns(3)
    col5.metric("Thrust EMA", "0.612")
    col6.metric("Last Thrust", "2025-11-05")
    col7.metric("Days Since Thrust", "87")

# --- Tab 3: Sector Breadth ---
with tab3:
    st.subheader("Sector Breadth Breakdown")

    sector_data = pd.DataFrame([
        {"Sector": "Technology", "Advancing": 42, "Declining": 8, "Score": 84.0,
         "Momentum": "Improving", "Rank": 1},
        {"Sector": "Healthcare", "Advancing": 35, "Declining": 15, "Score": 70.0,
         "Momentum": "Flat", "Rank": 2},
        {"Sector": "Energy", "Advancing": 28, "Declining": 12, "Score": 70.0,
         "Momentum": "Improving", "Rank": 3},
        {"Sector": "Industrials", "Advancing": 30, "Declining": 18, "Score": 62.5,
         "Momentum": "Flat", "Rank": 4},
        {"Sector": "Consumer Disc.", "Advancing": 22, "Declining": 18, "Score": 55.0,
         "Momentum": "Deteriorating", "Rank": 5},
        {"Sector": "Communication", "Advancing": 12, "Declining": 10, "Score": 54.5,
         "Momentum": "Flat", "Rank": 6},
        {"Sector": "Financials", "Advancing": 25, "Declining": 25, "Score": 50.0,
         "Momentum": "Flat", "Rank": 7},
        {"Sector": "Materials", "Advancing": 8, "Declining": 12, "Score": 40.0,
         "Momentum": "Deteriorating", "Rank": 8},
        {"Sector": "Consumer Staples", "Advancing": 10, "Declining": 20, "Score": 33.3,
         "Momentum": "Deteriorating", "Rank": 9},
        {"Sector": "Utilities", "Advancing": 8, "Declining": 18, "Score": 30.8,
         "Momentum": "Flat", "Rank": 10},
        {"Sector": "Real Estate", "Advancing": 5, "Declining": 20, "Score": 20.0,
         "Momentum": "Deteriorating", "Rank": 11},
    ])
    st.dataframe(sector_data, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Strongest Sectors")
        st.write("1. Technology (84.0) - Improving")
        st.write("2. Healthcare (70.0) - Flat")
        st.write("3. Energy (70.0) - Improving")
    with col2:
        st.markdown("#### Weakest Sectors")
        st.write("1. Real Estate (20.0) - Deteriorating")
        st.write("2. Utilities (30.8) - Flat")
        st.write("3. Consumer Staples (33.3) - Deteriorating")

# --- Tab 4: Signals ---
with tab4:
    st.subheader("Breadth Signals")

    signals_data = pd.DataFrame([
        {"Date": "2026-01-31", "Signal": "Zero Cross Up", "Indicator": "McClellan",
         "Value": "+62.4", "Interpretation": "Bullish momentum confirmation"},
        {"Date": "2026-01-29", "Signal": "New High Pole", "Indicator": "NH/NL",
         "Value": "91", "Interpretation": "Strong new high expansion"},
        {"Date": "2026-01-22", "Signal": "Breadth Thrust", "Indicator": "Thrust",
         "Value": "0.635", "Interpretation": "Rare bullish thrust signal"},
        {"Date": "2026-01-15", "Signal": "Oversold", "Indicator": "McClellan",
         "Value": "-112", "Interpretation": "Market oversold, bounce likely"},
    ])
    st.dataframe(signals_data, use_container_width=True, hide_index=True)

    st.markdown("#### Component Scores")
    scores_data = pd.DataFrame([
        {"Component": "Advance/Decline", "Score": 74.5, "Weight": "25%", "Weighted": 18.6},
        {"Component": "New Highs/Lows", "Score": 87.7, "Weight": "20%", "Weighted": 17.5},
        {"Component": "McClellan", "Score": 70.8, "Weight": "25%", "Weighted": 17.7},
        {"Component": "Breadth Thrust", "Score": 58.0, "Weight": "15%", "Weighted": 8.7},
        {"Component": "Volume", "Score": 63.3, "Weight": "15%", "Weighted": 9.5},
        {"Component": "Composite", "Score": 72.0, "Weight": "100%", "Weighted": 72.0},
    ])
    st.dataframe(scores_data, use_container_width=True, hide_index=True)
