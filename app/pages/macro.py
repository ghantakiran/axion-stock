"""Macro Regime Analysis Dashboard."""

import streamlit as st
import pandas as pd

try:
    st.set_page_config(page_title="Macro Regime Analysis", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Macro Regime Analysis")

# --- Sidebar ---
st.sidebar.header("Macro Settings")
period = st.sidebar.selectbox("Period", ["3 Months", "6 Months", "1 Year"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Indicators", "Yield Curve", "Regimes", "Factor Model",
])

# --- Tab 1: Indicators ---
with tab1:
    st.subheader("Economic Indicators")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite Index", "+0.42")
    col2.metric("Improving", "7 / 10")
    col3.metric("Breadth", "70%")
    col4.metric("Leading Score", "+0.65")

    st.markdown("#### Latest Readings")
    ind_data = pd.DataFrame([
        {"Indicator": "ISM PMI", "Value": 54.2, "Previous": 53.5,
         "Consensus": 53.8, "Surprise": "+0.4", "Type": "Leading"},
        {"Indicator": "Nonfarm Payrolls", "Value": 215, "Previous": 195,
         "Consensus": 200, "Surprise": "+15K", "Type": "Coincident"},
        {"Indicator": "CPI YoY", "Value": 2.8, "Previous": 2.9,
         "Consensus": 2.9, "Surprise": "-0.1", "Type": "Lagging"},
        {"Indicator": "Retail Sales", "Value": 0.6, "Previous": 0.3,
         "Consensus": 0.4, "Surprise": "+0.2", "Type": "Coincident"},
        {"Indicator": "Building Permits", "Value": 1.42, "Previous": 1.38,
         "Consensus": 1.40, "Surprise": "+0.02", "Type": "Leading"},
    ])
    st.dataframe(ind_data, use_container_width=True, hide_index=True)

# --- Tab 2: Yield Curve ---
with tab2:
    st.subheader("Yield Curve Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Shape", "Normal")
    col2.metric("2s10s Spread", "+40 bps")
    col3.metric("Inverted?", "No")
    col4.metric("Level", "4.45%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Slope (NS)", "-0.85")
    col6.metric("Curvature (NS)", "0.42")
    col7.metric("Short Rate", "4.00%")
    col8.metric("Long Rate", "5.00%")

    st.markdown("#### Current Curve")
    curve_data = pd.DataFrame([
        {"Tenor": "3M", "Yield": "4.00%"},
        {"Tenor": "6M", "Yield": "4.10%"},
        {"Tenor": "1Y", "Yield": "4.20%"},
        {"Tenor": "2Y", "Yield": "4.30%"},
        {"Tenor": "5Y", "Yield": "4.50%"},
        {"Tenor": "10Y", "Yield": "4.70%"},
        {"Tenor": "30Y", "Yield": "5.00%"},
    ])
    st.dataframe(curve_data, use_container_width=True, hide_index=True)

# --- Tab 3: Regimes ---
with tab3:
    st.subheader("Regime Detection")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Regime", "Expansion")
    col2.metric("Probability", "75%")
    col3.metric("Duration", "6 months")
    col4.metric("Consensus", "70%")

    st.markdown("#### Transition Probabilities")
    trans_data = pd.DataFrame([
        {"From": "Expansion", "To Expansion": "70%", "To Slowdown": "20%",
         "To Contraction": "5%", "To Recovery": "5%"},
        {"From": "Slowdown", "To Expansion": "15%", "To Slowdown": "50%",
         "To Contraction": "30%", "To Recovery": "5%"},
        {"From": "Contraction", "To Expansion": "5%", "To Slowdown": "10%",
         "To Contraction": "55%", "To Recovery": "30%"},
        {"From": "Recovery", "To Expansion": "40%", "To Slowdown": "10%",
         "To Contraction": "5%", "To Recovery": "45%"},
    ])
    st.dataframe(trans_data, use_container_width=True, hide_index=True)

# --- Tab 4: Factor Model ---
with tab4:
    st.subheader("Macro Factor Model")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dominant Factor", "Growth")
    col2.metric("Growth Return", "+0.5%")
    col3.metric("Inflation Return", "-0.2%")
    col4.metric("Rates Return", "+0.1%")

    st.markdown("#### Factor Exposures & Momentum")
    factor_data = pd.DataFrame([
        {"Factor": "Growth", "Return": "+0.50%", "Exposure": "+1.2 std",
         "Momentum": "+0.35", "Regime Avg": "+0.42%"},
        {"Factor": "Inflation", "Return": "-0.20%", "Exposure": "-0.5 std",
         "Momentum": "-0.12", "Regime Avg": "-0.15%"},
        {"Factor": "Rates", "Return": "+0.10%", "Exposure": "+0.3 std",
         "Momentum": "+0.08", "Regime Avg": "+0.12%"},
        {"Factor": "Risk", "Return": "-0.05%", "Exposure": "-0.2 std",
         "Momentum": "-0.03", "Regime Avg": "-0.08%"},
        {"Factor": "Liquidity", "Return": "+0.15%", "Exposure": "+0.8 std",
         "Momentum": "+0.22", "Regime Avg": "+0.18%"},
    ])
    st.dataframe(factor_data, use_container_width=True, hide_index=True)
