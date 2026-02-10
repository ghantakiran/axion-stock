"""PRD-177: Multi-Strategy Dashboard.

4 tabs: Registry, Backtest, Comparison, Configuration.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Strategies", page_icon="\U0001f3af", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f3af Multi-Strategy Manager")
st.caption("Strategy registry, backtesting, cross-strategy comparison, and configuration management")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.strategy_optimizer.optimizer import StrategyOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False

try:
    from src.strategy_selector.selector import StrategySelector
    SELECTOR_AVAILABLE = True
except ImportError:
    SELECTOR_AVAILABLE = False

np.random.seed(177)
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

STRATEGIES = [
    {
        "id": "STRAT-001",
        "name": "VWAP Reversion",
        "type": "mean_reversion",
        "description": "Mean-reversion strategy anchored to VWAP. Enters when price deviates >1.5 std from VWAP and targets reversion.",
        "timeframe": "5m",
        "instruments": "Equities",
        "status": "Active",
        "created": "2025-10-15",
        "version": "2.1",
        "author": "quant_team",
        "params": {
            "vwap_deviation_threshold": 1.5,
            "take_profit_pct": 0.8,
            "stop_loss_pct": 0.5,
            "max_position_size": 1000,
            "min_volume": 100000,
            "session": "RTH",
        },
    },
    {
        "id": "STRAT-002",
        "name": "Opening Range Breakout (ORB)",
        "type": "breakout",
        "description": "Captures momentum from the first 15-minute opening range. Enters on breakout above/below range with volume confirmation.",
        "timeframe": "15m",
        "instruments": "Equities, ETFs",
        "status": "Active",
        "created": "2025-11-01",
        "version": "1.4",
        "author": "quant_team",
        "params": {
            "opening_range_minutes": 15,
            "breakout_buffer_pct": 0.1,
            "volume_multiplier": 1.5,
            "take_profit_pct": 1.5,
            "stop_loss_pct": 0.5,
            "max_position_size": 500,
            "session": "First 2 hours",
        },
    },
    {
        "id": "STRAT-003",
        "name": "RSI Divergence",
        "type": "mean_reversion",
        "description": "Detects bullish/bearish divergence between price and RSI. Enters on confirmation candle with tight risk management.",
        "timeframe": "1h",
        "instruments": "Equities, Crypto",
        "status": "Active",
        "created": "2025-12-01",
        "version": "1.2",
        "author": "research_team",
        "params": {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "divergence_lookback": 20,
            "take_profit_pct": 2.0,
            "stop_loss_pct": 1.0,
            "min_divergence_bars": 3,
        },
    },
    {
        "id": "STRAT-004",
        "name": "EMA Cloud Trend",
        "type": "trend_following",
        "description": "Ripster-style 4-layer EMA clouds for trend identification. Enters on cloud alignment with conviction scoring.",
        "timeframe": "5m",
        "instruments": "Equities, Options",
        "status": "Active",
        "created": "2025-09-01",
        "version": "3.0",
        "author": "bot_team",
        "params": {
            "ema_fast": [8, 9],
            "ema_slow": [20, 21],
            "ema_trend": [34, 50],
            "ema_long": [100, 200],
            "min_conviction": 60,
            "adx_threshold": 25,
        },
    },
    {
        "id": "STRAT-005",
        "name": "Momentum Scalper",
        "type": "momentum",
        "description": "High-frequency momentum captures on volume spikes. Targets quick 0.3-0.5% moves with sub-minute holding periods.",
        "timeframe": "1m",
        "instruments": "Equities, ETFs",
        "status": "Paused",
        "created": "2026-01-10",
        "version": "0.9",
        "author": "quant_team",
        "params": {
            "volume_spike_threshold": 3.0,
            "momentum_lookback": 5,
            "take_profit_pct": 0.4,
            "stop_loss_pct": 0.2,
            "max_hold_seconds": 120,
            "min_spread_ratio": 0.5,
        },
    },
]

# Backtest results per strategy
backtest_results = {}
for strat in STRATEGIES:
    n_trades = int(np.random.randint(50, 300))
    wins = int(n_trades * np.random.uniform(0.42, 0.68))
    win_pnls = np.random.uniform(20, 600, wins)
    loss_pnls = np.random.uniform(-400, -15, n_trades - wins)
    all_pnls = np.concatenate([win_pnls, loss_pnls])
    np.random.shuffle(all_pnls)
    cum_pnl = np.cumsum(all_pnls)

    gross_profit = float(np.sum(win_pnls))
    gross_loss = float(abs(np.sum(loss_pnls)))
    sharpe = float(np.mean(all_pnls) / np.std(all_pnls)) * np.sqrt(252) if np.std(all_pnls) > 0 else 0
    downside = all_pnls[all_pnls < 0]
    sortino = float(np.mean(all_pnls) * np.sqrt(252) / np.std(downside)) if len(downside) > 0 and np.std(downside) > 0 else 0
    max_dd = float(np.min(cum_pnl - np.maximum.accumulate(cum_pnl)))

    backtest_results[strat["id"]] = {
        "trades": n_trades,
        "wins": wins,
        "win_rate": round(wins / n_trades * 100, 1),
        "total_pnl": round(float(np.sum(all_pnls)), 2),
        "avg_pnl": round(float(np.mean(all_pnls)), 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        "max_drawdown": round(max_dd, 2),
        "cum_pnl": cum_pnl,
    }

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Registry",
    "Backtest",
    "Comparison",
    "Configuration",
])

# =====================================================================
# Tab 1 - Registry
# =====================================================================
with tab1:
    st.subheader("Registered Strategies")

    if not OPTIMIZER_AVAILABLE:
        st.info("Strategy optimizer module not installed. Showing demo registry data.")

    active_count = sum(1 for s in STRATEGIES if s["status"] == "Active")
    paused_count = sum(1 for s in STRATEGIES if s["status"] == "Paused")
    strategy_types = set(s["type"] for s in STRATEGIES)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Strategies", len(STRATEGIES))
    c2.metric("Active", active_count)
    c3.metric("Paused", paused_count)
    c4.metric("Strategy Types", len(strategy_types))

    st.markdown("---")

    registry_df = pd.DataFrame([{
        "ID": s["id"],
        "Name": s["name"],
        "Type": s["type"],
        "Timeframe": s["timeframe"],
        "Instruments": s["instruments"],
        "Status": s["status"],
        "Version": s["version"],
        "Created": s["created"],
    } for s in STRATEGIES])
    st.dataframe(registry_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Strategy Details")

    selected_strat = st.selectbox(
        "Select Strategy",
        options=[s["name"] for s in STRATEGIES],
        key="registry_select",
    )

    for s in STRATEGIES:
        if s["name"] == selected_strat:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{s['name']}** (`{s['id']}`)")
                st.markdown(f"_{s['description']}_")
                st.markdown(f"- **Type**: {s['type']}")
                st.markdown(f"- **Timeframe**: {s['timeframe']}")
                st.markdown(f"- **Instruments**: {s['instruments']}")
                st.markdown(f"- **Author**: {s['author']}")
                st.markdown(f"- **Version**: {s['version']}")
            with col2:
                st.markdown("**Parameters**")
                st.json(s["params"])
            break

# =====================================================================
# Tab 2 - Backtest
# =====================================================================
with tab2:
    st.subheader("Strategy Backtesting")

    selected_bt = st.selectbox(
        "Select Strategy to Backtest",
        options=[s["name"] for s in STRATEGIES],
        key="backtest_select",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        bt_start = st.date_input("Start Date", value=NOW - timedelta(days=180), key="bt_start")
    with col2:
        bt_end = st.date_input("End Date", value=NOW, key="bt_end")
    with col3:
        bt_capital = st.number_input("Initial Capital ($)", min_value=10000, max_value=1000000, value=100000, key="bt_capital")

    if st.button("Run Backtest", type="primary"):
        st.info("Backtest simulation running with demo data...")

    # Show results for selected strategy
    for s in STRATEGIES:
        if s["name"] == selected_bt:
            bt = backtest_results[s["id"]]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Trades", bt["trades"])
            c2.metric("Win Rate", f"{bt['win_rate']:.1f}%")
            c3.metric("Total P&L", f"${bt['total_pnl']:,.2f}")
            c4.metric("Sharpe Ratio", f"{bt['sharpe']:.2f}")

            st.markdown("---")
            st.markdown("#### Equity Curve")
            initial = bt_capital
            equity = initial + bt["cum_pnl"]
            equity_df = pd.DataFrame({"Equity ($)": equity})
            st.line_chart(equity_df)

            st.markdown("---")
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("#### Performance Summary")
                summary = {
                    "trades": bt["trades"],
                    "wins": bt["wins"],
                    "win_rate": bt["win_rate"],
                    "total_pnl": bt["total_pnl"],
                    "avg_pnl": bt["avg_pnl"],
                    "sharpe": bt["sharpe"],
                    "sortino": bt["sortino"],
                    "profit_factor": bt["profit_factor"],
                    "max_drawdown": bt["max_drawdown"],
                }
                st.json(summary)

            with col_right:
                st.markdown("#### Trade Distribution")
                trade_pnls = np.concatenate([
                    np.random.uniform(20, 600, bt["wins"]),
                    np.random.uniform(-400, -15, bt["trades"] - bt["wins"]),
                ])
                pnl_bins = pd.cut(trade_pnls, bins=20).value_counts().sort_index()
                st.bar_chart(pnl_bins)
            break

# =====================================================================
# Tab 3 - Comparison
# =====================================================================
with tab3:
    st.subheader("Strategy Performance Comparison")

    best_strat = max(STRATEGIES, key=lambda s: backtest_results[s["id"]]["sharpe"])
    best_bt = backtest_results[best_strat["id"]]

    c1, c2, c3 = st.columns(3)
    c1.metric("Strategies Compared", len(STRATEGIES))
    c2.metric("Best Strategy", best_strat["name"])
    c3.metric("Best Sharpe", f"{best_bt['sharpe']:.2f}")

    st.markdown("---")

    comp_rows = []
    for s in STRATEGIES:
        bt = backtest_results[s["id"]]
        comp_rows.append({
            "Strategy": s["name"],
            "Type": s["type"],
            "Trades": bt["trades"],
            "Win Rate": f"{bt['win_rate']:.1f}%",
            "Total P&L": f"${bt['total_pnl']:,.2f}",
            "Avg P&L": f"${bt['avg_pnl']:,.2f}",
            "Sharpe": bt["sharpe"],
            "Sortino": bt["sortino"],
            "Profit Factor": bt["profit_factor"],
            "Max Drawdown": f"${bt['max_drawdown']:,.2f}",
            "Status": s["status"],
        })
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Cumulative P&L Comparison")

    max_len = max(len(backtest_results[s["id"]]["cum_pnl"]) for s in STRATEGIES)
    cum_data = {}
    for s in STRATEGIES:
        pnl = backtest_results[s["id"]]["cum_pnl"]
        padded = np.pad(pnl, (0, max_len - len(pnl)), mode="edge")
        cum_data[s["name"]] = padded
    cum_df = pd.DataFrame(cum_data)
    st.line_chart(cum_df)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Sharpe Ratio Ranking")
        sharpe_df = pd.DataFrame({
            "Sharpe": [backtest_results[s["id"]]["sharpe"] for s in STRATEGIES],
        }, index=[s["name"] for s in STRATEGIES])
        st.bar_chart(sharpe_df)

    with col_right:
        st.markdown("#### Win Rate Ranking")
        wr_df = pd.DataFrame({
            "Win Rate (%)": [backtest_results[s["id"]]["win_rate"] for s in STRATEGIES],
        }, index=[s["name"] for s in STRATEGIES])
        st.bar_chart(wr_df)

    highest_pnl = max(STRATEGIES, key=lambda s: backtest_results[s["id"]]["total_pnl"])
    st.success(
        f"Highest P&L: **{highest_pnl['name']}** with ${backtest_results[highest_pnl['id']]['total_pnl']:,.2f} "
        f"(Sharpe: {backtest_results[highest_pnl['id']]['sharpe']:.2f})"
    )

# =====================================================================
# Tab 4 - Configuration
# =====================================================================
with tab4:
    st.subheader("Strategy Configuration")

    if not SELECTOR_AVAILABLE:
        st.info("Strategy selector module not installed. Showing demo configuration.")

    config_strat = st.selectbox(
        "Select Strategy to Configure",
        options=[s["name"] for s in STRATEGIES],
        key="config_select",
    )

    for s in STRATEGIES:
        if s["name"] == config_strat:
            st.markdown(f"#### {s['name']} Configuration")
            st.markdown(f"**Type**: {s['type']} | **Version**: {s['version']} | **Status**: {s['status']}")

            st.markdown("---")
            st.markdown("##### Current Parameters")

            col1, col2 = st.columns(2)
            params = s["params"]
            param_keys = list(params.keys())
            half = len(param_keys) // 2 + 1

            with col1:
                for key in param_keys[:half]:
                    val = params[key]
                    if isinstance(val, (int, float)):
                        st.number_input(
                            key.replace("_", " ").title(),
                            value=float(val) if isinstance(val, float) else val,
                            key=f"param_{s['id']}_{key}",
                        )
                    elif isinstance(val, list):
                        st.text_input(
                            key.replace("_", " ").title(),
                            value=str(val),
                            key=f"param_{s['id']}_{key}",
                        )
                    else:
                        st.text_input(
                            key.replace("_", " ").title(),
                            value=str(val),
                            key=f"param_{s['id']}_{key}",
                        )

            with col2:
                for key in param_keys[half:]:
                    val = params[key]
                    if isinstance(val, (int, float)):
                        st.number_input(
                            key.replace("_", " ").title(),
                            value=float(val) if isinstance(val, float) else val,
                            key=f"param_{s['id']}_{key}",
                        )
                    elif isinstance(val, list):
                        st.text_input(
                            key.replace("_", " ").title(),
                            value=str(val),
                            key=f"param_{s['id']}_{key}",
                        )
                    else:
                        st.text_input(
                            key.replace("_", " ").title(),
                            value=str(val),
                            key=f"param_{s['id']}_{key}",
                        )

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Save Configuration", type="primary", key=f"save_{s['id']}"):
                    st.success(f"Configuration for '{s['name']}' saved successfully")
            with col2:
                if st.button("Reset to Defaults", key=f"reset_{s['id']}"):
                    st.info("Parameters reset to default values")
            with col3:
                new_status = "Paused" if s["status"] == "Active" else "Active"
                if st.button(f"Set {new_status}", key=f"toggle_{s['id']}"):
                    st.success(f"Strategy status changed to {new_status}")

            st.markdown("---")
            st.markdown("##### Risk Controls")
            col1, col2 = st.columns(2)
            with col1:
                st.number_input("Max Daily Loss ($)", min_value=100, max_value=10000, value=2000, key=f"risk_maxloss_{s['id']}")
                st.number_input("Max Concurrent Positions", min_value=1, max_value=20, value=5, key=f"risk_maxpos_{s['id']}")
            with col2:
                st.number_input("Max Position Size ($)", min_value=1000, max_value=100000, value=10000, key=f"risk_possize_{s['id']}")
                st.number_input("Cooldown After Loss (min)", min_value=0, max_value=60, value=5, key=f"risk_cooldown_{s['id']}")
            break

    st.markdown("---")
    st.subheader("Global Strategy Settings")
    global_config = {
        "strategy_rotation_enabled": True,
        "rotation_frequency": "Daily",
        "regime_override_enabled": True,
        "adx_routing_threshold": 25,
        "max_strategies_active": 3,
        "capital_allocation_mode": "equal_weight",
        "backtest_before_activation": True,
        "min_sharpe_for_activation": 0.5,
    }
    st.json(global_config)
