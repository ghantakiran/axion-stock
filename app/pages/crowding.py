"""Crowding Analysis Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Crowding Analysis", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Crowding Analysis")

# --- Sidebar ---
st.sidebar.header("Crowding Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Crowding", "Fund Overlap", "Short Interest", "Consensus",
])

# --- Tab 1: Crowding ---
with tab1:
    st.subheader("Position Crowding")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Crowding Score", "0.72")
    col2.metric("Level", "High")
    col3.metric("# Holders", "1,245")
    col4.metric("Concentration", "0.18")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Momentum", "+0.05")
    col6.metric("Percentile", "85th")
    col7.metric("De-crowding?", "No")
    col8.metric("Risk", "Elevated")

    st.markdown("#### Most Crowded Names")
    crowd_data = pd.DataFrame([
        {"Symbol": "AAPL", "# Funds": 42, "Ownership": "72.5%",
         "Avg Position": "2.8%", "Intensity": 0.82},
        {"Symbol": "MSFT", "# Funds": 38, "Ownership": "68.2%",
         "Avg Position": "2.5%", "Intensity": 0.78},
        {"Symbol": "NVDA", "# Funds": 35, "Ownership": "55.1%",
         "Avg Position": "3.2%", "Intensity": 0.75},
        {"Symbol": "AMZN", "# Funds": 33, "Ownership": "52.8%",
         "Avg Position": "2.1%", "Intensity": 0.70},
    ])
    st.dataframe(crowd_data, use_container_width=True, hide_index=True)

# --- Tab 2: Fund Overlap ---
with tab2:
    st.subheader("Fund Overlap Analysis")

    st.markdown("#### Highest Overlap Pairs")
    overlap_data = pd.DataFrame([
        {"Fund A": "Vanguard Growth", "Fund B": "BlackRock Growth",
         "Overlap": "62%", "Shared": 85, "Method": "Jaccard"},
        {"Fund A": "Fidelity Blue Chip", "Fund B": "T. Rowe Price Growth",
         "Overlap": "55%", "Shared": 72, "Method": "Jaccard"},
        {"Fund A": "ARK Innovation", "Fund B": "ARK Genomic",
         "Overlap": "48%", "Shared": 25, "Method": "Jaccard"},
        {"Fund A": "Bridgewater All Weather", "Fund B": "AQR Risk Parity",
         "Overlap": "42%", "Shared": 60, "Method": "Jaccard"},
    ])
    st.dataframe(overlap_data, use_container_width=True, hide_index=True)

# --- Tab 3: Short Interest ---
with tab3:
    st.subheader("Short Interest Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SI Ratio", "5.2%")
    col2.metric("Days to Cover", "2.8")
    col3.metric("Squeeze Score", "0.35")
    col4.metric("Risk", "Moderate")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Shares Short", "78M")
    col6.metric("Float", "1.5B")
    col7.metric("Cost to Borrow", "1.2%")
    col8.metric("SI Momentum", "+0.8%")

    st.markdown("#### High Short Interest")
    si_data = pd.DataFrame([
        {"Symbol": "GME", "SI Ratio": "21.5%", "DTC": 5.2,
         "Squeeze Score": 0.82, "Risk": "High", "CTB": "35%"},
        {"Symbol": "AMC", "SI Ratio": "18.3%", "DTC": 4.8,
         "Squeeze Score": 0.75, "Risk": "Elevated", "CTB": "28%"},
        {"Symbol": "BBBY", "SI Ratio": "15.1%", "DTC": 3.5,
         "Squeeze Score": 0.62, "Risk": "Elevated", "CTB": "15%"},
        {"Symbol": "TSLA", "SI Ratio": "3.2%", "DTC": 1.2,
         "Squeeze Score": 0.25, "Risk": "Low", "CTB": "0.8%"},
    ])
    st.dataframe(si_data, use_container_width=True, hide_index=True)

# --- Tab 4: Consensus ---
with tab4:
    st.subheader("Analyst Consensus")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rating", "Buy (4.2)")
    col2.metric("# Analysts", "42")
    col3.metric("Mean Target", "$195")
    col4.metric("Upside", "+12.5%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Buy", "32 (76%)")
    col6.metric("Hold", "8 (19%)")
    col7.metric("Sell", "2 (5%)")
    col8.metric("Contrarian?", "No")

    st.markdown("#### Contrarian Opportunities")
    cons_data = pd.DataFrame([
        {"Symbol": "XYZ", "Rating": "Strong Buy (4.8)", "Buy%": "95%",
         "Divergence": 0.3, "Contrarian": "Yes", "Revision": "+0.2"},
        {"Symbol": "ABC", "Rating": "Strong Sell (1.3)", "Buy%": "5%",
         "Divergence": 0.4, "Contrarian": "Yes", "Revision": "-0.1"},
        {"Symbol": "DEF", "Rating": "Hold (3.0)", "Buy%": "40%",
         "Divergence": 1.2, "Contrarian": "No", "Revision": "0.0"},
    ])
    st.dataframe(cons_data, use_container_width=True, hide_index=True)
