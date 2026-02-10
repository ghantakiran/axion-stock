"""Options Chain Analysis Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Options Chain Analysis", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Options Chain Analysis")

# --- Sidebar ---
st.sidebar.header("Chain Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
expiry = st.sidebar.selectbox("Expiry", ["Feb 7, 2026", "Feb 14, 2026", "Feb 21, 2026", "Mar 21, 2026"])

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Chain Overview", "Greeks", "Flow", "Unusual Activity",
])

# --- Tab 1: Chain Overview ---
with tab1:
    st.subheader("Chain Summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PCR (Volume)", "0.85")
    col2.metric("PCR (OI)", "0.92")
    col3.metric("Max Pain", "$150.00")
    col4.metric("IV Skew", "+0.032")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("ATM IV", "28.5%")
    col6.metric("Call Volume", "45,200")
    col7.metric("Put Volume", "38,400")
    col8.metric("Sentiment", "Neutral")

    st.markdown("#### Options Chain")
    chain_data = pd.DataFrame([
        {"Strike": 145, "Call Bid": 6.80, "Call Ask": 7.10, "Call Vol": 1200,
         "Call OI": 8500, "Put Bid": 1.20, "Put Ask": 1.40, "Put Vol": 800, "Put OI": 5200},
        {"Strike": 147.5, "Call Bid": 4.90, "Call Ask": 5.20, "Call Vol": 2100,
         "Call OI": 12000, "Put Bid": 2.10, "Put Ask": 2.30, "Put Vol": 1500, "Put OI": 7800},
        {"Strike": 150, "Call Bid": 3.20, "Call Ask": 3.50, "Call Vol": 5400,
         "Call OI": 18500, "Put Bid": 3.40, "Put Ask": 3.60, "Put Vol": 4800, "Put OI": 15200},
        {"Strike": 152.5, "Call Bid": 1.80, "Call Ask": 2.10, "Call Vol": 3200,
         "Call OI": 14000, "Put Bid": 5.50, "Put Ask": 5.80, "Put Vol": 2200, "Put OI": 9500},
        {"Strike": 155, "Call Bid": 0.80, "Call Ask": 1.00, "Call Vol": 1800,
         "Call OI": 9200, "Put Bid": 7.90, "Put Ask": 8.20, "Put Vol": 900, "Put OI": 6100},
    ])
    st.dataframe(chain_data, use_container_width=True, hide_index=True)

# --- Tab 2: Greeks ---
with tab2:
    st.subheader("Greeks Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ATM Delta", "0.52")
    col2.metric("ATM Gamma", "0.035")
    col3.metric("ATM Theta", "-$0.08")
    col4.metric("ATM Vega", "$0.18")

    st.markdown("#### Greeks by Strike")
    greeks_data = pd.DataFrame([
        {"Strike": 145, "Call Delta": 0.82, "Call Gamma": 0.018, "Call Theta": -0.04,
         "Put Delta": -0.18, "Put Gamma": 0.018, "Put Theta": -0.03, "IV": "26.2%"},
        {"Strike": 147.5, "Call Delta": 0.70, "Call Gamma": 0.025, "Call Theta": -0.06,
         "Put Delta": -0.30, "Put Gamma": 0.025, "Put Theta": -0.05, "IV": "27.1%"},
        {"Strike": 150, "Call Delta": 0.52, "Call Gamma": 0.035, "Call Theta": -0.08,
         "Put Delta": -0.48, "Put Gamma": 0.035, "Put Theta": -0.07, "IV": "28.5%"},
        {"Strike": 152.5, "Call Delta": 0.35, "Call Gamma": 0.030, "Call Theta": -0.07,
         "Put Delta": -0.65, "Put Gamma": 0.030, "Put Theta": -0.06, "IV": "29.8%"},
        {"Strike": 155, "Call Delta": 0.20, "Call Gamma": 0.022, "Call Theta": -0.05,
         "Put Delta": -0.80, "Put Gamma": 0.022, "Put Theta": -0.04, "IV": "31.2%"},
    ])
    st.dataframe(greeks_data, use_container_width=True, hide_index=True)

# --- Tab 3: Flow ---
with tab3:
    st.subheader("Options Flow")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net Sentiment", "Bullish")
    col2.metric("Bullish Premium", "$2.8M")
    col3.metric("Bearish Premium", "$1.4M")
    col4.metric("Sweeps Today", "8")

    st.markdown("#### Recent Flow")
    flow_data = pd.DataFrame([
        {"Time": "14:30", "Type": "Sweep", "Side": "Buy", "Option": "Call 150",
         "Size": 500, "Premium": "$250K", "Sentiment": "Bullish"},
        {"Time": "14:15", "Type": "Block", "Side": "Buy", "Option": "Put 145",
         "Size": 300, "Premium": "$42K", "Sentiment": "Bearish"},
        {"Time": "13:45", "Type": "Sweep", "Side": "Sell", "Option": "Put 148",
         "Size": 200, "Premium": "$56K", "Sentiment": "Bullish"},
        {"Time": "13:20", "Type": "Block", "Side": "Buy", "Option": "Call 155",
         "Size": 150, "Premium": "$15K", "Sentiment": "Bullish"},
        {"Time": "12:50", "Type": "Normal", "Side": "Buy", "Option": "Put 150",
         "Size": 80, "Premium": "$27K", "Sentiment": "Bearish"},
    ])
    st.dataframe(flow_data, use_container_width=True, hide_index=True)

# --- Tab 4: Unusual Activity ---
with tab4:
    st.subheader("Unusual Options Activity")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Alerts", "5")
    col2.metric("Extreme", "1")
    col3.metric("Unusual", "2")
    col4.metric("Elevated", "2")

    st.markdown("#### Flagged Activity")
    unusual_data = pd.DataFrame([
        {"Strike": 155, "Type": "Call", "Volume": 2800, "OI": 450,
         "Vol/OI": 6.22, "Premium": "$280K", "Level": "Extreme", "Score": 78.5},
        {"Strike": 150, "Type": "Put", "Volume": 1500, "OI": 600,
         "Vol/OI": 2.50, "Premium": "$510K", "Level": "Unusual", "Score": 62.3},
        {"Strike": 147.5, "Type": "Call", "Volume": 900, "OI": 350,
         "Vol/OI": 2.57, "Premium": "$468K", "Level": "Unusual", "Score": 55.1},
        {"Strike": 152.5, "Type": "Put", "Volume": 600, "OI": 380,
         "Vol/OI": 1.58, "Premium": "$348K", "Level": "Elevated", "Score": 38.7},
        {"Strike": 145, "Type": "Call", "Volume": 450, "OI": 280,
         "Vol/OI": 1.61, "Premium": "$306K", "Level": "Elevated", "Score": 35.2},
    ])
    st.dataframe(unusual_data, use_container_width=True, hide_index=True)
