"""Regime Detection Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Regime Detection", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Market Regime Detection")

# --- Sidebar ---
st.sidebar.header("Regime Settings")
method = st.sidebar.selectbox("Detection Method", ["HMM", "Clustering", "Rule-Based"], index=0)
n_regimes = st.sidebar.selectbox("Number of Regimes", [3, 4], index=1)
lookback = st.sidebar.selectbox("Lookback", ["1 Year", "3 Years", "5 Years"], index=1)

# --- Main Content ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Current Regime", "Regime History", "Transitions", "Allocation",
    "Signal Adaptation", "Dynamic Thresholds", "Ensemble", "Regime Signals",
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

# --- Tab 5: Signal Adaptation ---
with tab5:
    st.subheader("Regime-Aware Signal Adaptation")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Composite Score", "+0.52")
    col2.metric("Amplified", "2")
    col3.metric("Suppressed", "1")
    col4.metric("Direction", "Bullish")

    st.markdown("#### Signal Adjustments (Bull Regime)")
    adapt_data = pd.DataFrame([
        {"Signal": "RSI Momentum", "Category": "momentum", "Raw": "+0.60",
         "Multiplier": "1.40x", "Adapted": "+0.84", "Status": "Amplified"},
        {"Signal": "P/E Value", "Category": "value", "Raw": "+0.40",
         "Multiplier": "0.70x", "Adapted": "+0.28", "Status": "Suppressed"},
        {"Signal": "ROE Quality", "Category": "quality", "Raw": "+0.50",
         "Multiplier": "0.90x", "Adapted": "+0.45", "Status": "Suppressed"},
        {"Signal": "MACD Tech", "Category": "technical", "Raw": "+0.55",
         "Multiplier": "1.20x", "Adapted": "+0.66", "Status": "Amplified"},
    ])
    st.dataframe(adapt_data, use_container_width=True, hide_index=True)

    st.markdown("#### Cross-Regime Comparison")
    compare_data = pd.DataFrame([
        {"Category": "Momentum", "Bull": "1.40x", "Sideways": "0.80x",
         "Bear": "0.50x", "Crisis": "0.30x"},
        {"Category": "Value", "Bull": "0.70x", "Sideways": "1.20x",
         "Bear": "1.30x", "Crisis": "0.60x"},
        {"Category": "Quality", "Bull": "0.90x", "Sideways": "1.10x",
         "Bear": "1.40x", "Crisis": "1.50x"},
        {"Category": "Technical", "Bull": "1.20x", "Sideways": "1.00x",
         "Bear": "0.80x", "Crisis": "0.50x"},
    ])
    st.dataframe(compare_data, use_container_width=True, hide_index=True)

# --- Tab 6: Dynamic Thresholds ---
with tab6:
    st.subheader("Dynamic Threshold Management")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Entry Threshold", "0.30")
    col2.metric("Stop Loss", "7.0%")
    col3.metric("Take Profit", "15.0%")
    col4.metric("Position Size", "1.2x")

    st.markdown("#### Regime Threshold Comparison")
    thresh_data = pd.DataFrame([
        {"Regime": "Bull", "Entry": "0.30", "Exit": "-0.30", "Stop": "7.0%",
         "Take Profit": "15.0%", "Min Conf": "50%", "Pos Size": "1.2x"},
        {"Regime": "Sideways", "Entry": "0.50", "Exit": "-0.20", "Stop": "5.0%",
         "Take Profit": "10.0%", "Min Conf": "60%", "Pos Size": "0.8x"},
        {"Regime": "Bear", "Entry": "0.60", "Exit": "-0.10", "Stop": "3.0%",
         "Take Profit": "8.0%", "Min Conf": "70%", "Pos Size": "0.6x"},
        {"Regime": "Crisis", "Entry": "0.80", "Exit": "-0.05", "Stop": "2.0%",
         "Take Profit": "5.0%", "Min Conf": "85%", "Pos Size": "0.3x"},
    ])
    st.dataframe(thresh_data, use_container_width=True, hide_index=True)

    st.markdown("#### Signal Decisions")
    decision_data = pd.DataFrame([
        {"Signal": "RSI Momentum", "Score": "+0.84", "Confidence": "85%",
         "Action": "Enter", "Stop Loss": "7.0%", "Take Profit": "15.0%"},
        {"Signal": "MACD Cross", "Score": "+0.45", "Confidence": "70%",
         "Action": "Enter", "Stop Loss": "7.0%", "Take Profit": "15.0%"},
        {"Signal": "Mean Revert", "Score": "+0.20", "Confidence": "60%",
         "Action": "Hold", "Stop Loss": "—", "Take Profit": "—"},
        {"Signal": "Vol Spike", "Score": "-0.35", "Confidence": "75%",
         "Action": "Exit", "Stop Loss": "—", "Take Profit": "—"},
    ])
    st.dataframe(decision_data, use_container_width=True, hide_index=True)

# --- Tab 7: Ensemble ---
with tab7:
    st.subheader("Multi-Method Regime Ensemble")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Consensus", "Bull")
    col2.metric("Confidence", "72%")
    col3.metric("Agreement", "67%")
    col4.metric("Unanimous", "No")

    st.markdown("#### Method Results")
    method_data = pd.DataFrame([
        {"Method": "HMM", "Regime": "Bull", "Confidence": "80%",
         "Weight": "0.40", "Agrees": "Yes"},
        {"Method": "Clustering", "Regime": "Bull", "Confidence": "60%",
         "Weight": "0.30", "Agrees": "Yes"},
        {"Method": "Rule-Based", "Regime": "Sideways", "Confidence": "70%",
         "Weight": "0.30", "Agrees": "No"},
    ])
    st.dataframe(method_data, use_container_width=True, hide_index=True)

    st.markdown("#### Consensus Probabilities")
    prob_data = pd.DataFrame([
        {"Regime": "Bull", "HMM": "70%", "Clustering": "55%",
         "Rule-Based": "30%", "Ensemble": "54%"},
        {"Regime": "Sideways", "HMM": "20%", "Clustering": "30%",
         "Rule-Based": "50%", "Ensemble": "32%"},
        {"Regime": "Bear", "HMM": "8%", "Clustering": "10%",
         "Rule-Based": "15%", "Ensemble": "10%"},
        {"Regime": "Crisis", "HMM": "2%", "Clustering": "5%",
         "Rule-Based": "5%", "Ensemble": "4%"},
    ])
    st.dataframe(prob_data, use_container_width=True, hide_index=True)

# --- Tab 8: Regime Signals ---
with tab8:
    st.subheader("Regime-Derived Trading Signals")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Bias", "Bullish")
    col2.metric("Conviction", "0.72")
    col3.metric("Transition", "Risk On")
    col4.metric("Persistence", "Normal")

    st.markdown("#### Signal Components")
    sig_data = pd.DataFrame([
        {"Signal Type": "Transition", "Value": "Bear → Bull",
         "Classification": "Risk On", "Strength": "0.64", "Actionable": "Yes"},
        {"Signal Type": "Persistence", "Value": "50 days (ratio: 0.63)",
         "Classification": "Normal", "Strength": "0.70", "Actionable": "No"},
        {"Signal Type": "Alignment", "Value": "Mom +0.60 in Bull",
         "Classification": "Lean In", "Strength": "0.60", "Actionable": "Yes"},
        {"Signal Type": "Divergence", "Value": "2/3 methods agree",
         "Classification": "Uncertain", "Strength": "0.33", "Actionable": "No"},
    ])
    st.dataframe(sig_data, use_container_width=True, hide_index=True)

    st.markdown("#### Transition Signal Reference")
    trans_ref = pd.DataFrame([
        {"From": "Crisis", "To": "Bull", "Signal": "Risk On", "Strength": "1.0"},
        {"From": "Bear", "To": "Bull", "Signal": "Risk On", "Strength": "0.8"},
        {"From": "Bear", "To": "Sideways", "Signal": "Risk On", "Strength": "0.5"},
        {"From": "Bull", "To": "Crisis", "Signal": "Risk Off", "Strength": "1.0"},
        {"From": "Bull", "To": "Bear", "Signal": "Risk Off", "Strength": "0.7"},
        {"From": "Sideways", "To": "Crisis", "Signal": "Risk Off", "Strength": "0.8"},
    ])
    st.dataframe(trans_ref, use_container_width=True, hide_index=True)
