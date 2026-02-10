"""Tail Risk Hedging Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Tail Risk Hedging", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Tail Risk Management")

# --- Sidebar ---
st.sidebar.header("Risk Settings")
confidence = st.sidebar.selectbox("Confidence Level", ["95%", "99%"], index=0)
horizon = st.sidebar.selectbox("Horizon", ["1 Day", "5 Days", "10 Days"], index=0)
method = st.sidebar.selectbox("CVaR Method", ["Historical", "Parametric", "Cornish-Fisher"], index=0)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "CVaR Analysis", "Tail Dependence", "Hedge Construction", "Drawdown Budget",
])

# --- Tab 1: CVaR ---
with tab1:
    st.subheader("Expected Shortfall (CVaR)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VaR (95%)", "$1.65M (1.65%)")
    col2.metric("CVaR (95%)", "$2.31M (2.31%)")
    col3.metric("Tail Ratio", "1.40x")
    col4.metric("Excess over VaR", "0.66%")

    st.markdown("#### Multi-Horizon CVaR")
    horizon_data = pd.DataFrame([
        {"Horizon": "1 day", "VaR": "1.65%", "CVaR": "2.31%", "CVaR $": "$2.31M", "Tail Ratio": "1.40x"},
        {"Horizon": "5 days", "VaR": "3.69%", "CVaR": "5.17%", "CVaR $": "$5.17M", "Tail Ratio": "1.40x"},
        {"Horizon": "10 days", "VaR": "5.22%", "CVaR": "7.31%", "CVaR $": "$7.31M", "Tail Ratio": "1.40x"},
        {"Horizon": "20 days", "VaR": "7.38%", "CVaR": "10.33%", "CVaR $": "$10.33M", "Tail Ratio": "1.40x"},
    ])
    st.dataframe(horizon_data, use_container_width=True, hide_index=True)

    st.markdown("#### CVaR Decomposition by Position")
    decomp_data = pd.DataFrame([
        {"Asset": "SPY", "Weight": "50%", "Marginal CVaR": "2.8%",
         "Component CVaR": "1.40%", "% of Total": "61%"},
        {"Asset": "TLT", "Weight": "30%", "Marginal CVaR": "1.5%",
         "Component CVaR": "0.45%", "% of Total": "19%"},
        {"Asset": "GLD", "Weight": "20%", "Marginal CVaR": "2.3%",
         "Component CVaR": "0.46%", "% of Total": "20%"},
    ])
    st.dataframe(decomp_data, use_container_width=True, hide_index=True)

# --- Tab 2: Tail Dependence ---
with tab2:
    st.subheader("Tail Dependence Analysis")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Max Lower Tail", "0.42 (SPY-GLD)")
    col2.metric("Avg Contagion", "0.25")
    col3.metric("Tail Amplification", "1.8x")
    col4.metric("Pairs Analyzed", "3")

    st.markdown("#### Tail Dependence Matrix")
    td_data = pd.DataFrame([
        {"Pair": "SPY-TLT", "Lower Tail": "0.12", "Upper Tail": "0.08",
         "Normal Corr": "-0.30", "Tail Corr": "-0.45", "Contagion": "0.07"},
        {"Pair": "SPY-GLD", "Lower Tail": "0.42", "Upper Tail": "0.15",
         "Normal Corr": "0.10", "Tail Corr": "0.35", "Contagion": "0.39"},
        {"Pair": "TLT-GLD", "Lower Tail": "0.18", "Upper Tail": "0.22",
         "Normal Corr": "0.20", "Tail Corr": "0.28", "Contagion": "0.14"},
    ])
    st.dataframe(td_data, use_container_width=True, hide_index=True)

    st.markdown("#### Contagion Risk")
    st.info(
        "SPY-GLD shows elevated tail dependence (0.42): these assets crash "
        "together 42% of the time when SPY is in its worst 5% of returns. "
        "Normal correlation is only 0.10, suggesting hidden tail risk."
    )

# --- Tab 3: Hedge Construction ---
with tab3:
    st.subheader("Hedge Portfolio")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Hedge Cost", "1.2% ($12,000)")
    col2.metric("CVaR Reduction", "35%")
    col3.metric("Unhedged CVaR", "2.31%")
    col4.metric("Hedged CVaR", "1.50%")

    st.markdown("#### Recommended Hedges")
    hedge_data = pd.DataFrame([
        {"Instrument": "Put 5% OTM (30d)", "Notional": "$1.0M",
         "Cost": "0.8% ($8,000)", "Protection": "10%",
         "Effectiveness": "0.72", "Cost Effective?": "Yes"},
        {"Instrument": "VIX Call (10%)", "Notional": "$100K",
         "Cost": "0.3% ($3,000)", "Protection": "15%",
         "Effectiveness": "0.70", "Cost Effective?": "Yes"},
        {"Instrument": "Cash (2%)", "Notional": "$20K",
         "Cost": "0.01% ($100)", "Protection": "2%",
         "Effectiveness": "0.40", "Cost Effective?": "No"},
    ])
    st.dataframe(hedge_data, use_container_width=True, hide_index=True)

    st.markdown("#### Cost vs Protection Tradeoff")
    tradeoff_data = pd.DataFrame([
        {"Budget": "0.5%", "Instruments": "Put only", "CVaR Reduction": "18%"},
        {"Budget": "1.0%", "Instruments": "Put + VIX", "CVaR Reduction": "30%"},
        {"Budget": "1.5%", "Instruments": "Put + VIX + Cash", "CVaR Reduction": "38%"},
        {"Budget": "2.0%", "Instruments": "Deep Put + VIX + Cash", "CVaR Reduction": "45%"},
    ])
    st.dataframe(tradeoff_data, use_container_width=True, hide_index=True)

# --- Tab 4: Drawdown Budget ---
with tab4:
    st.subheader("Drawdown Risk Budgeting")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Max Portfolio DD", "-20% target")
    col2.metric("Current DD", "-3.2%")
    col3.metric("CDaR (95%)", "-8.5%")
    col4.metric("Recovery Days", "15")

    st.markdown("#### Drawdown Statistics")
    dd_stats = pd.DataFrame([
        {"Metric": "Maximum Drawdown", "Value": "-12.5%"},
        {"Metric": "Average Drawdown", "Value": "-2.8%"},
        {"Metric": "Current Drawdown", "Value": "-3.2%"},
        {"Metric": "Drawdown Duration", "Value": "8 days"},
        {"Metric": "CDaR (95%)", "Value": "-8.5%"},
        {"Metric": "Recovery from Max DD", "Value": "45 days"},
    ])
    st.dataframe(dd_stats, use_container_width=True, hide_index=True)

    st.markdown("#### Asset Drawdown Budgets")
    budget_data = pd.DataFrame([
        {"Asset": "SPY", "Weight": "50%", "Max DD": "-18%",
         "Budget": "8.0%", "Usage": "9.0%", "Status": "Over Budget",
         "Rec. Weight": "44%"},
        {"Asset": "TLT", "Weight": "30%", "Max DD": "-8%",
         "Budget": "7.5%", "Usage": "2.4%", "Status": "Under Budget",
         "Rec. Weight": "37%"},
        {"Asset": "GLD", "Weight": "20%", "Max DD": "-15%",
         "Budget": "4.5%", "Usage": "3.0%", "Status": "Under Budget",
         "Rec. Weight": "19%"},
    ])
    st.dataframe(budget_data, use_container_width=True, hide_index=True)
