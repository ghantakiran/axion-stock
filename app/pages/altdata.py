"""Alternative Data Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Alternative Data", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Alternative Data")

# --- Sidebar ---
st.sidebar.header("Alt Data Settings")
symbol = st.sidebar.text_input("Symbol", "WMT")

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Satellite Signals", "Web Traffic", "Social Sentiment", "Composite Score",
])

# --- Tab 1: Satellite Signals ---
with tab1:
    st.subheader("Satellite Signal Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Parking Lot", "Z: +1.8")
    col2.metric("Oil Storage", "Z: -0.3")
    col3.metric("Shipping", "Z: +0.9")
    col4.metric("Construction", "Z: +0.5")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Anomalies", "1")
    col6.metric("Signal", "Bullish")
    col7.metric("Trend", "+0.12")
    col8.metric("Quality", "Medium")

    st.markdown("#### Recent Satellite Observations")
    sat_data = pd.DataFrame([
        {"Symbol": "WMT", "Type": "Parking Lot", "Z-Score": 1.8,
         "Anomaly": "Yes", "Trend": "+0.12", "Signal": "Bullish"},
        {"Symbol": "XOM", "Type": "Oil Storage", "Z-Score": -0.3,
         "Anomaly": "No", "Trend": "-0.05", "Signal": "Neutral"},
        {"Symbol": "FDX", "Type": "Shipping", "Z-Score": 0.9,
         "Anomaly": "No", "Trend": "+0.08", "Signal": "Bullish"},
        {"Symbol": "DHI", "Type": "Construction", "Z-Score": 2.3,
         "Anomaly": "Yes", "Trend": "+0.15", "Signal": "Bullish"},
    ])
    st.dataframe(sat_data, use_container_width=True, hide_index=True)

# --- Tab 2: Web Traffic ---
with tab2:
    st.subheader("Web Traffic Analytics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Visits (7d)", "12.5M")
    col2.metric("Growth", "+18.5%")
    col3.metric("Engagement", "0.72")
    col4.metric("Momentum", "+0.15")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Unique Visitors", "8.2M")
    col6.metric("Bounce Rate", "32%")
    col7.metric("Avg Duration", "3m 12s")
    col8.metric("Signal", "Bullish")

    st.markdown("#### Traffic Trends")
    traffic_data = pd.DataFrame([
        {"Symbol": "AMZN", "Domain": "amazon.com", "Visits": "45M",
         "Growth": "+12%", "Engagement": 0.78, "Signal": "Bullish"},
        {"Symbol": "SHOP", "Domain": "shopify.com", "Visits": "8M",
         "Growth": "+25%", "Engagement": 0.65, "Signal": "Bullish"},
        {"Symbol": "META", "Domain": "facebook.com", "Visits": "120M",
         "Growth": "-2%", "Engagement": 0.55, "Signal": "Neutral"},
        {"Symbol": "NFLX", "Domain": "netflix.com", "Visits": "35M",
         "Growth": "+8%", "Engagement": 0.82, "Signal": "Bullish"},
    ])
    st.dataframe(traffic_data, use_container_width=True, hide_index=True)

# --- Tab 3: Social Sentiment ---
with tab3:
    st.subheader("Social Sentiment Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mentions", "2,450")
    col2.metric("Sentiment", "+0.42")
    col3.metric("Bullish %", "65%")
    col4.metric("Spike?", "No")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Reddit", "+0.55")
    col6.metric("Twitter/X", "+0.38")
    col7.metric("StockTwits", "+0.45")
    col8.metric("News", "+0.30")

    st.markdown("#### Trending Mentions")
    social_data = pd.DataFrame([
        {"Symbol": "NVDA", "Mentions": 5200, "Sentiment": "+0.68",
         "Bullish": "78%", "Spike": "Yes", "Source": "Reddit"},
        {"Symbol": "TSLA", "Mentions": 4800, "Sentiment": "+0.12",
         "Bullish": "52%", "Spike": "No", "Source": "Twitter"},
        {"Symbol": "GME", "Mentions": 3200, "Sentiment": "+0.45",
         "Bullish": "70%", "Spike": "Yes", "Source": "StockTwits"},
        {"Symbol": "AAPL", "Mentions": 2100, "Sentiment": "+0.35",
         "Bullish": "60%", "Spike": "No", "Source": "News"},
    ])
    st.dataframe(social_data, use_container_width=True, hide_index=True)

# --- Tab 4: Composite Score ---
with tab4:
    st.subheader("Composite Alternative Data Score")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite", "0.58")
    col2.metric("Quality", "Medium")
    col3.metric("Confidence", "0.65")
    col4.metric("Sources", "3/4")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Satellite", "+0.72")
    col6.metric("Web Traffic", "+0.45")
    col7.metric("Social", "+0.55")
    col8.metric("Consensus?", "Yes")

    st.markdown("#### Top Alt Data Signals")
    composite_data = pd.DataFrame([
        {"Symbol": "WMT", "Composite": 0.72, "Quality": "High",
         "Satellite": 0.85, "Web": 0.62, "Social": 0.68, "Sources": 3},
        {"Symbol": "AMZN", "Composite": 0.65, "Quality": "High",
         "Satellite": 0.45, "Web": 0.82, "Social": 0.70, "Sources": 3},
        {"Symbol": "NVDA", "Composite": 0.58, "Quality": "Medium",
         "Satellite": 0.0, "Web": 0.55, "Social": 0.78, "Sources": 2},
        {"Symbol": "XOM", "Composite": 0.42, "Quality": "Medium",
         "Satellite": 0.72, "Web": 0.20, "Social": 0.35, "Sources": 3},
    ])
    st.dataframe(composite_data, use_container_width=True, hide_index=True)
