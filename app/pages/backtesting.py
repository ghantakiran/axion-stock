"""Backtesting Engine Dashboard."""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

try:
    st.set_page_config(page_title="Backtesting Engine", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("Backtesting Engine")

# --- Sidebar ---
st.sidebar.header("Backtest Settings")

strategy = st.sidebar.selectbox(
    "Strategy",
    ["Equal Weight", "Momentum", "Mean Reversion", "Custom"],
)
start_date = st.sidebar.date_input("Start Date", date(2020, 1, 1))
end_date = st.sidebar.date_input("End Date", date(2024, 12, 31))
initial_capital = st.sidebar.number_input(
    "Initial Capital ($)", value=100_000, step=10_000,
)
rebalance = st.sidebar.selectbox(
    "Rebalance Frequency",
    ["Daily", "Weekly", "Monthly", "Quarterly"],
    index=2,
)

st.sidebar.markdown("---")
st.sidebar.subheader("Risk Rules")
max_position = st.sidebar.slider("Max Position (%)", 5, 50, 15) / 100
max_drawdown = st.sidebar.slider("Max Drawdown Halt (%)", 5, 50, 15) / 100
position_stop = st.sidebar.slider("Position Stop Loss (%)", 5, 30, 15) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("Cost Model")
commission_bps = st.sidebar.number_input("Commission (bps)", value=0.0, step=0.5)
slippage_bps = st.sidebar.number_input("Slippage (bps)", value=2.0, step=0.5)

# --- Main Content ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Run Backtest", "Trade Analysis", "Walk-Forward", "Strategy Comparison",
])

# --- Tab 1: Run Backtest ---
with tab1:
    st.subheader("Backtest Execution")

    symbols_input = st.text_input(
        "Symbols (comma-separated)",
        value="AAPL, MSFT, GOOGL, AMZN, META",
    )
    symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Running backtest..."):
            try:
                from src.backtesting import (
                    BacktestConfig, BacktestEngine, TearSheetGenerator,
                    RebalanceFrequency, RiskConfig, CostModelConfig,
                    Signal, OrderSide,
                )

                freq_map = {
                    "Daily": RebalanceFrequency.DAILY,
                    "Weekly": RebalanceFrequency.WEEKLY,
                    "Monthly": RebalanceFrequency.MONTHLY,
                    "Quarterly": RebalanceFrequency.QUARTERLY,
                }
                config = BacktestConfig(
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    rebalance_frequency=freq_map[rebalance],
                    risk_rules=RiskConfig(
                        max_position_pct=max_position,
                        max_drawdown_halt=-max_drawdown,
                        position_stop_loss=-position_stop,
                    ),
                    cost_model=CostModelConfig(
                        slippage_bps=slippage_bps,
                    ),
                )

                # Generate synthetic price data for demo
                rng = np.random.RandomState(42)
                n_days = (end_date - start_date).days
                dates = pd.bdate_range(start=start_date, periods=min(n_days, 1260))
                price_data = pd.DataFrame(
                    {
                        sym: 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(dates))))
                        for sym in symbols
                    },
                    index=dates,
                )

                # Build strategy
                target_w = min(1.0 / len(symbols), max_position)

                class DashboardStrategy:
                    def on_bar(self, event, portfolio):
                        signals = []
                        for sym in symbols:
                            if sym in event.bars:
                                w = portfolio.get_position_weight(sym)
                                if abs(w - target_w) > 0.03:
                                    signals.append(Signal(
                                        symbol=sym,
                                        timestamp=event.timestamp,
                                        side=OrderSide.BUY,
                                        target_weight=target_w,
                                    ))
                        return signals

                engine = BacktestEngine(config)
                engine.load_data(price_data)
                result = engine.run(DashboardStrategy())

                # Metrics
                m = result.metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Return", f"{m.total_return:.1%}")
                col2.metric("CAGR", f"{m.cagr:.1%}")
                col3.metric("Sharpe Ratio", f"{m.sharpe_ratio:.2f}")
                col4.metric("Max Drawdown", f"{m.max_drawdown:.1%}")

                col5, col6, col7, col8 = st.columns(4)
                col5.metric("Total Trades", str(m.total_trades))
                col6.metric("Win Rate", f"{m.win_rate:.0%}")
                col7.metric("Profit Factor", f"{m.profit_factor:.2f}")
                col8.metric("Total Costs", f"${m.total_costs:,.2f}")

                # Equity curve
                st.markdown("#### Equity Curve")
                eq_df = pd.DataFrame({"Equity": result.equity_curve})
                st.line_chart(eq_df)

                # Drawdown
                st.markdown("#### Drawdown")
                dd_df = pd.DataFrame({"Drawdown": result.drawdown_curve})
                st.area_chart(dd_df)

                # Tearsheet
                generator = TearSheetGenerator()
                tearsheet = generator.generate(result, strategy)
                with st.expander("Full Tear Sheet"):
                    st.text(tearsheet)

                st.session_state["backtest_result"] = result

            except Exception as e:
                st.error(f"Backtest failed: {e}")

# --- Tab 2: Trade Analysis ---
with tab2:
    st.subheader("Trade Analysis")

    result = st.session_state.get("backtest_result")
    if result and result.trades:
        trades_df = result.get_trades_df()
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### P&L Distribution")
            pnl_series = trades_df["pnl"]
            hist_data = pd.DataFrame({"P&L": pnl_series})
            st.bar_chart(hist_data.value_counts(bins=20).sort_index())

        with col2:
            st.markdown("#### Trade Duration")
            hold_data = pd.DataFrame({"Hold Days": trades_df["hold_days"]})
            st.bar_chart(hold_data.value_counts(bins=15).sort_index())
    else:
        st.info("Run a backtest first to see trade analysis.")

# --- Tab 3: Walk-Forward ---
with tab3:
    st.subheader("Walk-Forward Optimization")
    st.info("Walk-forward optimization splits the backtest period into "
            "in-sample (training) and out-of-sample (validation) windows.")

    n_windows = st.slider("Number of Windows", 2, 10, 4)
    is_pct = st.slider("In-Sample %", 50, 90, 70)

    if st.button("Run Walk-Forward"):
        with st.spinner("Running walk-forward optimization..."):
            st.markdown("#### Window Results (Demo)")
            wf_data = []
            rng = np.random.RandomState(42)
            for i in range(n_windows):
                is_sharpe = rng.uniform(0.8, 2.0)
                oos_sharpe = is_sharpe * rng.uniform(0.3, 0.9)
                wf_data.append({
                    "Window": i + 1,
                    "IS Sharpe": f"{is_sharpe:.2f}",
                    "OOS Sharpe": f"{oos_sharpe:.2f}",
                    "Efficiency": f"{oos_sharpe / is_sharpe:.0%}",
                })
            st.dataframe(pd.DataFrame(wf_data), use_container_width=True, hide_index=True)

            avg_eff = np.mean([float(r["Efficiency"].strip("%")) / 100 for r in wf_data])
            if avg_eff > 0.5:
                st.success(f"Average efficiency ratio: {avg_eff:.0%} — strategy shows robustness.")
            else:
                st.warning(f"Average efficiency ratio: {avg_eff:.0%} — possible overfitting.")

# --- Tab 4: Strategy Comparison ---
with tab4:
    st.subheader("Strategy Comparison")
    st.info("Compare multiple strategies side-by-side with proper benchmarking.")

    st.markdown("#### Strategy Rankings (Demo)")
    comparison_data = pd.DataFrame([
        {"Strategy": "Momentum", "Return": "18.2%", "Sharpe": "1.42",
         "Max DD": "-12.3%", "Win Rate": "54%", "Rank": 1},
        {"Strategy": "Equal Weight", "Return": "12.1%", "Sharpe": "1.18",
         "Max DD": "-9.8%", "Win Rate": "51%", "Rank": 2},
        {"Strategy": "Mean Reversion", "Return": "9.5%", "Sharpe": "0.95",
         "Max DD": "-14.1%", "Win Rate": "48%", "Rank": 3},
    ])
    st.dataframe(comparison_data, use_container_width=True, hide_index=True)

    st.markdown("#### Correlation Matrix")
    corr = pd.DataFrame(
        [[1.0, 0.62, -0.15], [0.62, 1.0, 0.31], [-0.15, 0.31, 1.0]],
        index=["Momentum", "Equal Weight", "Mean Reversion"],
        columns=["Momentum", "Equal Weight", "Mean Reversion"],
    )
    st.dataframe(corr.style.format("{:.2f}"), use_container_width=True)
