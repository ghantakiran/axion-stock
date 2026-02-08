"""Market Microstructure Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Market Microstructure", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Market Microstructure")

# --- Sidebar ---
st.sidebar.header("Microstructure Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")
period = st.sidebar.selectbox("Period", ["Today", "1 Week", "1 Month"], index=0)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Spread Analysis", "Order Book", "Tick Metrics", "Price Impact",
])

# --- Tab 1: Spread Analysis ---
with tab1:
    st.subheader("Bid-Ask Spread Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Quoted Spread", "1.2 bps")
    col2.metric("Effective Spread", "1.8 bps")
    col3.metric("Realized Spread", "0.6 bps")
    col4.metric("Adverse Selection", "1.2 bps")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Roll Spread", "$0.015")
    col6.metric("Spread Efficiency", "33%")
    col7.metric("Midpoint", "$185.42")
    col8.metric("Adverse Sel. %", "67%")

    st.markdown("#### Spread History")
    spread_data = pd.DataFrame([
        {"Time": "15:30", "Quoted (bps)": 1.2, "Effective (bps)": 1.8,
         "Realized (bps)": 0.6, "Adv. Sel. (bps)": 1.2},
        {"Time": "15:00", "Quoted (bps)": 1.1, "Effective (bps)": 1.5,
         "Realized (bps)": 0.7, "Adv. Sel. (bps)": 0.8},
        {"Time": "14:30", "Quoted (bps)": 1.4, "Effective (bps)": 2.0,
         "Realized (bps)": 0.5, "Adv. Sel. (bps)": 1.5},
        {"Time": "14:00", "Quoted (bps)": 1.0, "Effective (bps)": 1.3,
         "Realized (bps)": 0.8, "Adv. Sel. (bps)": 0.5},
    ])
    st.dataframe(spread_data, use_container_width=True, hide_index=True)

# --- Tab 2: Order Book ---
with tab2:
    st.subheader("Order Book Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Imbalance", "+0.32")
    col2.metric("Bid Depth", "45,200")
    col3.metric("Ask Depth", "28,800")
    col4.metric("Book Pressure", "+0.22")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Weighted Mid", "$185.425")
    col6.metric("Bid Slope", "0.85")
    col7.metric("Ask Slope", "1.12")
    col8.metric("Resilience", "0.94")

    st.markdown("#### Book Levels")
    book_data = pd.DataFrame([
        {"Level": 1, "Bid Price": 185.42, "Bid Size": 1200, "Ask Price": 185.43, "Ask Size": 800},
        {"Level": 2, "Bid Price": 185.41, "Bid Size": 2500, "Ask Price": 185.44, "Ask Size": 1500},
        {"Level": 3, "Bid Price": 185.40, "Bid Size": 3800, "Ask Price": 185.45, "Ask Size": 2200},
        {"Level": 4, "Bid Price": 185.39, "Bid Size": 5000, "Ask Price": 185.46, "Ask Size": 3500},
        {"Level": 5, "Bid Price": 185.38, "Bid Size": 6500, "Ask Price": 185.47, "Ask Size": 4200},
    ])
    st.dataframe(book_data, use_container_width=True, hide_index=True)

# --- Tab 3: Tick Metrics ---
with tab3:
    st.subheader("Tick-Level Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", "12,450")
    col2.metric("Total Volume", "3.2M")
    col3.metric("VWAP", "$185.38")
    col4.metric("TWAP", "$185.35")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Buy Volume", "1.8M")
    col6.metric("Sell Volume", "1.4M")
    col7.metric("Kyle's Lambda", "0.00012")
    col8.metric("Order Imbalance", "+0.13")

    st.markdown("#### Size Distribution")
    size_data = pd.DataFrame([
        {"Bucket": "0-100", "Count": 4200, "Pct": "33.7%"},
        {"Bucket": "100-500", "Count": 3800, "Pct": "30.5%"},
        {"Bucket": "500-1000", "Count": 2100, "Pct": "16.9%"},
        {"Bucket": "1000-5000", "Count": 1800, "Pct": "14.5%"},
        {"Bucket": "5000-10000", "Count": 400, "Pct": "3.2%"},
        {"Bucket": "10000+", "Count": 150, "Pct": "1.2%"},
    ])
    st.dataframe(size_data, use_container_width=True, hide_index=True)

# --- Tab 4: Price Impact ---
with tab4:
    st.subheader("Price Impact Estimation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temp Impact", "3.2 bps")
    col2.metric("Perm Impact", "1.8 bps")
    col3.metric("Total Impact", "5.0 bps")
    col4.metric("Est. Cost", "$925")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Participation", "1.0%")
    col6.metric("Daily Volume", "3.2M")
    col7.metric("Volatility", "2.1%")
    col8.metric("Model", "Square-Root")

    st.markdown("#### Optimal Execution Schedule")
    schedule_data = pd.DataFrame([
        {"Period": 1, "Shares": 3200, "Cumulative": "32%", "Est. Impact (bps)": 2.1},
        {"Period": 2, "Shares": 2400, "Cumulative": "56%", "Est. Impact (bps)": 1.5},
        {"Period": 3, "Shares": 1800, "Cumulative": "74%", "Est. Impact (bps)": 1.2},
        {"Period": 4, "Shares": 1400, "Cumulative": "88%", "Est. Impact (bps)": 0.9},
        {"Period": 5, "Shares": 1200, "Cumulative": "100%", "Est. Impact (bps)": 0.7},
    ])
    st.dataframe(schedule_data, use_container_width=True, hide_index=True)
