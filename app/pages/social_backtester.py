"""Social Signal Backtester Dashboard (PRD-161).

4 tabs: Signal Archive, Outcome Validation, Correlation Analysis, Backtest.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Social Backtester", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

st.title("Social Signal Backtester")
st.caption("Validate social signals against historical price data")

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Archive",
    "Outcome Validation",
    "Correlation Analysis",
    "Backtest",
])


# ── Tab 1: Signal Archive ─────────────────────────────────────────────

with tab1:
    st.subheader("Archived Social Signals")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Signals", "1,247")
    m2.metric("Avg Score", "62.4")
    m3.metric("Date Range", "2024-01 to 2025-04")

    st.divider()
    st.subheader("Recent Signals")
    np.random.seed(99)
    n_signals = 20
    tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD"]
    platforms = ["twitter", "reddit", "stocktwits", "news"]
    directions = ["bullish", "bearish", "neutral"]
    base_date = datetime(2025, 4, 1)

    archive_df = pd.DataFrame({
        "Timestamp": [
            (base_date - timedelta(hours=i * 4)).strftime("%Y-%m-%d %H:%M")
            for i in range(n_signals)
        ],
        "Ticker": np.random.choice(tickers, n_signals),
        "Platform": np.random.choice(platforms, n_signals),
        "Direction": np.random.choice(directions, n_signals, p=[0.5, 0.3, 0.2]),
        "Score": np.random.randint(25, 95, n_signals),
        "Mentions": np.random.randint(5, 500, n_signals),
    })
    st.dataframe(archive_df, use_container_width=True)

    st.subheader("Direction Distribution")
    dist_data = pd.DataFrame({
        "Direction": ["bullish", "bearish", "neutral"],
        "Count": [623, 374, 250],
    }).set_index("Direction")
    st.bar_chart(dist_data)


# ── Tab 2: Outcome Validation ────────────────────────────────────────

with tab2:
    st.subheader("Signal Predictiveness by Horizon")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("1-Day Hit Rate", "54.2%", "+4.2% vs random")
    with col2:
        st.metric("5-Day Hit Rate", "61.8%", "+11.8% vs random")
    with col3:
        st.metric("30-Day Hit Rate", "58.3%", "+8.3% vs random")

    st.divider()
    st.subheader("High vs Low Score Comparison")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**High-Score Signals (>70)**")
        m1, m2, m3 = st.columns(3)
        m1.metric("1d Hit", "62.1%")
        m2.metric("5d Hit", "71.4%")
        m3.metric("30d Hit", "66.8%")
    with col2:
        st.markdown("**Low-Score Signals (<40)**")
        m1, m2, m3 = st.columns(3)
        m1.metric("1d Hit", "48.3%")
        m2.metric("5d Hit", "50.7%")
        m3.metric("30d Hit", "49.1%")

    st.divider()
    st.subheader("Per-Ticker Hit Rates (5-Day Horizon)")
    ticker_hit_data = {
        "Ticker": ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD"],
        "Signals": [185, 162, 198, 210, 145, 130, 112, 105],
        "1d Hit": ["56.2%", "53.1%", "58.6%", "49.5%", "55.9%", "54.6%", "52.7%", "57.1%"],
        "5d Hit": ["64.3%", "62.3%", "68.2%", "55.7%", "63.4%", "60.0%", "58.0%", "65.7%"],
        "30d Hit": ["60.5%", "59.3%", "63.1%", "52.4%", "58.6%", "57.7%", "56.3%", "62.9%"],
        "Avg Score": [64, 61, 68, 55, 63, 60, 58, 66],
    }
    st.dataframe(pd.DataFrame(ticker_hit_data), use_container_width=True)


# ── Tab 3: Correlation Analysis ──────────────────────────────────────

with tab3:
    st.subheader("Social Signal vs Price Movement Correlation")

    # Demo lag analysis
    lags = list(range(0, 11))
    np.random.seed(77)
    correlations = [0.08, 0.15, 0.22, 0.31, 0.28, 0.19, 0.14, 0.10, 0.07, 0.05, 0.03]
    lag_df = pd.DataFrame({
        "Lag (days)": lags,
        "Correlation": correlations,
    }).set_index("Lag (days)")
    st.line_chart(lag_df)

    st.info("Peak correlation at **lag 3 days** (r=0.31) -- social signals lead price by ~3 trading days")

    st.divider()
    st.subheader("Significant Correlations (p < 0.05)")
    sig_corr_data = {
        "Lag": [1, 2, 3, 4, 5],
        "Correlation": [0.15, 0.22, 0.31, 0.28, 0.19],
        "p-value": [0.032, 0.008, 0.001, 0.003, 0.021],
        "Significant": [True, True, True, True, True],
    }
    st.dataframe(pd.DataFrame(sig_corr_data), use_container_width=True)

    st.divider()
    st.subheader("Optimal Lag per Ticker")
    opt_lag_data = {
        "Ticker": ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD"],
        "Optimal Lag": [3, 2, 3, 4, 3, 2, 5, 3],
        "Peak Corr": [0.34, 0.28, 0.38, 0.22, 0.30, 0.26, 0.19, 0.35],
        "p-value": [0.001, 0.006, 0.0003, 0.028, 0.002, 0.009, 0.041, 0.001],
    }
    st.dataframe(pd.DataFrame(opt_lag_data), use_container_width=True)


# ── Tab 4: Backtest ──────────────────────────────────────────────────

with tab4:
    st.subheader("Social Signal Strategy Backtest")

    col1, col2 = st.columns(2)
    with col1:
        min_score = st.slider("Min Signal Score", 0, 100, 60, key="bt_score")
        direction_filter = st.selectbox(
            "Direction Filter",
            ["bullish_only", "bearish_only", "all"],
            key="bt_dir",
        )
        max_positions = st.number_input("Max Positions", value=10, step=1, key="bt_maxpos")
    with col2:
        stop_loss = st.number_input("Stop Loss (%)", value=5.0, step=0.5, key="bt_sl")
        take_profit = st.number_input("Take Profit (%)", value=10.0, step=0.5, key="bt_tp")
        initial_capital = st.number_input(
            "Initial Capital ($)", value=100_000, step=10_000, key="bt_cap"
        )

    if st.button("Run Backtest", type="primary", use_container_width=True):
        st.info("Social signal backtest engine ready. Running with demo data.")

        st.divider()
        st.subheader("Key Metrics")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sharpe Ratio", "1.42")
        m2.metric("Max Drawdown", "-9.8%")
        m3.metric("Win Rate", "61.4%")
        m4.metric("Total Return", "+24.6%")

        # Demo equity curve
        np.random.seed(55)
        n_days = 252
        dates_idx = pd.bdate_range(start=date(2024, 1, 2), periods=n_days)
        daily_ret = np.random.normal(0.0004, 0.012, n_days)
        equity = initial_capital * np.cumprod(1 + daily_ret)
        equity_df = pd.DataFrame({"Equity ($)": equity}, index=dates_idx)

        st.subheader("Equity Curve")
        st.line_chart(equity_df)

        # Trade log
        st.subheader("Trade Log (Recent)")
        trade_log = {
            "Date": ["2024-11-05", "2024-11-08", "2024-11-12", "2024-11-15",
                      "2024-11-19", "2024-11-22", "2024-11-26", "2024-12-02"],
            "Ticker": ["NVDA", "AAPL", "TSLA", "AMD", "META", "MSFT", "GOOGL", "AMZN"],
            "Direction": ["long", "long", "short", "long", "long", "long", "short", "long"],
            "Entry": [480.2, 176.3, 242.8, 138.5, 520.1, 372.4, 164.9, 185.6],
            "Exit": [502.5, 182.1, 238.1, 145.2, 535.8, 368.9, 158.2, 194.3],
            "P&L": [2230, 580, 470, 670, 1570, -350, 670, 870],
            "Signal Score": [82, 71, 74, 68, 79, 62, 73, 65],
        }
        st.dataframe(pd.DataFrame(trade_log), use_container_width=True)

        # Drawdown chart
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak
        dd_df = pd.DataFrame({"Drawdown": dd}, index=dates_idx)
        st.subheader("Drawdown")
        st.area_chart(dd_df)
