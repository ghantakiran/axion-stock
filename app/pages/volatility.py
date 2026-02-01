"""Volatility Analysis Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Volatility Analysis", layout="wide")
st.title("Volatility Analysis")

# --- Sidebar ---
st.sidebar.header("Volatility Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
method = st.sidebar.selectbox("Method", ["Historical", "EWMA", "Parkinson", "Garman-Klass"])
window = st.sidebar.selectbox("Window", ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview", "Surface", "Term Structure", "Regime",
])

# --- Tab 1: Overview ---
with tab1:
    st.subheader("Volatility Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Historical Vol (21d)", "18.5%")
    col2.metric("EWMA Vol", "19.2%")
    col3.metric("Parkinson Vol", "17.8%")
    col4.metric("Garman-Klass Vol", "18.1%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Percentile", "42nd")
    col6.metric("IV (30d)", "22.3%")
    col7.metric("Vol Risk Premium", "3.8%")
    col8.metric("Regime", "Normal")

    st.markdown("#### Volatility Cone")
    cone_data = pd.DataFrame({
        "Window": ["1W", "2W", "1M", "2M", "3M", "6M", "1Y"],
        "5th": [10.2, 11.5, 12.8, 13.5, 14.0, 14.8, 15.2],
        "25th": [14.5, 15.2, 15.8, 16.2, 16.5, 16.8, 17.0],
        "50th": [18.0, 18.5, 19.0, 19.2, 19.5, 19.8, 20.0],
        "75th": [22.5, 22.0, 21.5, 21.2, 21.0, 20.8, 20.5],
        "95th": [30.5, 28.8, 27.2, 26.0, 25.5, 24.8, 24.0],
        "Current": [18.5, 17.8, 18.5, 19.0, 18.8, 19.2, 19.5],
    })
    st.dataframe(cone_data, use_container_width=True, hide_index=True)

# --- Tab 2: Surface ---
with tab2:
    st.subheader("Volatility Surface")

    col1, col2, col3 = st.columns(3)
    col1.metric("ATM Vol (30d)", "22.3%")
    col2.metric("25d Skew", "-3.2%")
    col3.metric("25d Butterfly", "1.8%")

    st.markdown("#### Smile (30-Day)")
    smile_data = pd.DataFrame({
        "Moneyness": [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15],
        "Strike": [170.0, 180.0, 190.0, 200.0, 210.0, 220.0, 230.0],
        "IV": [0.298, 0.265, 0.235, 0.223, 0.232, 0.248, 0.270],
    })
    st.dataframe(smile_data, use_container_width=True, hide_index=True)

    st.markdown("#### ATM Term Structure")
    ts_data = pd.DataFrame({
        "Tenor": ["1W", "2W", "1M", "2M", "3M", "6M"],
        "ATM IV": [0.245, 0.235, 0.223, 0.228, 0.232, 0.240],
        "Realized": [0.185, 0.190, 0.185, 0.188, 0.192, 0.195],
        "VRP": [0.060, 0.045, 0.038, 0.040, 0.040, 0.045],
    })
    st.dataframe(ts_data, use_container_width=True, hide_index=True)

# --- Tab 3: Term Structure ---
with tab3:
    st.subheader("Realized Vol Term Structure")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Shape", "Contango")
    col2.metric("Slope", "+0.02%/day")
    col3.metric("Short-Term Vol", "18.5%")
    col4.metric("Long-Term Vol", "19.5%")

    st.markdown("#### Multi-Window Realized Vol")
    rv_data = pd.DataFrame({
        "Window": ["5d", "10d", "21d", "42d", "63d", "126d", "252d"],
        "Realized Vol": ["18.5%", "17.8%", "18.5%", "19.0%", "18.8%", "19.2%", "19.5%"],
        "Percentile": ["42%", "38%", "42%", "48%", "45%", "50%", "52%"],
        "vs 1Y Avg": ["-1.0%", "-1.7%", "-1.0%", "-0.5%", "-0.7%", "-0.3%", "0.0%"],
    })
    st.dataframe(rv_data, use_container_width=True, hide_index=True)

    st.markdown("#### IV vs RV Spread")
    spread_data = pd.DataFrame({
        "Tenor": ["1M", "2M", "3M", "6M"],
        "Implied Vol": ["22.3%", "22.8%", "23.2%", "24.0%"],
        "Realized Vol": ["18.5%", "19.0%", "18.8%", "19.2%"],
        "Spread": ["3.8%", "3.8%", "4.4%", "4.8%"],
        "Assessment": ["Normal", "Normal", "Elevated", "Elevated"],
    })
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 4: Regime ---
with tab4:
    st.subheader("Volatility Regime")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Regime", "Normal")
    col2.metric("Z-Score", "0.15")
    col3.metric("Percentile", "42nd")
    col4.metric("Days in Regime", "28")

    st.markdown("#### Regime History")
    regime_data = pd.DataFrame([
        {"Date": "2026-01-31", "Regime": "Normal", "Vol": "18.5%",
         "Z-Score": 0.15, "Percentile": "42%", "Changed": "No"},
        {"Date": "2026-01-03", "Regime": "Normal", "Vol": "17.2%",
         "Z-Score": -0.10, "Percentile": "38%", "Changed": "Yes"},
        {"Date": "2025-12-15", "Regime": "High", "Vol": "28.5%",
         "Z-Score": 1.85, "Percentile": "88%", "Changed": "Yes"},
        {"Date": "2025-11-01", "Regime": "Normal", "Vol": "19.0%",
         "Z-Score": 0.25, "Percentile": "52%", "Changed": "No"},
    ])
    st.dataframe(regime_data, use_container_width=True, hide_index=True)

    st.markdown("#### Regime Distribution (1Y)")
    dist_data = pd.DataFrame([
        {"Regime": "Low", "Fraction": "18%", "Days": "~45"},
        {"Regime": "Normal", "Fraction": "58%", "Days": "~146"},
        {"Regime": "High", "Fraction": "20%", "Days": "~50"},
        {"Regime": "Extreme", "Fraction": "4%", "Days": "~11"},
    ])
    st.dataframe(dist_data, use_container_width=True, hide_index=True)
