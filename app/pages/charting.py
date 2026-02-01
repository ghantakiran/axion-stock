"""Technical Charting Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Technical Charting", layout="wide")
st.title("Technical Charting")

# --- Sidebar ---
st.sidebar.header("Chart Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
timeframe = st.sidebar.selectbox("Timeframe", ["Daily", "Weekly", "Monthly"], index=0)
lookback = st.sidebar.selectbox("Lookback", ["3 Months", "6 Months", "1 Year", "2 Years"], index=2)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Patterns", "Trends", "Support/Resistance", "Fibonacci",
])

# --- Tab 1: Patterns ---
with tab1:
    st.subheader("Chart Patterns")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Patterns Found", "3")
    col2.metric("Strongest Signal", "Double Bottom")
    col3.metric("Confidence", "78%")
    col4.metric("Direction", "Bullish")

    st.markdown("#### Detected Patterns")
    pattern_data = pd.DataFrame([
        {"Pattern": "Double Bottom", "Confidence": "78%", "Target": "$158.50",
         "Neckline": "$152.00", "Status": "Confirmed", "Bias": "Bullish"},
        {"Pattern": "Ascending Triangle", "Confidence": "65%", "Target": "$162.00",
         "Neckline": "$155.00", "Status": "Forming", "Bias": "Bullish"},
        {"Pattern": "Flag", "Confidence": "55%", "Target": "$160.00",
         "Neckline": "$150.00", "Status": "Forming", "Bias": "Bullish"},
    ])
    st.dataframe(pattern_data, use_container_width=True, hide_index=True)

# --- Tab 2: Trends ---
with tab2:
    st.subheader("Trend Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Direction", "Uptrend")
    col2.metric("Strength", "72/100")
    col3.metric("R-Squared", "0.68")
    col4.metric("Slope", "+0.15%/day")

    col5, col6, col7 = st.columns(3)
    col5.metric("MA (20)", "$148.50")
    col6.metric("MA (50)", "$145.20")
    col7.metric("MA (200)", "$138.75")

    st.markdown("#### Moving Average Alignment: Bullish (Short > Medium > Long)")

    st.markdown("#### Recent Crossovers")
    cross_data = pd.DataFrame([
        {"Date": "2026-01-15", "Type": "Golden Cross", "Fast": "20-day",
         "Slow": "50-day", "Price": "$147.25"},
        {"Date": "2025-11-20", "Type": "Death Cross", "Fast": "20-day",
         "Slow": "50-day", "Price": "$135.80"},
    ])
    st.dataframe(cross_data, use_container_width=True, hide_index=True)

# --- Tab 3: Support/Resistance ---
with tab3:
    st.subheader("Support & Resistance Levels")

    st.markdown("#### Key Levels")
    sr_data = pd.DataFrame([
        {"Type": "Resistance", "Price": "$155.00", "Touches": 4,
         "Strength": "0.85", "Status": "Strong"},
        {"Type": "Resistance", "Price": "$160.50", "Touches": 2,
         "Strength": "0.62", "Status": "Moderate"},
        {"Type": "Support", "Price": "$145.00", "Touches": 5,
         "Strength": "0.92", "Status": "Strong"},
        {"Type": "Support", "Price": "$140.25", "Touches": 3,
         "Strength": "0.75", "Status": "Strong"},
        {"Type": "Support", "Price": "$135.00", "Touches": 2,
         "Strength": "0.55", "Status": "Moderate"},
    ])
    st.dataframe(sr_data, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Nearest Support", "$145.00 (-2.3%)")
    col2.metric("Nearest Resistance", "$155.00 (+4.4%)")
    col3.metric("Risk/Reward", "1:1.9")

# --- Tab 4: Fibonacci ---
with tab4:
    st.subheader("Fibonacci Levels")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Swing High", "$158.50")
    col2.metric("Swing Low", "$130.00")
    col3.metric("Range", "$28.50")
    col4.metric("Trend", "Uptrend")

    st.markdown("#### Retracement Levels")
    ret_data = pd.DataFrame([
        {"Level": "23.6%", "Price": "$151.78", "Status": "Above"},
        {"Level": "38.2%", "Price": "$147.61", "Status": "Near"},
        {"Level": "50.0%", "Price": "$144.25", "Status": "Below"},
        {"Level": "61.8%", "Price": "$140.89", "Status": "Below"},
        {"Level": "78.6%", "Price": "$136.10", "Status": "Below"},
    ])
    st.dataframe(ret_data, use_container_width=True, hide_index=True)

    st.markdown("#### Extension Levels")
    ext_data = pd.DataFrame([
        {"Level": "100.0%", "Price": "$158.50", "Status": "At Swing High"},
        {"Level": "127.2%", "Price": "$166.25", "Status": "Target 1"},
        {"Level": "161.8%", "Price": "$176.11", "Status": "Target 2"},
        {"Level": "200.0%", "Price": "$187.00", "Status": "Target 3"},
        {"Level": "261.8%", "Price": "$204.61", "Status": "Target 4"},
    ])
    st.dataframe(ext_data, use_container_width=True, hide_index=True)
