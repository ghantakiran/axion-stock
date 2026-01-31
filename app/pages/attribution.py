"""Performance Attribution Dashboard."""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Attribution", layout="wide")
st.title("Performance Attribution")

# --- Sidebar ---
st.sidebar.header("Attribution")
benchmark = st.sidebar.selectbox("Benchmark", ["S&P 500", "NASDAQ 100", "Russell 2000", "60/40"])
period = st.sidebar.selectbox("Period", ["YTD", "1M", "3M", "6M", "1Y", "3Y", "Inception"])

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Summary", "Brinson Attribution", "Factor Attribution", "Tear Sheet",
])

# --- Tab 1: Summary ---
with tab1:
    st.subheader("Performance Summary")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Return", "+18.5%")
    col2.metric("Benchmark", "+12.2%")
    col3.metric("Active Return", "+6.3%")
    col4.metric("Sharpe Ratio", "1.85")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Volatility", "14.2%")
    col6.metric("Max Drawdown", "-8.3%")
    col7.metric("Tracking Error", "5.1%")
    col8.metric("Information Ratio", "1.24")

    st.markdown("#### Benchmark Comparison")
    bm_data = pd.DataFrame([
        {"Metric": "Total Return", "Portfolio": "+18.5%", "Benchmark": "+12.2%", "Difference": "+6.3%"},
        {"Metric": "Annualized Return", "Portfolio": "+18.5%", "Benchmark": "+12.2%", "Difference": "+6.3%"},
        {"Metric": "Volatility", "Portfolio": "14.2%", "Benchmark": "12.0%", "Difference": "+2.2%"},
        {"Metric": "Sharpe Ratio", "Portfolio": "1.85", "Benchmark": "1.42", "Difference": "+0.43"},
        {"Metric": "Max Drawdown", "Portfolio": "-8.3%", "Benchmark": "-10.5%", "Difference": "+2.2%"},
        {"Metric": "Beta", "Portfolio": "0.95", "Benchmark": "1.00", "Difference": "-0.05"},
        {"Metric": "Alpha (ann.)", "Portfolio": "5.8%", "Benchmark": "—", "Difference": "—"},
        {"Metric": "Up Capture", "Portfolio": "105%", "Benchmark": "100%", "Difference": "+5%"},
        {"Metric": "Down Capture", "Portfolio": "82%", "Benchmark": "100%", "Difference": "-18%"},
    ])
    st.dataframe(bm_data, use_container_width=True, hide_index=True)

# --- Tab 2: Brinson Attribution ---
with tab2:
    st.subheader("Brinson-Fachler Attribution")

    col1, col2, col3 = st.columns(3)
    col1.metric("Allocation Effect", "+1.8%")
    col2.metric("Selection Effect", "+3.5%")
    col3.metric("Interaction Effect", "+1.0%")

    st.markdown("#### Sector Breakdown")
    brinson_data = pd.DataFrame([
        {"Sector": "Technology", "Port Weight": "35%", "BM Weight": "28%",
         "Port Return": "22%", "BM Return": "18%",
         "Allocation": "+0.8%", "Selection": "+1.4%", "Interaction": "+0.3%", "Total": "+2.5%"},
        {"Sector": "Healthcare", "Port Weight": "18%", "BM Weight": "15%",
         "Port Return": "12%", "BM Return": "10%",
         "Allocation": "+0.2%", "Selection": "+0.3%", "Interaction": "+0.1%", "Total": "+0.6%"},
        {"Sector": "Financials", "Port Weight": "12%", "BM Weight": "14%",
         "Port Return": "15%", "BM Return": "11%",
         "Allocation": "-0.1%", "Selection": "+0.6%", "Interaction": "-0.1%", "Total": "+0.4%"},
        {"Sector": "Consumer", "Port Weight": "15%", "BM Weight": "18%",
         "Port Return": "8%", "BM Return": "7%",
         "Allocation": "+0.3%", "Selection": "+0.2%", "Interaction": "-0.0%", "Total": "+0.5%"},
        {"Sector": "Energy", "Port Weight": "5%", "BM Weight": "8%",
         "Port Return": "25%", "BM Return": "20%",
         "Allocation": "-0.2%", "Selection": "+0.4%", "Interaction": "-0.2%", "Total": "+0.0%"},
    ])
    st.dataframe(brinson_data, use_container_width=True, hide_index=True)

# --- Tab 3: Factor Attribution ---
with tab3:
    st.subheader("Factor Attribution")

    factor_data = pd.DataFrame([
        {"Factor": "Market", "Exposure": "1.05", "Factor Return": "12.2%",
         "Contribution": "12.8%", "Share": "69%"},
        {"Factor": "Value", "Exposure": "0.25", "Factor Return": "4.5%",
         "Contribution": "1.1%", "Share": "6%"},
        {"Factor": "Momentum", "Exposure": "0.35", "Factor Return": "6.2%",
         "Contribution": "2.2%", "Share": "12%"},
        {"Factor": "Quality", "Exposure": "0.15", "Factor Return": "3.1%",
         "Contribution": "0.5%", "Share": "3%"},
        {"Factor": "Size", "Exposure": "-0.10", "Factor Return": "2.0%",
         "Contribution": "-0.2%", "Share": "-1%"},
        {"Factor": "Specific (Alpha)", "Exposure": "—", "Factor Return": "—",
         "Contribution": "2.1%", "Share": "11%"},
    ])
    st.dataframe(factor_data, use_container_width=True, hide_index=True)

    st.markdown(f"**R² = 0.89** — Factor model explains 89% of return variance")

# --- Tab 4: Tear Sheet ---
with tab4:
    st.subheader("Monthly Returns")

    monthly_data = pd.DataFrame([
        {"Month": "Jan", "Portfolio": "+3.2%", "Benchmark": "+2.1%", "Active": "+1.1%"},
        {"Month": "Feb", "Portfolio": "-1.5%", "Benchmark": "-2.8%", "Active": "+1.3%"},
        {"Month": "Mar", "Portfolio": "+2.8%", "Benchmark": "+1.5%", "Active": "+1.3%"},
        {"Month": "Apr", "Portfolio": "+4.1%", "Benchmark": "+3.2%", "Active": "+0.9%"},
        {"Month": "May", "Portfolio": "-0.8%", "Benchmark": "-1.2%", "Active": "+0.4%"},
        {"Month": "Jun", "Portfolio": "+2.5%", "Benchmark": "+1.8%", "Active": "+0.7%"},
    ])
    st.dataframe(monthly_data, use_container_width=True, hide_index=True)

    st.markdown("#### Top Drawdowns")
    dd_data = pd.DataFrame([
        {"Rank": "1", "Start": "2025-02-15", "Trough": "2025-03-05",
         "Recovery": "2025-03-22", "Depth": "-8.3%", "Duration": "25 days"},
        {"Rank": "2", "Start": "2025-05-10", "Trough": "2025-05-18",
         "Recovery": "2025-05-28", "Depth": "-4.1%", "Duration": "18 days"},
        {"Rank": "3", "Start": "2025-07-20", "Trough": "2025-07-25",
         "Recovery": "2025-08-02", "Depth": "-3.2%", "Duration": "13 days"},
    ])
    st.dataframe(dd_data, use_container_width=True, hide_index=True)

    st.markdown("#### Distribution Stats")
    dist_data = pd.DataFrame([
        {"Metric": "Skewness", "Value": "-0.18"},
        {"Metric": "Kurtosis", "Value": "1.52"},
        {"Metric": "VaR (95%)", "Value": "-1.82%"},
        {"Metric": "CVaR (95%)", "Value": "-2.45%"},
        {"Metric": "Best Day", "Value": "+3.8%"},
        {"Metric": "Worst Day", "Value": "-4.1%"},
        {"Metric": "Win Rate", "Value": "54.2%"},
    ])
    st.dataframe(dist_data, use_container_width=True, hide_index=True)
