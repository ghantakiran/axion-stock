"""Correlation Matrix Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Correlation Matrix", layout="wide")
st.title("Correlation Matrix")

# --- Sidebar ---
st.sidebar.header("Correlation Analysis")
method = st.sidebar.selectbox("Method", ["Pearson", "Spearman", "Kendall"])
window = st.sidebar.selectbox("Window", ["1 Month", "3 Months", "6 Months", "1 Year"], index=1)
symbols_input = st.sidebar.text_input("Symbols", "AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA, JPM")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Matrix", "Pairs", "Regime", "Diversification",
])

# --- Tab 1: Matrix ---
with tab1:
    st.subheader("Correlation Matrix")

    matrix_data = pd.DataFrame({
        "": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM"],
        "AAPL": [1.00, 0.72, 0.68, 0.65, 0.58, 0.42, 0.71, 0.35],
        "MSFT": [0.72, 1.00, 0.75, 0.70, 0.62, 0.38, 0.78, 0.40],
        "GOOGL": [0.68, 0.75, 1.00, 0.72, 0.65, 0.35, 0.70, 0.38],
        "AMZN": [0.65, 0.70, 0.72, 1.00, 0.60, 0.40, 0.68, 0.32],
        "META": [0.58, 0.62, 0.65, 0.60, 1.00, 0.45, 0.60, 0.28],
        "TSLA": [0.42, 0.38, 0.35, 0.40, 0.45, 1.00, 0.48, 0.15],
        "NVDA": [0.71, 0.78, 0.70, 0.68, 0.60, 0.48, 1.00, 0.30],
        "JPM": [0.35, 0.40, 0.38, 0.32, 0.28, 0.15, 0.30, 1.00],
    })
    st.dataframe(matrix_data, use_container_width=True, hide_index=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Correlation", "0.52")
    col2.metric("Max Pair", "MSFT-NVDA (0.78)")
    col3.metric("Min Pair", "TSLA-JPM (0.15)")

# --- Tab 2: Pairs ---
with tab2:
    st.subheader("Pair Analysis")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Most Correlated Pairs")
        top_pairs = pd.DataFrame([
            {"Pair": "MSFT - NVDA", "Correlation": 0.78, "Stability": "High"},
            {"Pair": "GOOGL - AMZN", "Correlation": 0.72, "Stability": "High"},
            {"Pair": "AAPL - MSFT", "Correlation": 0.72, "Stability": "High"},
            {"Pair": "AAPL - NVDA", "Correlation": 0.71, "Stability": "Medium"},
            {"Pair": "MSFT - GOOGL", "Correlation": 0.75, "Stability": "High"},
        ])
        st.dataframe(top_pairs, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Least Correlated Pairs")
        bottom_pairs = pd.DataFrame([
            {"Pair": "TSLA - JPM", "Correlation": 0.15, "Stability": "Low"},
            {"Pair": "META - JPM", "Correlation": 0.28, "Stability": "Medium"},
            {"Pair": "NVDA - JPM", "Correlation": 0.30, "Stability": "Medium"},
            {"Pair": "AMZN - JPM", "Correlation": 0.32, "Stability": "Medium"},
            {"Pair": "GOOGL - TSLA", "Correlation": 0.35, "Stability": "Low"},
        ])
        st.dataframe(bottom_pairs, use_container_width=True, hide_index=True)

    st.markdown("#### Highly Correlated (> 0.70)")
    high_corr = pd.DataFrame([
        {"Pair": "MSFT - NVDA", "Correlation": 0.78, "Risk": "Concentration"},
        {"Pair": "MSFT - GOOGL", "Correlation": 0.75, "Risk": "Concentration"},
        {"Pair": "AAPL - MSFT", "Correlation": 0.72, "Risk": "Concentration"},
        {"Pair": "GOOGL - AMZN", "Correlation": 0.72, "Risk": "Concentration"},
        {"Pair": "AAPL - NVDA", "Correlation": 0.71, "Risk": "Moderate"},
    ])
    st.dataframe(high_corr, use_container_width=True, hide_index=True)

# --- Tab 3: Regime ---
with tab3:
    st.subheader("Correlation Regime")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Regime", "Normal")
    col2.metric("Avg Correlation", "0.52")
    col3.metric("Dispersion", "0.18")
    col4.metric("Days in Regime", "34")

    st.markdown("#### Regime History")
    regime_data = pd.DataFrame([
        {"Date": "2026-01-31", "Regime": "Normal", "Avg Corr": 0.52,
         "Dispersion": 0.18, "Changed": "No"},
        {"Date": "2025-12-28", "Regime": "Normal", "Avg Corr": 0.48,
         "Dispersion": 0.20, "Changed": "Yes"},
        {"Date": "2025-12-01", "Regime": "High", "Avg Corr": 0.58,
         "Dispersion": 0.12, "Changed": "Yes"},
        {"Date": "2025-10-15", "Regime": "Normal", "Avg Corr": 0.45,
         "Dispersion": 0.22, "Changed": "No"},
    ])
    st.dataframe(regime_data, use_container_width=True, hide_index=True)

# --- Tab 4: Diversification ---
with tab4:
    st.subheader("Portfolio Diversification")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Diversification Ratio", "1.35")
    col2.metric("Effective Bets", "4.2")
    col3.metric("Level", "Good")
    col4.metric("Assets", "8")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Avg Pair Correlation", "0.52")
    col6.metric("Max Pair Correlation", "0.78")
    col7.metric("Max Pair", "MSFT-NVDA")
    col8.metric("Highly Correlated Pairs", "5")

    st.markdown("#### Diversification Breakdown")
    div_data = pd.DataFrame([
        {"Metric": "Diversification Ratio", "Value": "1.35", "Assessment": "Good"},
        {"Metric": "Effective Number of Bets", "Value": "4.2 / 8", "Assessment": "Moderate"},
        {"Metric": "Avg Pairwise Correlation", "Value": "0.52", "Assessment": "Normal"},
        {"Metric": "Max Pairwise Correlation", "Value": "0.78", "Assessment": "Concentration Risk"},
        {"Metric": "Highly Correlated Pairs", "Value": "5 of 28", "Assessment": "Watch"},
    ])
    st.dataframe(div_data, use_container_width=True, hide_index=True)
