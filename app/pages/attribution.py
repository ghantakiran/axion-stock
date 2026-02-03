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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "Summary", "Brinson Attribution", "Factor Attribution",
    "Risk Decomposition", "Performance Contribution", "Tear Sheet",
    "Multi-Period", "Fama-French", "Geographic", "Risk-Adjusted",
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

# --- Tab 4: Risk Decomposition ---
with tab4:
    st.subheader("Risk Decomposition (Euler)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Portfolio Vol", "14.2%")
    col2.metric("Positions", "25")
    col3.metric("Top Risk", "AAPL (18%)")
    col4.metric("Diversification", "0.72")

    st.markdown("#### Position Risk Contributions")
    risk_data = pd.DataFrame([
        {"Position": "AAPL", "Weight": "8.0%", "Vol": "28.5%",
         "Component Risk": "2.56%", "Marginal Risk": "32.0%", "% of Total": "18.0%"},
        {"Position": "MSFT", "Weight": "7.0%", "Vol": "24.2%",
         "Component Risk": "1.98%", "Marginal Risk": "28.3%", "% of Total": "13.9%"},
        {"Position": "GOOGL", "Weight": "6.5%", "Vol": "26.8%",
         "Component Risk": "1.82%", "Marginal Risk": "28.0%", "% of Total": "12.8%"},
        {"Position": "AMZN", "Weight": "6.0%", "Vol": "30.1%",
         "Component Risk": "1.74%", "Marginal Risk": "29.0%", "% of Total": "12.2%"},
        {"Position": "NVDA", "Weight": "5.5%", "Vol": "42.3%",
         "Component Risk": "1.65%", "Marginal Risk": "30.0%", "% of Total": "11.6%"},
    ])
    st.dataframe(risk_data, use_container_width=True, hide_index=True)

    st.markdown("#### Sector Risk")
    sector_risk_data = pd.DataFrame([
        {"Sector": "Technology", "Weight": "35%", "Component Risk": "8.2%", "% of Total": "58%"},
        {"Sector": "Healthcare", "Weight": "18%", "Component Risk": "2.1%", "% of Total": "15%"},
        {"Sector": "Financials", "Weight": "12%", "Component Risk": "1.5%", "% of Total": "11%"},
        {"Sector": "Consumer", "Weight": "15%", "Component Risk": "1.2%", "% of Total": "8%"},
        {"Sector": "Energy", "Weight": "5%", "Component Risk": "0.6%", "% of Total": "4%"},
    ])
    st.dataframe(sector_risk_data, use_container_width=True, hide_index=True)

# --- Tab 5: Performance Contribution ---
with tab5:
    st.subheader("Performance Contribution")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Return", "+18.5%")
    col2.metric("Hit Rate", "68%")
    col3.metric("Concentration", "42%")
    col4.metric("Positions", "25")

    st.markdown("#### Top Contributors")
    top_data = pd.DataFrame([
        {"Symbol": "NVDA", "Weight": "5.5%", "Return": "+85%",
         "Contribution": "+4.68%", "% of Total": "25.3%"},
        {"Symbol": "AAPL", "Weight": "8.0%", "Return": "+22%",
         "Contribution": "+1.76%", "% of Total": "9.5%"},
        {"Symbol": "META", "Weight": "4.5%", "Return": "+35%",
         "Contribution": "+1.58%", "% of Total": "8.5%"},
        {"Symbol": "LLY", "Weight": "3.5%", "Return": "+42%",
         "Contribution": "+1.47%", "% of Total": "7.9%"},
        {"Symbol": "MSFT", "Weight": "7.0%", "Return": "+18%",
         "Contribution": "+1.26%", "% of Total": "6.8%"},
    ])
    st.dataframe(top_data, use_container_width=True, hide_index=True)

    st.markdown("#### Bottom Contributors")
    bottom_data = pd.DataFrame([
        {"Symbol": "BA", "Weight": "2.0%", "Return": "-25%",
         "Contribution": "-0.50%", "% of Total": "-2.7%"},
        {"Symbol": "DIS", "Weight": "2.5%", "Return": "-12%",
         "Contribution": "-0.30%", "% of Total": "-1.6%"},
        {"Symbol": "PFE", "Weight": "3.0%", "Return": "-8%",
         "Contribution": "-0.24%", "% of Total": "-1.3%"},
        {"Symbol": "NKE", "Weight": "1.5%", "Return": "-15%",
         "Contribution": "-0.23%", "% of Total": "-1.2%"},
        {"Symbol": "INTC", "Weight": "1.0%", "Return": "-18%",
         "Contribution": "-0.18%", "% of Total": "-1.0%"},
    ])
    st.dataframe(bottom_data, use_container_width=True, hide_index=True)

# --- Tab 6: Tear Sheet ---
with tab6:
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

# --- Tab 7: Multi-Period Attribution ---
with tab7:
    st.subheader("Multi-Period Brinson Attribution (Carino Linking)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Linked Allocation", "+1.9%")
    col2.metric("Linked Selection", "+3.6%")
    col3.metric("Linked Interaction", "+0.9%")
    col4.metric("Residual", "0.01%")

    st.markdown("#### Period-by-Period Decomposition")
    mp_data = pd.DataFrame([
        {"Period": "Q1", "Portfolio": "+5.2%", "Benchmark": "+3.8%",
         "Allocation": "+0.5%", "Selection": "+0.8%", "Interaction": "+0.1%"},
        {"Period": "Q2", "Portfolio": "+3.1%", "Benchmark": "+2.5%",
         "Allocation": "+0.3%", "Selection": "+0.2%", "Interaction": "+0.1%"},
        {"Period": "Q3", "Portfolio": "-1.2%", "Benchmark": "-0.5%",
         "Allocation": "-0.2%", "Selection": "-0.4%", "Interaction": "-0.1%"},
        {"Period": "Q4", "Portfolio": "+4.8%", "Benchmark": "+3.2%",
         "Allocation": "+0.6%", "Selection": "+0.8%", "Interaction": "+0.2%"},
    ])
    st.dataframe(mp_data, use_container_width=True, hide_index=True)

    st.markdown("#### Cumulative Effects")
    cum_data = pd.DataFrame([
        {"Period": "Q1", "Cum Allocation": "+0.5%", "Cum Selection": "+0.8%",
         "Cum Active": "+1.4%"},
        {"Period": "Q1-Q2", "Cum Allocation": "+0.8%", "Cum Selection": "+1.0%",
         "Cum Active": "+2.0%"},
        {"Period": "Q1-Q3", "Cum Allocation": "+0.6%", "Cum Selection": "+0.6%",
         "Cum Active": "+1.3%"},
        {"Period": "Q1-Q4", "Cum Allocation": "+1.2%", "Cum Selection": "+1.4%",
         "Cum Active": "+2.9%"},
    ])
    st.dataframe(cum_data, use_container_width=True, hide_index=True)

# --- Tab 8: Fama-French ---
with tab8:
    st.subheader("Fama-French Factor Model")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Alpha (ann.)", "+3.2%")
    col2.metric("Alpha t-stat", "2.15")
    col3.metric("R-squared", "0.91")
    col4.metric("Preferred Model", "FF5")

    st.markdown("#### FF5 Factor Exposures")
    ff_data = pd.DataFrame([
        {"Factor": "Mkt-RF", "Beta": "1.08", "t-stat": "18.5",
         "p-value": "0.000", "Significant": "Yes", "Contribution": "12.1%"},
        {"Factor": "SMB", "Beta": "0.28", "t-stat": "3.2",
         "p-value": "0.001", "Significant": "Yes", "Contribution": "0.8%"},
        {"Factor": "HML", "Beta": "-0.15", "t-stat": "-1.8",
         "p-value": "0.072", "Significant": "No", "Contribution": "-0.5%"},
        {"Factor": "RMW", "Beta": "0.22", "t-stat": "2.6",
         "p-value": "0.010", "Significant": "Yes", "Contribution": "0.9%"},
        {"Factor": "CMA", "Beta": "-0.08", "t-stat": "-0.9",
         "p-value": "0.368", "Significant": "No", "Contribution": "-0.2%"},
    ])
    st.dataframe(ff_data, use_container_width=True, hide_index=True)

    st.markdown("#### Model Comparison")
    model_comp = pd.DataFrame([
        {"Model": "FF3", "R-squared": "0.88", "Adj R-squared": "0.87",
         "Alpha": "+3.5%", "Alpha t-stat": "2.05"},
        {"Model": "FF5", "R-squared": "0.91", "Adj R-squared": "0.90",
         "Alpha": "+3.2%", "Alpha t-stat": "2.15"},
    ])
    st.dataframe(model_comp, use_container_width=True, hide_index=True)

# --- Tab 9: Geographic Attribution ---
with tab9:
    st.subheader("Geographic Attribution")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Countries", "8")
    col2.metric("Regions", "3")
    col3.metric("Allocation Effect", "+1.2%")
    col4.metric("Currency Effect", "-0.3%")

    st.markdown("#### Region-Level Attribution")
    region_data = pd.DataFrame([
        {"Region": "North America", "Port Weight": "62%", "BM Weight": "55%",
         "Allocation": "+0.8%", "Selection": "+1.5%", "Currency": "0.0%", "Total": "+2.3%"},
        {"Region": "Europe", "Port Weight": "22%", "BM Weight": "25%",
         "Allocation": "+0.2%", "Selection": "-0.3%", "Currency": "-0.2%", "Total": "-0.3%"},
        {"Region": "Asia Pacific", "Port Weight": "16%", "BM Weight": "20%",
         "Allocation": "+0.2%", "Selection": "+0.1%", "Currency": "-0.1%", "Total": "+0.2%"},
    ])
    st.dataframe(region_data, use_container_width=True, hide_index=True)

    st.markdown("#### Country-Level Breakdown")
    country_data = pd.DataFrame([
        {"Country": "US", "Port Wt": "58%", "BM Wt": "50%",
         "Port Return": "20%", "BM Return": "15%",
         "Allocation": "+0.7%", "Selection": "+2.5%", "Total": "+3.3%"},
        {"Country": "GB", "Port Wt": "12%", "BM Wt": "15%",
         "Port Return": "8%", "BM Return": "10%",
         "Allocation": "+0.1%", "Selection": "-0.3%", "Total": "-0.2%"},
        {"Country": "JP", "Port Wt": "10%", "BM Wt": "12%",
         "Port Return": "6%", "BM Return": "5%",
         "Allocation": "+0.1%", "Selection": "+0.1%", "Total": "+0.2%"},
    ])
    st.dataframe(country_data, use_container_width=True, hide_index=True)

# --- Tab 10: Risk-Adjusted Metrics ---
with tab10:
    st.subheader("Advanced Risk-Adjusted Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("M-squared", "+16.8%")
    col2.metric("Omega Ratio", "1.85")
    col3.metric("Ulcer Index", "3.2%")
    col4.metric("Composite Score", "82")

    st.markdown("#### Standard Metrics")
    std_data = pd.DataFrame([
        {"Metric": "Sharpe Ratio", "Value": "1.85"},
        {"Metric": "Sortino Ratio", "Value": "2.45"},
        {"Metric": "Calmar Ratio", "Value": "2.23"},
        {"Metric": "Treynor Ratio", "Value": "0.19"},
    ])
    st.dataframe(std_data, use_container_width=True, hide_index=True)

    st.markdown("#### Advanced Metrics")
    adv_data = pd.DataFrame([
        {"Metric": "M-squared", "Value": "16.8%", "Description": "Risk-adjusted return at benchmark volatility"},
        {"Metric": "Omega Ratio", "Value": "1.85", "Description": "Probability-weighted gain/loss ratio"},
        {"Metric": "Gain-Loss Ratio", "Value": "1.42", "Description": "Mean gain / mean loss"},
        {"Metric": "Sterling Ratio", "Value": "3.15", "Description": "Excess return / average drawdown"},
        {"Metric": "Burke Ratio", "Value": "2.28", "Description": "Excess return / RMS of drawdowns"},
        {"Metric": "Kappa 3", "Value": "1.95", "Description": "Generalized Sortino (3rd order LPM)"},
        {"Metric": "Tail Ratio", "Value": "1.35", "Description": "95th percentile / |5th percentile|"},
        {"Metric": "Prospect Ratio", "Value": "0.0028", "Description": "Loss-aversion adjusted utility"},
    ])
    st.dataframe(adv_data, use_container_width=True, hide_index=True)

    st.markdown("#### Drawdown-Based Metrics")
    dd_metrics = pd.DataFrame([
        {"Metric": "Ulcer Index", "Value": "3.2%", "Description": "RMS of drawdown percentages"},
        {"Metric": "Pain Ratio", "Value": "4.25", "Description": "Excess return / mean drawdown"},
        {"Metric": "Martin Ratio", "Value": "5.78", "Description": "Excess return / ulcer index"},
    ])
    st.dataframe(dd_metrics, use_container_width=True, hide_index=True)
