"""Credit Risk Analysis Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Credit Risk", layout="wide")
st.title("Credit Risk Analysis")

# --- Sidebar ---
st.sidebar.header("Credit Settings")
symbol = st.sidebar.text_input("Symbol", "XYZ")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Credit Spreads", "Default Probability", "Rating Migration", "Debt Structure",
])

# --- Tab 1: Credit Spreads ---
with tab1:
    st.subheader("Credit Spread Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Spread", "185 bps")
    col2.metric("Z-Score", "+1.2")
    col3.metric("Percentile", "82%")
    col4.metric("Trend", "Widening")

    st.markdown("#### Spread Term Structure")
    ts_data = pd.DataFrame([
        {"Term": "1Y", "Spread (bps)": 95, "Z-Score": 0.8},
        {"Term": "2Y", "Spread (bps)": 120, "Z-Score": 0.9},
        {"Term": "5Y", "Spread (bps)": 185, "Z-Score": 1.2},
        {"Term": "10Y", "Spread (bps)": 210, "Z-Score": 1.0},
        {"Term": "30Y", "Spread (bps)": 240, "Z-Score": 0.7},
    ])
    st.dataframe(ts_data, use_container_width=True, hide_index=True)

    st.markdown("#### Relative Value")
    rv_data = pd.DataFrame([
        {"Issuer": "XYZ", "Spread": "185 bps", "Avg": "150 bps", "Z-Score": 1.2, "Rich/Cheap": "Cheap"},
        {"Issuer": "ABC", "Spread": "120 bps", "Avg": "130 bps", "Z-Score": -0.5, "Rich/Cheap": "Rich"},
        {"Issuer": "DEF", "Spread": "200 bps", "Avg": "195 bps", "Z-Score": 0.3, "Rich/Cheap": "Fair"},
    ])
    st.dataframe(rv_data, use_container_width=True, hide_index=True)

# --- Tab 2: Default Probability ---
with tab2:
    st.subheader("Default Probability Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PD (1Y)", "1.2%")
    col2.metric("PD (5Y)", "5.8%")
    col3.metric("Distance to Default", "3.2")
    col4.metric("Expected Loss", "0.7%")

    st.markdown("#### Model Comparison")
    model_data = pd.DataFrame([
        {"Model": "Merton Structural", "PD (1Y)": "1.2%", "PD (5Y)": "5.8%", "DD": 3.2},
        {"Model": "CDS-Implied", "PD (1Y)": "1.5%", "PD (5Y)": "7.2%", "DD": "—"},
        {"Model": "Statistical (Z-Score)", "PD (1Y)": "0.8%", "PD (5Y)": "3.9%", "DD": 4.1},
    ])
    st.dataframe(model_data, use_container_width=True, hide_index=True)

# --- Tab 3: Rating Migration ---
with tab3:
    st.subheader("Credit Rating Migration")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Rating", "BBB")
    col2.metric("Outlook", "Negative")
    col3.metric("Momentum", "-0.5")
    col4.metric("Direction", "Downgrade Risk")

    st.markdown("#### Rating History")
    rating_data = pd.DataFrame([
        {"Date": "2025-01", "Rating": "BBB", "Outlook": "Negative", "Direction": "Downgrade"},
        {"Date": "2024-06", "Rating": "BBB+", "Outlook": "Stable", "Direction": "—"},
        {"Date": "2023-01", "Rating": "A-", "Outlook": "Negative", "Direction": "Downgrade"},
        {"Date": "2022-01", "Rating": "A", "Outlook": "Stable", "Direction": "—"},
    ])
    st.dataframe(rating_data, use_container_width=True, hide_index=True)

    st.markdown("#### Watchlist (Negative Outlook)")
    watch_data = pd.DataFrame([
        {"Symbol": "XYZ", "Rating": "BBB", "Outlook": "Negative", "Momentum": "-0.5"},
        {"Symbol": "RST", "Rating": "BB", "Outlook": "Watch", "Momentum": "-1.0"},
        {"Symbol": "UVW", "Rating": "B", "Outlook": "Negative", "Momentum": "-0.3"},
    ])
    st.dataframe(watch_data, use_container_width=True, hide_index=True)

# --- Tab 4: Debt Structure ---
with tab4:
    st.subheader("Debt Structure Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Debt", "$2.5B")
    col2.metric("Leverage", "3.8x")
    col3.metric("Coverage", "4.2x")
    col4.metric("Credit Health", "0.62")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Net Debt", "$2.1B")
    col6.metric("Avg Maturity", "5.2Y")
    col7.metric("Near-Term %", "22%")
    col8.metric("Refi Risk", "0.35")

    st.markdown("#### Maturity Wall")
    mat_data = pd.DataFrame([
        {"Year": 2026, "Amount ($M)": 350, "% of Total": "14%"},
        {"Year": 2027, "Amount ($M)": 200, "% of Total": "8%"},
        {"Year": 2028, "Amount ($M)": 500, "% of Total": "20%"},
        {"Year": 2029, "Amount ($M)": 450, "% of Total": "18%"},
        {"Year": 2030, "Amount ($M)": 600, "% of Total": "24%"},
        {"Year": "2031+", "Amount ($M)": 400, "% of Total": "16%"},
    ])
    st.dataframe(mat_data, use_container_width=True, hide_index=True)
