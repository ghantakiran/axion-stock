"""Event-Driven Analytics Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Event Analytics", layout="wide")
st.title("Event-Driven Analytics")

# --- Sidebar ---
st.sidebar.header("Event Settings")
symbol = st.sidebar.text_input("Symbol", "AAPL")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Earnings", "M&A / Risk Arb", "Corporate Actions", "Event Signals",
])

# --- Tab 1: Earnings ---
with tab1:
    st.subheader("Earnings Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Beat Rate", "75%")
    col2.metric("Avg Surprise", "+5.2%")
    col3.metric("Streak", "+3 beats")
    col4.metric("Avg PEAD", "+1.8%")

    st.markdown("#### Recent Earnings")
    earn_data = pd.DataFrame([
        {"Quarter": "Q3 2025", "EPS Est": "$1.50", "EPS Act": "$1.62",
         "Surprise": "+8.0%", "Result": "Beat", "Post Drift": "+2.3%"},
        {"Quarter": "Q2 2025", "EPS Est": "$1.45", "EPS Act": "$1.52",
         "Surprise": "+4.8%", "Result": "Beat", "Post Drift": "+1.5%"},
        {"Quarter": "Q1 2025", "EPS Est": "$1.40", "EPS Act": "$1.43",
         "Surprise": "+2.1%", "Result": "Beat", "Post Drift": "+0.8%"},
        {"Quarter": "Q4 2024", "EPS Est": "$1.38", "EPS Act": "$1.35",
         "Surprise": "-2.2%", "Result": "Miss", "Post Drift": "-1.5%"},
    ])
    st.dataframe(earn_data, use_container_width=True, hide_index=True)

# --- Tab 2: M&A / Risk Arb ---
with tab2:
    st.subheader("M&A Deal Monitor")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Deals", "8")
    col2.metric("Avg Spread", "5.2%")
    col3.metric("Avg Probability", "78%")
    col4.metric("Strong Buys", "2")

    st.markdown("#### Active Deals")
    deal_data = pd.DataFrame([
        {"Target": "VMW", "Acquirer": "AVGO", "Spread": "3.2%",
         "Ann. Spread": "8.5%", "Probability": "92%", "Signal": "Strong Buy"},
        {"Target": "ATVI", "Acquirer": "MSFT", "Spread": "1.8%",
         "Ann. Spread": "12.1%", "Probability": "88%", "Signal": "Buy"},
        {"Target": "SGEN", "Acquirer": "PFE", "Spread": "5.5%",
         "Ann. Spread": "9.2%", "Probability": "72%", "Signal": "Buy"},
        {"Target": "SAVE", "Acquirer": "JBLU", "Spread": "18.5%",
         "Ann. Spread": "25.0%", "Probability": "45%", "Signal": "Avoid"},
    ])
    st.dataframe(deal_data, use_container_width=True, hide_index=True)

# --- Tab 3: Corporate Actions ---
with tab3:
    st.subheader("Corporate Actions")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Upcoming", "5")
    col2.metric("Div Yield", "0.55%")
    col3.metric("Buyback", "$90B")
    col4.metric("Div Growth", "+4.2%")

    st.markdown("#### Upcoming Events")
    corp_data = pd.DataFrame([
        {"Symbol": "AAPL", "Type": "Dividend", "Effective": "2025-08-10",
         "Amount": "$0.25", "Days Until": "8"},
        {"Symbol": "NVDA", "Type": "Split", "Effective": "2025-08-15",
         "Amount": "10:1", "Days Until": "13"},
        {"Symbol": "MSFT", "Type": "Dividend", "Effective": "2025-08-20",
         "Amount": "$0.75", "Days Until": "18"},
        {"Symbol": "GOOGL", "Type": "Buyback", "Effective": "2025-09-01",
         "Amount": "$70B", "Days Until": "30"},
    ])
    st.dataframe(corp_data, use_container_width=True, hide_index=True)

# --- Tab 4: Event Signals ---
with tab4:
    st.subheader("Composite Event Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite", "+0.65")
    col2.metric("Direction", "Bullish")
    col3.metric("Strength", "Strong")
    col4.metric("Signals", "3")

    st.markdown("#### Top Event Signals")
    sig_data = pd.DataFrame([
        {"Symbol": "AAPL", "Composite": "+0.72", "Earnings": "+0.85",
         "M&A": "—", "Corporate": "+0.40", "Direction": "Bullish"},
        {"Symbol": "VMW", "Composite": "+0.68", "Earnings": "+0.30",
         "M&A": "+0.90", "Corporate": "—", "Direction": "Bullish"},
        {"Symbol": "NVDA", "Composite": "+0.55", "Earnings": "+0.65",
         "M&A": "—", "Corporate": "+0.20", "Direction": "Bullish"},
        {"Symbol": "BA", "Composite": "-0.45", "Earnings": "-0.60",
         "M&A": "—", "Corporate": "+0.10", "Direction": "Bearish"},
    ])
    st.dataframe(sig_data, use_container_width=True, hide_index=True)
