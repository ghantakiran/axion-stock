"""Regime Detection Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Regime Detection", layout="wide")
st.title("Market Regime Detection")

# --- Sidebar ---
st.sidebar.header("Regime Settings")
method = st.sidebar.selectbox("Detection Method", ["HMM", "Clustering", "Rule-Based"], index=0)
n_regimes = st.sidebar.selectbox("Number of Regimes", [3, 4], index=1)
lookback = st.sidebar.selectbox("Lookback", ["1 Year", "3 Years", "5 Years"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Current Regime", "Regime History", "Transitions", "Allocation",
])

# --- Tab 1: Current Regime ---
with tab1:
    st.subheader("Current Market Regime")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Regime", "BULL")
    col2.metric("Confidence", "82%")
    col3.metric("Duration", "47 days")
    col4.metric("Method", "HMM")

    st.markdown("#### Regime Probabilities")
    prob_data = pd.DataFrame([
        {"Regime": "Bull", "Probability": "62%", "Indicator": "Active"},
        {"Regime": "Sideways", "Probability": "25%", "Indicator": "-"},
        {"Regime": "Bear", "Probability": "10%", "Indicator": "-"},
        {"Regime": "Crisis", "Probability": "3%", "Indicator": "-"},
    ])
    st.dataframe(prob_data, use_container_width=True, hide_index=True)

    st.markdown("#### Regime Features")
    feature_data = pd.DataFrame([
        {"Feature": "S&P 500 vs 200 SMA", "Value": "+6.2%", "Signal": "Bullish"},
        {"Feature": "VIX Level", "Value": "14.5", "Signal": "Low Vol"},
        {"Feature": "Market Breadth", "Value": "62%", "Signal": "Positive"},
        {"Feature": "1-Month Return", "Value": "+3.1%", "Signal": "Positive"},
        {"Feature": "Avg Correlation", "Value": "0.32", "Signal": "Normal"},
    ])
    st.dataframe(feature_data, use_container_width=True, hide_index=True)

# --- Tab 2: Regime History ---
with tab2:
    st.subheader("Regime History")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Observations", "756")
    col2.metric("Regime Changes", "12")
    col3.metric("Avg Duration", "63 days")
    col4.metric("Silhouette Score", "0.42")

    st.markdown("#### Regime Segments")
    segment_data = pd.DataFrame([
        {"Period": "2024-08 to 2024-12", "Regime": "Bull", "Days": 98,
         "Avg Return": "+0.08%", "Volatility": "1.1%"},
        {"Period": "2024-05 to 2024-07", "Regime": "Sideways", "Days": 65,
         "Avg Return": "+0.01%", "Volatility": "0.9%"},
        {"Period": "2024-03 to 2024-04", "Regime": "Bear", "Days": 42,
         "Avg Return": "-0.12%", "Volatility": "1.8%"},
        {"Period": "2024-01 to 2024-02", "Regime": "Bull", "Days": 45,
         "Avg Return": "+0.07%", "Volatility": "1.0%"},
        {"Period": "2023-10 to 2023-12", "Regime": "Sideways", "Days": 60,
         "Avg Return": "+0.02%", "Volatility": "0.8%"},
    ])
    st.dataframe(segment_data, use_container_width=True, hide_index=True)

    st.markdown("#### Conditional Statistics")
    stats_data = pd.DataFrame([
        {"Regime": "Bull", "Frequency": "42%", "Avg Return": "+0.08%/d",
         "Volatility": "1.1%", "Avg Duration": "78 days", "Max Duration": "120 days"},
        {"Regime": "Sideways", "Frequency": "33%", "Avg Return": "+0.01%/d",
         "Volatility": "0.9%", "Avg Duration": "55 days", "Max Duration": "90 days"},
        {"Regime": "Bear", "Frequency": "20%", "Avg Return": "-0.10%/d",
         "Volatility": "1.8%", "Avg Duration": "35 days", "Max Duration": "65 days"},
        {"Regime": "Crisis", "Frequency": "5%", "Avg Return": "-0.45%/d",
         "Volatility": "3.5%", "Avg Duration": "12 days", "Max Duration": "25 days"},
    ])
    st.dataframe(stats_data, use_container_width=True, hide_index=True)

# --- Tab 3: Transitions ---
with tab3:
    st.subheader("Regime Transitions")

    st.markdown("#### Transition Matrix")
    trans_data = pd.DataFrame(
        {
            "From \\ To": ["Bull", "Sideways", "Bear", "Crisis"],
            "Bull": ["92%", "18%", "5%", "1%"],
            "Sideways": ["6%", "75%", "10%", "2%"],
            "Bear": ["1%", "5%", "80%", "7%"],
            "Crisis": ["1%", "2%", "5%", "90%"],
        }
    )
    st.dataframe(trans_data, use_container_width=True, hide_index=True)

    st.markdown("#### Expected Regime Durations")
    dur_data = pd.DataFrame([
        {"Regime": "Bull", "Persistence": "92%", "Expected Duration": "12.5 periods"},
        {"Regime": "Sideways", "Persistence": "75%", "Expected Duration": "4.0 periods"},
        {"Regime": "Bear", "Persistence": "80%", "Expected Duration": "5.0 periods"},
        {"Regime": "Crisis", "Persistence": "90%", "Expected Duration": "10.0 periods"},
    ])
    st.dataframe(dur_data, use_container_width=True, hide_index=True)

    st.markdown("#### 5-Step Forecast (from Bull)")
    forecast_data = pd.DataFrame([
        {"Step": 1, "Bull": "92%", "Sideways": "6%", "Bear": "1%", "Crisis": "1%"},
        {"Step": 2, "Bull": "85%", "Sideways": "10%", "Bear": "3%", "Crisis": "2%"},
        {"Step": 3, "Bull": "79%", "Sideways": "13%", "Bear": "5%", "Crisis": "3%"},
        {"Step": 4, "Bull": "74%", "Sideways": "15%", "Bear": "7%", "Crisis": "4%"},
        {"Step": 5, "Bull": "70%", "Sideways": "17%", "Bear": "8%", "Crisis": "5%"},
    ])
    st.dataframe(forecast_data, use_container_width=True, hide_index=True)

# --- Tab 4: Allocation ---
with tab4:
    st.subheader("Regime-Aware Allocation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Regime", "Bull")
    col2.metric("Expected Return", "15% ann.")
    col3.metric("Expected Risk", "12% ann.")
    col4.metric("Defensive?", "No")

    st.markdown("#### Target Allocation (Bull)")
    alloc_data = pd.DataFrame([
        {"Asset": "Equity", "Weight": "70%", "Signal": "Overweight"},
        {"Asset": "Bonds", "Weight": "15%", "Signal": "Underweight"},
        {"Asset": "Commodities", "Weight": "10%", "Signal": "Neutral"},
        {"Asset": "Cash", "Weight": "5%", "Signal": "Minimum"},
    ])
    st.dataframe(alloc_data, use_container_width=True, hide_index=True)

    st.markdown("#### Regime Target Comparison")
    compare_data = pd.DataFrame([
        {"Asset": "Equity", "Bull": "70%", "Sideways": "50%", "Bear": "30%", "Crisis": "15%"},
        {"Asset": "Bonds", "Bull": "15%", "Sideways": "30%", "Bear": "40%", "Crisis": "30%"},
        {"Asset": "Commodities", "Bull": "10%", "Sideways": "10%", "Bear": "10%", "Crisis": "5%"},
        {"Asset": "Cash", "Bull": "5%", "Sideways": "10%", "Bear": "20%", "Crisis": "50%"},
    ])
    st.dataframe(compare_data, use_container_width=True, hide_index=True)

    st.markdown("#### Recommended Shifts (if regime → Crisis)")
    shift_data = pd.DataFrame([
        {"Asset": "Equity", "Current": "70%", "Target": "15%", "Action": "Sell 55%"},
        {"Asset": "Bonds", "Current": "15%", "Target": "30%", "Action": "Buy 15%"},
        {"Asset": "Commodities", "Current": "10%", "Target": "5%", "Action": "Sell 5%"},
        {"Asset": "Cash", "Current": "5%", "Target": "50%", "Action": "Buy 45%"},
    ])
    st.dataframe(shift_data, use_container_width=True, hide_index=True)
