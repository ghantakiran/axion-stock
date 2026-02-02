"""Dark Pool Analytics Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Dark Pool Analytics", layout="wide")
st.title("Dark Pool Analytics")

# --- Sidebar ---
st.sidebar.header("Dark Pool Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
period = st.sidebar.selectbox("Period", ["Today", "1 Week", "1 Month"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Volume Analysis", "Print Analysis", "Block Detection", "Liquidity",
])

# --- Tab 1: Volume Analysis ---
with tab1:
    st.subheader("Dark Pool Volume")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dark Share", "41.2%")
    col2.metric("Dark Volume", "1.3M")
    col3.metric("Lit Volume", "1.8M")
    col4.metric("Trend", "+2.1%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Short Volume", "390K")
    col6.metric("Short Ratio", "30.1%")
    col7.metric("# Venues", "5")
    col8.metric("Status", "Normal")

    st.markdown("#### Volume History")
    vol_data = pd.DataFrame([
        {"Date": "2026-01-31", "Dark Vol": "1.3M", "Lit Vol": "1.8M",
         "Dark Share": "41.2%", "Short Ratio": "30.1%"},
        {"Date": "2026-01-30", "Dark Vol": "1.1M", "Lit Vol": "1.9M",
         "Dark Share": "36.7%", "Short Ratio": "28.5%"},
        {"Date": "2026-01-29", "Dark Vol": "1.5M", "Lit Vol": "1.7M",
         "Dark Share": "46.9%", "Short Ratio": "32.4%"},
        {"Date": "2026-01-28", "Dark Vol": "1.2M", "Lit Vol": "1.8M",
         "Dark Share": "40.0%", "Short Ratio": "29.8%"},
    ])
    st.dataframe(vol_data, use_container_width=True, hide_index=True)

# --- Tab 2: Print Analysis ---
with tab2:
    st.subheader("Dark Print Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Prints", "8,450")
    col2.metric("Avg Size", "4,200")
    col3.metric("Avg Improvement", "0.3 bps")
    col4.metric("Block %", "15.2%")

    st.markdown("#### Print Distribution")
    print_data = pd.DataFrame([
        {"Type": "Block", "Count": 85, "Volume": "1.2M", "Pct": "15.2%"},
        {"Type": "Institutional", "Count": 2100, "Volume": "4.5M", "Pct": "35.8%"},
        {"Type": "Midpoint", "Count": 3200, "Volume": "2.8M", "Pct": "22.3%"},
        {"Type": "Retail", "Count": 2800, "Volume": "0.4M", "Pct": "3.2%"},
        {"Type": "Unknown", "Count": 265, "Volume": "2.9M", "Pct": "23.5%"},
    ])
    st.dataframe(print_data, use_container_width=True, hide_index=True)

# --- Tab 3: Block Detection ---
with tab3:
    st.subheader("Block Trade Detection")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Blocks", "85")
    col2.metric("Block Volume", "1.2M")
    col3.metric("Buy Blocks", "48")
    col4.metric("Sell Blocks", "32")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Clusters", "5")
    col6.metric("Significant", "12")
    col7.metric("Avg Size", "14,100")
    col8.metric("Total Notional", "$180M")

    st.markdown("#### Recent Blocks")
    block_data = pd.DataFrame([
        {"Time": "15:42", "Size": 50000, "Price": "$185.42",
         "Direction": "Buy", "ADV%": "5.0%", "Cluster": 1},
        {"Time": "15:38", "Size": 35000, "Price": "$185.38",
         "Direction": "Buy", "ADV%": "3.5%", "Cluster": 1},
        {"Time": "15:35", "Size": 28000, "Price": "$185.35",
         "Direction": "Sell", "ADV%": "2.8%", "Cluster": 1},
        {"Time": "14:52", "Size": 20000, "Price": "$185.50",
         "Direction": "Buy", "ADV%": "2.0%", "Cluster": 0},
    ])
    st.dataframe(block_data, use_container_width=True, hide_index=True)

# --- Tab 4: Liquidity ---
with tab4:
    st.subheader("Dark Pool Liquidity")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Liquidity Score", "0.65")
    col2.metric("Level", "Moderate")
    col3.metric("Est. Depth", "520K")
    col4.metric("Dark/Lit Ratio", "0.68")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Consistency", "0.82")
    col6.metric("1K Fill Rate", "99%")
    col7.metric("10K Fill Rate", "89%")
    col8.metric("100K Fill Rate", "52%")

    st.markdown("#### Fill Rate Estimates")
    fill_data = pd.DataFrame([
        {"Order Size": "1,000", "Est. Fill Rate": "99.2%", "Avg Time": "< 1 min"},
        {"Order Size": "5,000", "Est. Fill Rate": "95.1%", "Avg Time": "2 min"},
        {"Order Size": "10,000", "Est. Fill Rate": "89.3%", "Avg Time": "5 min"},
        {"Order Size": "50,000", "Est. Fill Rate": "72.5%", "Avg Time": "15 min"},
        {"Order Size": "100,000", "Est. Fill Rate": "52.1%", "Avg Time": "30 min"},
    ])
    st.dataframe(fill_data, use_container_width=True, hide_index=True)
