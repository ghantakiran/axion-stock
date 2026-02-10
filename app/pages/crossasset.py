"""Cross-Asset Signals Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Cross-Asset Signals", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Cross-Asset Signal Analysis")

# --- Sidebar ---
st.sidebar.header("Signal Settings")
lookback = st.sidebar.selectbox("Lookback", ["3 Months", "6 Months", "1 Year"], index=1)
assets = st.sidebar.multiselect(
    "Asset Classes",
    ["SPY (Equity)", "TLT (Bonds)", "GLD (Gold)", "UUP (Dollar)", "USO (Oil)"],
    default=["SPY (Equity)", "TLT (Bonds)", "GLD (Gold)", "UUP (Dollar)"],
)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Intermarket", "Lead-Lag", "Momentum", "Composite Signals",
])

# --- Tab 1: Intermarket ---
with tab1:
    st.subheader("Intermarket Relationships")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Correlation", "0.35")
    col2.metric("Divergences", "2")
    col3.metric("Regime", "Normal")
    col4.metric("Top Pair", "SPY-TLT")

    st.markdown("#### Correlation Matrix")
    corr_data = pd.DataFrame(
        {
            "": ["SPY", "TLT", "GLD", "UUP"],
            "SPY": ["1.00", "-0.42", "0.15", "-0.28"],
            "TLT": ["-0.42", "1.00", "0.22", "-0.10"],
            "GLD": ["0.15", "0.22", "1.00", "-0.55"],
            "UUP": ["-0.28", "-0.10", "-0.55", "1.00"],
        }
    )
    st.dataframe(corr_data, use_container_width=True, hide_index=True)

    st.markdown("#### Relative Strength")
    rs_data = pd.DataFrame([
        {"Rank": 1, "Asset": "SPY", "Return (6M)": "+8.5%", "vs Benchmark": "+4.2%", "Trend": "Outperforming"},
        {"Rank": 2, "Asset": "GLD", "Return (6M)": "+5.8%", "vs Benchmark": "+1.5%", "Trend": "Outperforming"},
        {"Rank": 3, "Asset": "TLT", "Return (6M)": "+2.1%", "vs Benchmark": "-2.2%", "Trend": "Underperforming"},
        {"Rank": 4, "Asset": "UUP", "Return (6M)": "+0.8%", "vs Benchmark": "-3.5%", "Trend": "Underperforming"},
    ])
    st.dataframe(rs_data, use_container_width=True, hide_index=True)

    st.markdown("#### Divergence Detection")
    div_data = pd.DataFrame([
        {"Pair": "SPY-TLT", "Current Corr": "-0.42", "Long-Term": "-0.30",
         "Z-Score": "-1.8", "Status": "Weakening"},
        {"Pair": "GLD-UUP", "Current Corr": "-0.55", "Long-Term": "-0.45",
         "Z-Score": "-1.2", "Status": "Stable"},
        {"Pair": "SPY-GLD", "Current Corr": "0.15", "Long-Term": "0.05",
         "Z-Score": "1.6", "Status": "Diverging"},
    ])
    st.dataframe(div_data, use_container_width=True, hide_index=True)

# --- Tab 2: Lead-Lag ---
with tab2:
    st.subheader("Lead-Lag Relationships")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Significant Pairs", "3")
    col2.metric("Avg Lead Time", "4.2 days")
    col3.metric("Best Stability", "0.72")
    col4.metric("Top Leader", "TLT")

    st.markdown("#### Detected Lead-Lag Pairs")
    ll_data = pd.DataFrame([
        {"Leader": "TLT", "Lagger": "SPY", "Lag": "3 days",
         "Correlation": "0.35", "Significant": "Yes", "Stability": "0.72"},
        {"Leader": "UUP", "Lagger": "GLD", "Lag": "2 days",
         "Correlation": "-0.28", "Significant": "Yes", "Stability": "0.65"},
        {"Leader": "VIX", "Lagger": "SPY", "Lag": "1 day",
         "Correlation": "-0.42", "Significant": "Yes", "Stability": "0.58"},
    ])
    st.dataframe(ll_data, use_container_width=True, hide_index=True)

    st.markdown("#### Current Signals from Leaders")
    leader_sig = pd.DataFrame([
        {"Leader": "TLT", "Recent Return": "+0.3%", "Signal for Lagger": "SPY Bullish",
         "Confidence": "72%"},
        {"Leader": "UUP", "Recent Return": "+0.1%", "Signal for Lagger": "GLD Bearish",
         "Confidence": "65%"},
    ])
    st.dataframe(leader_sig, use_container_width=True, hide_index=True)

# --- Tab 3: Momentum ---
with tab3:
    st.subheader("Cross-Asset Momentum")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trending Assets", "2")
    col2.metric("Mean-Reverting", "1")
    col3.metric("Top Momentum", "SPY")
    col4.metric("Most Oversold", "TLT")

    st.markdown("#### Time-Series & Cross-Sectional Momentum")
    mom_data = pd.DataFrame([
        {"Asset": "SPY", "TS Momentum": "+5.2%", "XS Rank": "1st (1.00)",
         "Z-Score": "1.2", "Trend Strength": "1.8", "Signal": "Bullish"},
        {"Asset": "GLD", "TS Momentum": "+2.8%", "XS Rank": "2nd (0.67)",
         "Z-Score": "0.5", "Trend Strength": "0.9", "Signal": "Bullish"},
        {"Asset": "UUP", "TS Momentum": "+0.4%", "XS Rank": "3rd (0.33)",
         "Z-Score": "-0.3", "Trend Strength": "0.3", "Signal": "Neutral"},
        {"Asset": "TLT", "TS Momentum": "-1.5%", "XS Rank": "4th (0.00)",
         "Z-Score": "-2.3", "Trend Strength": "-1.1", "Signal": "Mean-Revert Buy"},
    ])
    st.dataframe(mom_data, use_container_width=True, hide_index=True)

# --- Tab 4: Composite Signals ---
with tab4:
    st.subheader("Composite Cross-Asset Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Actionable Signals", "3")
    col2.metric("Strongest", "SPY Bullish")
    col3.metric("Avg Confidence", "62%")
    col4.metric("Signal Agreement", "High")

    st.markdown("#### Composite Signals")
    signal_data = pd.DataFrame([
        {"Asset": "SPY", "Direction": "Bullish", "Strength": "Strong",
         "Score": "+5.2 bps", "Confidence": "75%",
         "Momentum": "+3.1", "Lead-Lag": "+1.2", "Intermarket": "+0.9"},
        {"Asset": "GLD", "Direction": "Bullish", "Strength": "Moderate",
         "Score": "+2.8 bps", "Confidence": "60%",
         "Momentum": "+1.8", "Lead-Lag": "+0.5", "Intermarket": "+0.5"},
        {"Asset": "TLT", "Direction": "Bullish", "Strength": "Weak",
         "Score": "+1.2 bps", "Confidence": "45%",
         "Momentum": "-1.0", "Lead-Lag": "+1.5", "Intermarket": "+0.7"},
        {"Asset": "UUP", "Direction": "Bearish", "Strength": "Moderate",
         "Score": "-2.1 bps", "Confidence": "55%",
         "Momentum": "-0.8", "Lead-Lag": "-0.7", "Intermarket": "-0.6"},
    ])
    st.dataframe(signal_data, use_container_width=True, hide_index=True)

    st.markdown("#### Signal Component Weights")
    weight_data = pd.DataFrame([
        {"Component": "Momentum", "Weight": "30%", "Description": "Time-series and cross-sectional momentum"},
        {"Component": "Lead-Lag", "Weight": "25%", "Description": "Signals from leading indicators"},
        {"Component": "Intermarket", "Weight": "30%", "Description": "Correlation divergence signals"},
        {"Component": "Mean-Reversion", "Weight": "15%", "Description": "Z-score based reversal signals"},
    ])
    st.dataframe(weight_data, use_container_width=True, hide_index=True)
