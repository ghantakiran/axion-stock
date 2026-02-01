"""Order Flow Analysis Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Order Flow Analysis", layout="wide")
st.title("Order Flow Analysis")

# --- Sidebar ---
st.sidebar.header("Order Flow Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
window = st.sidebar.selectbox("Window", ["5 min", "15 min", "1 hour", "1 day"], index=2)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Imbalance", "Blocks", "Pressure", "Smart Money",
])

# --- Tab 1: Imbalance ---
with tab1:
    st.subheader("Order Book Imbalance")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bid Volume", "52,300")
    col2.metric("Ask Volume", "38,100")
    col3.metric("Imbalance Ratio", "1.37")
    col4.metric("Type", "Balanced")

    st.markdown("#### Recent Imbalance History")
    imb_data = pd.DataFrame([
        {"Time": "14:30", "Bid Vol": "52,300", "Ask Vol": "38,100",
         "Ratio": 1.37, "Type": "Balanced", "Signal": "Neutral"},
        {"Time": "14:00", "Bid Vol": "68,500", "Ask Vol": "32,200",
         "Ratio": 2.13, "Type": "Bid Heavy", "Signal": "Buy"},
        {"Time": "13:30", "Bid Vol": "28,100", "Ask Vol": "55,800",
         "Ratio": 0.50, "Type": "Ask Heavy", "Signal": "Sell"},
        {"Time": "13:00", "Bid Vol": "45,200", "Ask Vol": "42,100",
         "Ratio": 1.07, "Type": "Balanced", "Signal": "Neutral"},
    ])
    st.dataframe(imb_data, use_container_width=True, hide_index=True)

# --- Tab 2: Blocks ---
with tab2:
    st.subheader("Block Trades")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Blocks Detected", "12")
    col2.metric("Institutional", "4")
    col3.metric("Block Volume", "1.2M shares")
    col4.metric("Block Ratio", "18%")

    st.markdown("#### Recent Block Trades")
    block_data = pd.DataFrame([
        {"Time": "14:15", "Size": "200,000", "Price": "$148.50",
         "Side": "Buy", "Value": "$29.7M", "Class": "Institutional"},
        {"Time": "13:45", "Size": "150,000", "Price": "$148.20",
         "Side": "Buy", "Value": "$22.2M", "Class": "Institutional"},
        {"Time": "12:30", "Size": "80,000", "Price": "$147.90",
         "Side": "Sell", "Value": "$11.8M", "Class": "Large"},
        {"Time": "11:15", "Size": "120,000", "Price": "$148.10",
         "Side": "Buy", "Value": "$17.8M", "Class": "Institutional"},
        {"Time": "10:30", "Size": "55,000", "Price": "$147.50",
         "Side": "Sell", "Value": "$8.1M", "Class": "Large"},
    ])
    st.dataframe(block_data, use_container_width=True, hide_index=True)

# --- Tab 3: Pressure ---
with tab3:
    st.subheader("Buy/Sell Pressure")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Buy Volume", "3.2M")
    col2.metric("Sell Volume", "2.1M")
    col3.metric("Net Flow", "+1.1M")
    col4.metric("Direction", "Buying")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Pressure Ratio", "1.52")
    col6.metric("Buy %", "60.4%")
    col7.metric("Cumulative Delta", "+2.8M")
    col8.metric("Smoothed Ratio", "1.38")

    st.markdown("#### Pressure History")
    pressure_data = pd.DataFrame([
        {"Date": "2026-01-31", "Buy Vol": "3.2M", "Sell Vol": "2.1M",
         "Net": "+1.1M", "Ratio": 1.52, "Direction": "Buying", "Cum Delta": "+2.8M"},
        {"Date": "2026-01-30", "Buy Vol": "2.8M", "Sell Vol": "3.0M",
         "Net": "-0.2M", "Ratio": 0.93, "Direction": "Neutral", "Cum Delta": "+1.7M"},
        {"Date": "2026-01-29", "Buy Vol": "2.5M", "Sell Vol": "1.8M",
         "Net": "+0.7M", "Ratio": 1.39, "Direction": "Neutral", "Cum Delta": "+1.9M"},
        {"Date": "2026-01-28", "Buy Vol": "1.9M", "Sell Vol": "2.4M",
         "Net": "-0.5M", "Ratio": 0.79, "Direction": "Neutral", "Cum Delta": "+1.2M"},
    ])
    st.dataframe(pressure_data, use_container_width=True, hide_index=True)

# --- Tab 4: Smart Money ---
with tab4:
    st.subheader("Smart Money Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signal", "Buy")
    col2.metric("Confidence", "72%")
    col3.metric("Block Ratio", "18%")
    col4.metric("Inst. Buy %", "68%")

    st.markdown("#### Smart Money History")
    smart_data = pd.DataFrame([
        {"Date": "2026-01-31", "Signal": "Buy", "Confidence": "72%",
         "Inst Net Flow": "+450K", "Inst Buy %": "68%", "Block Ratio": "18%"},
        {"Date": "2026-01-30", "Signal": "Neutral", "Confidence": "35%",
         "Inst Net Flow": "-50K", "Inst Buy %": "48%", "Block Ratio": "12%"},
        {"Date": "2026-01-29", "Signal": "Buy", "Confidence": "65%",
         "Inst Net Flow": "+320K", "Inst Buy %": "62%", "Block Ratio": "15%"},
        {"Date": "2026-01-28", "Signal": "Sell", "Confidence": "58%",
         "Inst Net Flow": "-280K", "Inst Buy %": "38%", "Block Ratio": "14%"},
    ])
    st.dataframe(smart_data, use_container_width=True, hide_index=True)
