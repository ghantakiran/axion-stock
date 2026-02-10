"""Fund Flow Analysis Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Fund Flow Analysis", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Fund Flow Analysis")

# --- Sidebar ---
st.sidebar.header("Flow Settings")
fund = st.sidebar.text_input("Fund/ETF", "SPY")
period = st.sidebar.selectbox("Period", ["1 Week", "1 Month", "3 Months"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Fund Flows", "Institutional", "Sector Rotation", "Smart Money",
])

# --- Tab 1: Fund Flows ---
with tab1:
    st.subheader("Fund Flow Summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net Flow", "+$2.3B")
    col2.metric("Flow Momentum", "+15.2%")
    col3.metric("Flow/AUM", "0.52%")
    col4.metric("Strength", "Moderate")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total Inflow", "$8.5B")
    col6.metric("Total Outflow", "$6.2B")
    col7.metric("Cumulative", "+$2.3B")
    col8.metric("Flow Ratio", "1.37x")

    st.markdown("#### Flow History")
    flow_data = pd.DataFrame([
        {"Date": "2026-01-31", "Inflow ($M)": 450, "Outflow ($M)": 320,
         "Net ($M)": 130, "Flow/AUM": "0.13%", "Direction": "Inflow"},
        {"Date": "2026-01-30", "Inflow ($M)": 380, "Outflow ($M)": 290,
         "Net ($M)": 90, "Flow/AUM": "0.09%", "Direction": "Inflow"},
        {"Date": "2026-01-29", "Inflow ($M)": 220, "Outflow ($M)": 410,
         "Net ($M)": -190, "Flow/AUM": "-0.19%", "Direction": "Outflow"},
        {"Date": "2026-01-28", "Inflow ($M)": 510, "Outflow ($M)": 280,
         "Net ($M)": 230, "Flow/AUM": "0.23%", "Direction": "Inflow"},
    ])
    st.dataframe(flow_data, use_container_width=True, hide_index=True)

# --- Tab 2: Institutional ---
with tab2:
    st.subheader("Institutional Ownership")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Institutional %", "72.5%")
    col2.metric("# Holders", "1,245")
    col3.metric("Concentration", "0.15")
    col4.metric("Net Change", "+3.2%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("New Positions", "42")
    col6.metric("Exits", "18")
    col7.metric("Increases", "385")
    col8.metric("Decreases", "210")

    st.markdown("#### Top Holders")
    holder_data = pd.DataFrame([
        {"Holder": "Vanguard Group", "Shares (M)": 120.5, "Value ($B)": 18.1,
         "Ownership": "8.2%", "Change": "+2.1%"},
        {"Holder": "BlackRock", "Shares (M)": 105.2, "Value ($B)": 15.8,
         "Ownership": "7.1%", "Change": "+1.5%"},
        {"Holder": "State Street", "Shares (M)": 62.3, "Value ($B)": 9.3,
         "Ownership": "4.2%", "Change": "-0.8%"},
        {"Holder": "Fidelity", "Shares (M)": 48.7, "Value ($B)": 7.3,
         "Ownership": "3.3%", "Change": "+5.2%"},
        {"Holder": "T. Rowe Price", "Shares (M)": 35.1, "Value ($B)": 5.3,
         "Ownership": "2.4%", "Change": "-1.2%"},
    ])
    st.dataframe(holder_data, use_container_width=True, hide_index=True)

# --- Tab 3: Sector Rotation ---
with tab3:
    st.subheader("Sector Rotation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Phase", "Mid Cycle")
    col2.metric("Top Sector", "Technology")
    col3.metric("Bottom Sector", "Utilities")
    col4.metric("Divergence", "2.1 std")

    st.markdown("#### Sector Rankings")
    rotation_data = pd.DataFrame([
        {"Rank": 1, "Sector": "Technology", "Flow Score": 1.85,
         "Momentum": 1.42, "Composite": 1.68, "Strength": "+2.1 std"},
        {"Rank": 2, "Sector": "Financials", "Flow Score": 1.20,
         "Momentum": 0.95, "Composite": 1.10, "Strength": "+1.3 std"},
        {"Rank": 3, "Sector": "Healthcare", "Flow Score": 0.45,
         "Momentum": 0.30, "Composite": 0.39, "Strength": "+0.4 std"},
        {"Rank": 4, "Sector": "Energy", "Flow Score": -0.80,
         "Momentum": -0.50, "Composite": -0.68, "Strength": "-0.8 std"},
        {"Rank": 5, "Sector": "Utilities", "Flow Score": -1.50,
         "Momentum": -1.20, "Composite": -1.38, "Strength": "-1.6 std"},
    ])
    st.dataframe(rotation_data, use_container_width=True, hide_index=True)

# --- Tab 4: Smart Money ---
with tab4:
    st.subheader("Smart Money Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signal", "Accumulation")
    col2.metric("Score", "+0.65")
    col3.metric("Conviction", "78%")
    col4.metric("Contrarian?", "Yes")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Inst. Flow", "+$5.2M")
    col6.metric("Retail Flow", "-$1.8M")
    col7.metric("Net Smart", "+$7.0M")
    col8.metric("Divergence", "+1.2")

    st.markdown("#### Recent Signals")
    signal_data = pd.DataFrame([
        {"Symbol": "AAPL", "Signal": "Accumulation", "Score": 0.65,
         "Conviction": "78%", "Divergence": "+1.2", "Contrarian": "Yes"},
        {"Symbol": "TSLA", "Signal": "Distribution", "Score": -0.52,
         "Conviction": "65%", "Divergence": "-0.8", "Contrarian": "No"},
        {"Symbol": "MSFT", "Signal": "Accumulation", "Score": 0.48,
         "Conviction": "72%", "Divergence": "+0.5", "Contrarian": "No"},
        {"Symbol": "NVDA", "Signal": "Neutral", "Score": 0.12,
         "Conviction": "35%", "Divergence": "+0.1", "Contrarian": "No"},
    ])
    st.dataframe(signal_data, use_container_width=True, hide_index=True)
