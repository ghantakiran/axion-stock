"""Bot Strategy Backtesting Dashboard (PRD-138).

4 tabs: Run Backtest, Signal Attribution, Walk-Forward, Replay Analysis.
"""

try:
    import streamlit as st
from app.styles import inject_global_styles
    st.set_page_config(page_title="Bot Backtesting", layout="wide")

inject_global_styles()
except Exception:
    import streamlit as st

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

st.title("Bot Strategy Backtesting")
st.caption("Validate EMA Cloud strategies against historical data before deploying live")

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Run Backtest",
    "Signal Attribution",
    "Walk-Forward",
    "Replay Analysis",
])


# ── Tab 1: Run Backtest ──────────────────────────────────────────────

with tab1:
    st.subheader("Configure & Run Backtest")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date(2022, 1, 1))
        capital = st.number_input("Initial Capital ($)", value=100_000, step=10_000)
        min_conv = st.slider("Min Conviction", 0, 100, 50)
    with col2:
        end_date = st.date_input("End Date", value=date(2024, 12, 31))
        max_pos = st.slider("Max Positions", 1, 20, 10)
        max_weight = st.slider("Max Position Weight (%)", 1, 30, 15) / 100

    default_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
                       "META", "TSLA", "JPM", "V", "JNJ"]
    tickers = st.multiselect(
        "Tickers",
        options=default_tickers + ["WMT", "PG", "MA", "UNH", "HD",
                                   "DIS", "PYPL", "NFLX", "ADBE", "CRM"],
        default=default_tickers,
    )

    signal_types = st.multiselect(
        "Enabled Signal Types",
        options=[
            "cloud_cross_bullish", "cloud_cross_bearish",
            "cloud_flip_bullish", "cloud_flip_bearish",
            "cloud_bounce_long", "cloud_bounce_short",
            "trend_aligned_long", "trend_aligned_short",
            "momentum_exhaustion", "mtf_confluence",
        ],
        default=[
            "cloud_cross_bullish", "cloud_flip_bullish",
            "cloud_bounce_long", "trend_aligned_long",
        ],
    )

    if st.button("Run Backtest", type="primary", use_container_width=True):
        st.info("Backtest engine ready. Connect OHLCV data source to run live backtests.")

        # Demo results
        st.divider()
        st.subheader("Results")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Return", "+18.4%")
        m2.metric("CAGR", "+8.7%")
        m3.metric("Sharpe Ratio", "1.24")
        m4.metric("Max Drawdown", "-12.3%")
        m5.metric("Win Rate", "58.2%")
        m6.metric("Total Trades", "147")

        # Demo equity curve
        dates_idx = pd.bdate_range(start=start_date, end=end_date)
        np.random.seed(42)
        returns = np.random.normal(0.0003, 0.01, len(dates_idx))
        equity = capital * np.cumprod(1 + returns)
        equity_df = pd.DataFrame({"Equity": equity}, index=dates_idx)
        st.line_chart(equity_df)

        # Demo drawdown
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak
        dd_df = pd.DataFrame({"Drawdown": dd}, index=dates_idx)
        st.area_chart(dd_df)

        # Demo trades table
        st.subheader("Recent Trades")
        trades_data = {
            "Symbol": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
            "Entry": ["$174.20", "$365.50", "$480.10", "$138.90", "$320.70"],
            "Exit": ["$182.40", "$358.20", "$502.30", "$145.60", "$312.50"],
            "PnL": ["$820", "-$730", "$2,220", "$670", "-$820"],
            "PnL %": ["+4.7%", "-2.0%", "+4.6%", "+4.8%", "-2.6%"],
            "Signal": ["Cloud Cross", "Cloud Flip", "Trend Aligned", "Bounce Long", "Cloud Cross"],
            "Hold Days": [5, 3, 8, 4, 2],
        }
        st.dataframe(pd.DataFrame(trades_data), use_container_width=True)


# ── Tab 2: Signal Attribution ─────────────────────────────────────────

with tab2:
    st.subheader("Signal Type Performance")

    # Demo attribution data
    attr_data = {
        "Signal Type": [
            "Cloud Cross Bullish", "Cloud Flip Bullish",
            "Trend Aligned Long", "Cloud Bounce Long",
            "Momentum Exhaustion",
        ],
        "Trades": [42, 35, 28, 25, 17],
        "Win Rate": ["61.9%", "54.3%", "67.9%", "56.0%", "41.2%"],
        "Total PnL": ["$4,230", "$1,850", "$5,120", "$2,410", "-$890"],
        "Avg PnL": ["$100.7", "$52.9", "$182.9", "$96.4", "-$52.4"],
        "Profit Factor": ["1.82", "1.31", "2.15", "1.54", "0.72"],
        "Avg Conviction": [62, 58, 71, 55, 48],
        "Avg Hold (days)": [4.2, 3.1, 6.8, 3.5, 2.1],
    }
    attr_df = pd.DataFrame(attr_data).set_index("Signal Type")

    st.dataframe(attr_df, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("PnL by Signal Type")
        pnl_data = pd.DataFrame({
            "Signal Type": attr_data["Signal Type"],
            "PnL ($)": [4230, 1850, 5120, 2410, -890],
        }).set_index("Signal Type")
        st.bar_chart(pnl_data)

    with col2:
        st.subheader("Trade Distribution")
        dist_df = pd.DataFrame({
            "Signal Type": attr_data["Signal Type"],
            "Trades": attr_data["Trades"],
        }).set_index("Signal Type")
        st.bar_chart(dist_df)

    # Best / Worst highlights
    col1, col2 = st.columns(2)
    with col1:
        st.success("Best: **Trend Aligned Long** — PF 2.15, 67.9% win rate, $5,120 total PnL")
    with col2:
        st.error("Worst: **Momentum Exhaustion** — PF 0.72, 41.2% win rate, -$890 total PnL")


# ── Tab 3: Walk-Forward ───────────────────────────────────────────────

with tab3:
    st.subheader("Walk-Forward Optimization")

    col1, col2, col3 = st.columns(3)
    with col1:
        n_windows = st.slider("Windows", 3, 10, 5)
    with col2:
        is_pct = st.slider("In-Sample %", 50, 80, 70)
    with col3:
        opt_metric = st.selectbox("Optimization Metric", ["Sharpe", "CAGR", "Sortino"])

    st.write("**Parameter Grid:**")
    col1, col2 = st.columns(2)
    with col1:
        conv_values = st.multiselect("Min Conviction", [30, 40, 50, 60, 70], default=[40, 50, 60])
    with col2:
        weight_values = st.multiselect("Max Weight %", [5, 10, 15, 20], default=[10, 15])

    if st.button("Run Walk-Forward", use_container_width=True):
        st.info("Walk-forward optimizer ready. Connect data to run.")

        # Demo results
        st.metric("Efficiency Ratio (OOS/IS Sharpe)", "0.62", help=">0.5 = robust")

        wf_data = {
            "Window": [1, 2, 3, 4, 5],
            "IS Sharpe": [1.45, 1.62, 1.38, 1.51, 1.29],
            "OOS Sharpe": [0.92, 1.05, 0.78, 0.98, 0.84],
            "Best Conv": [50, 50, 60, 50, 40],
            "Best Weight": [15, 10, 15, 15, 10],
        }
        st.dataframe(pd.DataFrame(wf_data).set_index("Window"), use_container_width=True)

        # IS vs OOS Sharpe comparison
        sharpe_df = pd.DataFrame({
            "In-Sample": wf_data["IS Sharpe"],
            "Out-of-Sample": wf_data["OOS Sharpe"],
        }, index=[f"W{i}" for i in wf_data["Window"]])
        st.bar_chart(sharpe_df)


# ── Tab 4: Replay Analysis ───────────────────────────────────────────

with tab4:
    st.subheader("Signal Replay Analysis")
    st.caption("Replay historical signals through different risk configurations")

    col1, col2, col3 = st.columns(3)
    with col1:
        replay_max_pos = st.slider("Max Concurrent Positions", 1, 20, 10, key="replay_pos")
    with col2:
        replay_daily_limit = st.slider("Daily Loss Limit (%)", 1, 20, 10, key="replay_limit") / 100
    with col3:
        replay_min_equity = st.number_input(
            "Min Account Equity ($)", value=25_000, step=5_000, key="replay_eq"
        )

    if st.button("Run Replay", use_container_width=True):
        st.info("Replay engine ready. Load historical signals to analyze.")

        # Demo results
        m1, m2, m3 = st.columns(3)
        m1.metric("Approval Rate", "72.4%")
        m2.metric("Approved", "108 / 149")
        m3.metric("Unique Rejections", "4 reasons")

        # Rejection reasons
        st.subheader("Rejection Reasons")
        reasons_df = pd.DataFrame({
            "Reason": ["Max positions reached", "Daily loss limit", "Duplicate ticker", "Min equity"],
            "Count": [22, 8, 7, 4],
        }).set_index("Reason")
        st.bar_chart(reasons_df)

        # Signal-by-signal table
        st.subheader("Signal-by-Signal Results")
        replay_data = {
            "Ticker": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AAPL", "TSLA"],
            "Signal": ["Cloud Cross", "Trend Aligned", "Cloud Flip", "Bounce", "Cloud Cross", "Duplicate", "Cloud Cross"],
            "Conviction": [72, 68, 61, 55, 64, 70, 58],
            "Approved": [True, True, True, True, True, False, False],
            "Reason": ["-", "-", "-", "-", "-", "Duplicate ticker", "Max positions"],
            "Size": [150, 120, 100, 80, 110, 0, 0],
        }
        st.dataframe(pd.DataFrame(replay_data), use_container_width=True)
