"""Paper Trading Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd

try:
    st.set_page_config(page_title="Paper Trading", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

st.title("Paper Trading")

# --- Sidebar ---
st.sidebar.header("Paper Trading")
session_name = st.sidebar.text_input("Session Name", "My Session")
initial_capital = st.sidebar.number_input("Initial Capital ($)", value=100_000, step=10_000)
symbols_input = st.sidebar.text_input("Symbols", "AAPL, MSFT, GOOGL, AMZN, META")
strategy = st.sidebar.selectbox(
    "Strategy", ["Manual", "Equal Weight", "Momentum", "Factor-Based"],
)
rebalance = st.sidebar.selectbox(
    "Rebalance", ["Manual", "Daily", "Weekly", "Monthly"], index=3,
)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Active Session", "Trade Log", "Performance", "Compare Sessions",
])

# --- Tab 1: Active Session ---
with tab1:
    st.subheader("Session Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Equity", "$108,250", "+8.3%")
    col2.metric("Cash", "$22,150")
    col3.metric("Positions", "5")
    col4.metric("Drawdown", "-2.1%")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total Return", "+8.3%")
    col6.metric("Sharpe Ratio", "1.52")
    col7.metric("Win Rate", "62%")
    col8.metric("Total Trades", "24")

    st.markdown("#### Current Positions")
    positions_data = pd.DataFrame([
        {"Symbol": "AAPL", "Qty": 120, "Avg Cost": "$178.50", "Current": "$185.20",
         "P&L": "+$804", "P&L %": "+3.8%", "Weight": "20.5%"},
        {"Symbol": "MSFT", "Qty": 55, "Avg Cost": "$405.00", "Current": "$412.30",
         "P&L": "+$402", "P&L %": "+1.8%", "Weight": "20.9%"},
        {"Symbol": "GOOGL", "Qty": 75, "Avg Cost": "$142.80", "Current": "$148.50",
         "P&L": "+$428", "P&L %": "+4.0%", "Weight": "10.3%"},
        {"Symbol": "AMZN", "Qty": 60, "Avg Cost": "$185.60", "Current": "$192.40",
         "P&L": "+$408", "P&L %": "+3.7%", "Weight": "10.7%"},
        {"Symbol": "META", "Qty": 40, "Avg Cost": "$510.00", "Current": "$525.80",
         "P&L": "+$632", "P&L %": "+3.1%", "Weight": "19.4%"},
    ])
    st.dataframe(positions_data, use_container_width=True, hide_index=True)

# --- Tab 2: Trade Log ---
with tab2:
    st.subheader("Trade History")

    trades_data = pd.DataFrame([
        {"Time": "2026-01-30 10:15", "Symbol": "AAPL", "Side": "BUY", "Qty": 20,
         "Price": "$184.50", "Notional": "$3,690", "Reason": "rebalance"},
        {"Time": "2026-01-28 14:30", "Symbol": "MSFT", "Side": "SELL", "Qty": 10,
         "Price": "$415.20", "Notional": "$4,152", "Reason": "take_profit"},
        {"Time": "2026-01-25 09:45", "Symbol": "GOOGL", "Side": "BUY", "Qty": 25,
         "Price": "$145.30", "Notional": "$3,633", "Reason": "rebalance"},
        {"Time": "2026-01-22 11:00", "Symbol": "META", "Side": "BUY", "Qty": 15,
         "Price": "$508.90", "Notional": "$7,634", "Reason": "signal"},
        {"Time": "2026-01-20 15:45", "Symbol": "AMZN", "Side": "SELL", "Qty": 20,
         "Price": "$188.40", "Notional": "$3,768", "Reason": "stop_loss"},
    ])
    st.dataframe(trades_data, use_container_width=True, hide_index=True)

    st.markdown("#### Trade Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", "24")
    col2.metric("Buys", "14")
    col3.metric("Sells", "10")
    col4.metric("Total Costs", "$12.80")

# --- Tab 3: Performance ---
with tab3:
    st.subheader("Performance Metrics")

    perf_data = pd.DataFrame([
        {"Metric": "Total Return", "Portfolio": "+8.3%", "Benchmark (SPY)": "+5.2%", "Active": "+3.1%"},
        {"Metric": "Annualized Return", "Portfolio": "+18.5%", "Benchmark (SPY)": "+11.8%", "Active": "+6.7%"},
        {"Metric": "Volatility", "Portfolio": "14.2%", "Benchmark (SPY)": "12.8%", "Active": "+1.4%"},
        {"Metric": "Sharpe Ratio", "Portfolio": "1.52", "Benchmark (SPY)": "1.12", "Active": "+0.40"},
        {"Metric": "Sortino Ratio", "Portfolio": "2.10", "Benchmark (SPY)": "1.55", "Active": "+0.55"},
        {"Metric": "Max Drawdown", "Portfolio": "-5.8%", "Benchmark (SPY)": "-7.2%", "Active": "+1.4%"},
        {"Metric": "Win Rate", "Portfolio": "62%", "Benchmark (SPY)": "—", "Active": "—"},
        {"Metric": "Profit Factor", "Portfolio": "1.85", "Benchmark (SPY)": "—", "Active": "—"},
    ])
    st.dataframe(perf_data, use_container_width=True, hide_index=True)

    st.markdown("#### Monthly Returns")
    monthly_data = pd.DataFrame([
        {"Month": "Jan 2026", "Return": "+3.2%", "Benchmark": "+1.8%", "Active": "+1.4%"},
        {"Month": "Dec 2025", "Return": "+2.5%", "Benchmark": "+1.5%", "Active": "+1.0%"},
        {"Month": "Nov 2025", "Return": "-1.2%", "Benchmark": "-0.8%", "Active": "-0.4%"},
        {"Month": "Oct 2025", "Return": "+4.1%", "Benchmark": "+2.9%", "Active": "+1.2%"},
    ])
    st.dataframe(monthly_data, use_container_width=True, hide_index=True)

# --- Tab 4: Compare Sessions ---
with tab4:
    st.subheader("Session Comparison")

    comparison_data = pd.DataFrame([
        {"Session": "Momentum Strategy", "Return": "+12.5%", "Sharpe": "1.65",
         "Max DD": "-6.2%", "Win Rate": "58%", "Trades": "42", "Rank": 1},
        {"Session": "Equal Weight", "Return": "+8.3%", "Sharpe": "1.52",
         "Max DD": "-5.8%", "Win Rate": "62%", "Trades": "24", "Rank": 2},
        {"Session": "Factor-Based", "Return": "+6.1%", "Sharpe": "1.15",
         "Max DD": "-8.5%", "Win Rate": "55%", "Trades": "36", "Rank": 3},
    ])
    st.dataframe(comparison_data, use_container_width=True, hide_index=True)

    st.markdown("#### Best by Metric")
    best_data = pd.DataFrame([
        {"Metric": "Total Return", "Winner": "Momentum Strategy"},
        {"Metric": "Sharpe Ratio", "Winner": "Momentum Strategy"},
        {"Metric": "Max Drawdown", "Winner": "Equal Weight"},
        {"Metric": "Win Rate", "Winner": "Equal Weight"},
    ])
    st.dataframe(best_data, use_container_width=True, hide_index=True)
