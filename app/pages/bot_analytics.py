"""PRD-175: Bot Analytics Dashboard.

4 tabs: Equity Curve, Metrics, Signal Breakdown, Strategy Comparison.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Bot Analytics", page_icon="\U0001f4c8", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f4c8 Bot Analytics")
st.caption("Equity curve, risk-adjusted metrics, per-signal-type performance, and strategy comparison")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.bot_pipeline.orchestrator import BotOrchestrator
    BOT_AVAILABLE = True
except ImportError:
    BOT_AVAILABLE = False

try:
    from src.trade_attribution.attributor import TradeAttributor
    ATTRIBUTION_AVAILABLE = True
except ImportError:
    ATTRIBUTION_AVAILABLE = False

np.random.seed(175)
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

# Equity curve data (90 trading days)
n_days = 90
initial_equity = 100000.0
daily_returns = np.random.normal(0.0008, 0.012, n_days)
equity_values = [initial_equity]
for r in daily_returns:
    equity_values.append(equity_values[-1] * (1 + r))
equity_values = equity_values[1:]

trading_dates = pd.date_range(end=NOW, periods=n_days, freq="B")
daily_pnl = np.diff([initial_equity] + equity_values)
cumulative_pnl = np.cumsum(daily_pnl)

# Running drawdown
peak = np.maximum.accumulate(equity_values)
drawdown = (np.array(equity_values) - peak) / peak * 100

# Key metrics
final_equity = equity_values[-1]
total_return_pct = (final_equity - initial_equity) / initial_equity * 100
annualized_return = ((final_equity / initial_equity) ** (252 / n_days) - 1) * 100
daily_vol = np.std(daily_returns) * np.sqrt(252) * 100
sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0

# Sortino
downside_returns = daily_returns[daily_returns < 0]
downside_vol = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 1
sortino = (np.mean(daily_returns) * 252) / (downside_vol) if downside_vol > 0 else 0

max_drawdown = float(np.min(drawdown))
calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

# Win/loss stats
winning_days = sum(1 for d in daily_pnl if d > 0)
losing_days = sum(1 for d in daily_pnl if d <= 0)
win_rate = winning_days / n_days * 100
avg_win = float(np.mean([d for d in daily_pnl if d > 0])) if winning_days > 0 else 0
avg_loss = float(np.mean([d for d in daily_pnl if d <= 0])) if losing_days > 0 else 0
profit_factor = abs(sum(d for d in daily_pnl if d > 0) / sum(d for d in daily_pnl if d <= 0)) if sum(d for d in daily_pnl if d <= 0) != 0 else 0

# Signal type breakdown
SIGNAL_TYPES = [
    "ema_cloud_bullish", "ema_cloud_bearish", "cloud_expansion",
    "momentum_breakout", "volume_spike", "mean_reversion_long",
    "mean_reversion_short", "social_sentiment", "fusion_composite",
]

signal_performance = []
for sig_type in SIGNAL_TYPES:
    n_trades = int(np.random.randint(15, 120))
    wins = int(n_trades * np.random.uniform(0.40, 0.72))
    win_pnls = np.random.uniform(30, 600, wins)
    loss_pnls = np.random.uniform(-400, -20, n_trades - wins)
    all_pnls = np.concatenate([win_pnls, loss_pnls])

    total_pnl = float(np.sum(all_pnls))
    avg_pnl = float(np.mean(all_pnls))
    gross_profit = float(np.sum(win_pnls))
    gross_loss = float(abs(np.sum(loss_pnls)))
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    sig_sharpe = float(np.mean(all_pnls) / np.std(all_pnls)) * np.sqrt(252) if np.std(all_pnls) > 0 else 0
    avg_holding = round(float(np.random.uniform(5, 120)), 0)

    signal_performance.append({
        "Signal Type": sig_type,
        "Trades": n_trades,
        "Wins": wins,
        "Win Rate": round(wins / n_trades * 100, 1),
        "Total P&L": round(total_pnl, 2),
        "Avg P&L": round(avg_pnl, 2),
        "Profit Factor": round(pf, 2),
        "Sharpe": round(sig_sharpe, 2),
        "Avg Holding (min)": int(avg_holding),
    })

# Strategy comparison
STRATEGIES = ["EMA Cloud", "Mean Reversion", "Momentum", "Social", "Fusion"]
strategy_comparison = []
for strat in STRATEGIES:
    n_trades = int(np.random.randint(40, 200))
    wins = int(n_trades * np.random.uniform(0.45, 0.68))
    win_pnls = np.random.uniform(40, 500, wins)
    loss_pnls = np.random.uniform(-350, -25, n_trades - wins)
    all_pnls = np.concatenate([win_pnls, loss_pnls])

    total_pnl = float(np.sum(all_pnls))
    gross_profit = float(np.sum(win_pnls))
    gross_loss = float(abs(np.sum(loss_pnls)))
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    strat_sharpe = float(np.mean(all_pnls) / np.std(all_pnls)) * np.sqrt(252) if np.std(all_pnls) > 0 else 0

    # Generate cumulative P&L for chart
    np.random.shuffle(all_pnls)
    cum_pnl = np.cumsum(all_pnls)

    strategy_comparison.append({
        "name": strat,
        "trades": n_trades,
        "wins": wins,
        "win_rate": round(wins / n_trades * 100, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(float(np.mean(all_pnls)), 2),
        "profit_factor": round(pf, 2),
        "sharpe": round(strat_sharpe, 2),
        "max_drawdown": round(float(np.min(cum_pnl) - np.max(cum_pnl[:np.argmin(cum_pnl) + 1])) if len(cum_pnl) > 1 else 0, 2),
        "cum_pnl": cum_pnl,
    })

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Equity Curve",
    "Metrics",
    "Signal Breakdown",
    "Strategy Comparison",
])

# =====================================================================
# Tab 1 - Equity Curve
# =====================================================================
with tab1:
    st.subheader("Equity Curve")

    if not BOT_AVAILABLE:
        st.info("Bot pipeline module not installed. Showing demo equity data.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Equity", f"${final_equity:,.2f}", delta=f"{total_return_pct:+.2f}%")
    c2.metric("Total P&L", f"${final_equity - initial_equity:,.2f}")
    c3.metric("Max Drawdown", f"{max_drawdown:.2f}%")
    c4.metric("Win Rate", f"{win_rate:.1f}%")

    st.markdown("---")

    # Equity curve chart
    equity_df = pd.DataFrame({
        "Equity": equity_values,
    }, index=trading_dates)
    st.line_chart(equity_df)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Daily P&L")
        pnl_df = pd.DataFrame({
            "Daily P&L": [round(float(p), 2) for p in daily_pnl],
        }, index=trading_dates)
        st.bar_chart(pnl_df)

    with col_right:
        st.markdown("#### Drawdown")
        dd_df = pd.DataFrame({
            "Drawdown (%)": [round(float(d), 2) for d in drawdown],
        }, index=trading_dates)
        st.line_chart(dd_df)

    st.markdown("---")
    st.markdown("#### Monthly Returns")
    monthly_returns = []
    for month_start in pd.date_range(start=trading_dates[0], end=trading_dates[-1], freq="MS"):
        month_end = month_start + pd.offsets.MonthEnd(1)
        mask = (trading_dates >= month_start) & (trading_dates <= month_end)
        if mask.any():
            month_ret = float(np.sum(daily_returns[mask]) * 100)
            monthly_returns.append({
                "Month": month_start.strftime("%Y-%m"),
                "Return (%)": round(month_ret, 2),
            })
    st.dataframe(pd.DataFrame(monthly_returns), use_container_width=True, hide_index=True)

# =====================================================================
# Tab 2 - Metrics
# =====================================================================
with tab2:
    st.subheader("Risk-Adjusted Performance Metrics")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Return Metrics")
        st.metric("Total Return", f"{total_return_pct:.2f}%")
        st.metric("Annualized Return", f"{annualized_return:.2f}%")
        st.metric("Annualized Volatility", f"{daily_vol:.2f}%")
        st.metric("Total P&L", f"${final_equity - initial_equity:,.2f}")

        st.markdown("---")
        st.markdown("#### Risk-Adjusted Ratios")
        st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        st.metric("Sortino Ratio", f"{sortino:.2f}")
        st.metric("Calmar Ratio", f"{calmar:.2f}")
        st.metric("Profit Factor", f"{profit_factor:.2f}")

    with col_right:
        st.markdown("#### Drawdown Metrics")
        st.metric("Max Drawdown", f"{max_drawdown:.2f}%")
        st.metric("Current Drawdown", f"{drawdown[-1]:.2f}%")
        avg_dd = float(np.mean(drawdown[drawdown < 0])) if np.any(drawdown < 0) else 0
        st.metric("Avg Drawdown", f"{avg_dd:.2f}%")
        dd_duration = int(np.random.randint(3, 15))
        st.metric("Longest DD Duration", f"{dd_duration} days")

        st.markdown("---")
        st.markdown("#### Win/Loss Statistics")
        st.metric("Win Rate", f"{win_rate:.1f}%")
        st.metric("Winning Days", winning_days)
        st.metric("Losing Days", losing_days)
        st.metric("Avg Win", f"${avg_win:,.2f}")
        st.metric("Avg Loss", f"${avg_loss:,.2f}")

    st.markdown("---")
    st.subheader("Performance Summary")
    summary = {
        "initial_equity": initial_equity,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_trading_days": n_days,
        "avg_daily_pnl": round(float(np.mean(daily_pnl)), 2),
    }
    st.json(summary)

# =====================================================================
# Tab 3 - Signal Breakdown
# =====================================================================
with tab3:
    st.subheader("Per-Signal-Type Performance")

    if not ATTRIBUTION_AVAILABLE:
        st.info("Trade attribution module not installed. Showing demo signal breakdown.")

    total_signal_trades = sum(s["Trades"] for s in signal_performance)
    total_signal_pnl = sum(s["Total P&L"] for s in signal_performance)
    best_signal = max(signal_performance, key=lambda s: s["Sharpe"])
    worst_signal = min(signal_performance, key=lambda s: s["Sharpe"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trades", total_signal_trades)
    c2.metric("Total P&L", f"${total_signal_pnl:,.2f}")
    c3.metric("Best Signal", f"{best_signal['Signal Type']}")
    c4.metric("Best Sharpe", f"{best_signal['Sharpe']:.2f}")

    st.markdown("---")
    st.dataframe(pd.DataFrame(signal_performance), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### P&L by Signal Type")
        pnl_chart = pd.DataFrame({
            "Total P&L": [s["Total P&L"] for s in signal_performance],
        }, index=[s["Signal Type"] for s in signal_performance])
        st.bar_chart(pnl_chart)

    with col_right:
        st.markdown("#### Win Rate by Signal Type")
        wr_chart = pd.DataFrame({
            "Win Rate (%)": [s["Win Rate"] for s in signal_performance],
        }, index=[s["Signal Type"] for s in signal_performance])
        st.bar_chart(wr_chart)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.success(
            f"Best: **{best_signal['Signal Type']}** -- "
            f"Sharpe {best_signal['Sharpe']:.2f}, Win Rate {best_signal['Win Rate']:.1f}%, "
            f"P&L ${best_signal['Total P&L']:,.2f}"
        )
    with col2:
        st.error(
            f"Worst: **{worst_signal['Signal Type']}** -- "
            f"Sharpe {worst_signal['Sharpe']:.2f}, Win Rate {worst_signal['Win Rate']:.1f}%, "
            f"P&L ${worst_signal['Total P&L']:,.2f}"
        )

# =====================================================================
# Tab 4 - Strategy Comparison
# =====================================================================
with tab4:
    st.subheader("Per-Strategy Performance Comparison")

    best_strat = max(strategy_comparison, key=lambda s: s["sharpe"])
    total_strat_pnl = sum(s["total_pnl"] for s in strategy_comparison)

    c1, c2, c3 = st.columns(3)
    c1.metric("Strategies Tracked", len(strategy_comparison))
    c2.metric("Total P&L (All)", f"${total_strat_pnl:,.2f}")
    c3.metric("Best Strategy", f"{best_strat['name']} (Sharpe: {best_strat['sharpe']:.2f})")

    st.markdown("---")

    # Comparison table
    comp_rows = []
    for s in strategy_comparison:
        comp_rows.append({
            "Strategy": s["name"],
            "Trades": s["trades"],
            "Wins": s["wins"],
            "Win Rate": f"{s['win_rate']:.1f}%",
            "Total P&L": f"${s['total_pnl']:,.2f}",
            "Avg P&L": f"${s['avg_pnl']:,.2f}",
            "Profit Factor": f"{s['profit_factor']:.2f}",
            "Sharpe": f"{s['sharpe']:.2f}",
        })
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Cumulative P&L by Strategy")

    max_len = max(len(s["cum_pnl"]) for s in strategy_comparison)
    cum_pnl_data = {}
    for s in strategy_comparison:
        padded = np.pad(s["cum_pnl"], (0, max_len - len(s["cum_pnl"])), mode="edge")
        cum_pnl_data[s["name"]] = padded
    cum_pnl_df = pd.DataFrame(cum_pnl_data)
    st.line_chart(cum_pnl_df)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Sharpe Ratio Comparison")
        sharpe_df = pd.DataFrame({
            "Sharpe": [s["sharpe"] for s in strategy_comparison],
        }, index=[s["name"] for s in strategy_comparison])
        st.bar_chart(sharpe_df)

    with col_right:
        st.markdown("#### Win Rate Comparison")
        wr_df = pd.DataFrame({
            "Win Rate (%)": [s["win_rate"] for s in strategy_comparison],
        }, index=[s["name"] for s in strategy_comparison])
        st.bar_chart(wr_df)

    best_overall = max(strategy_comparison, key=lambda s: s["total_pnl"])
    st.success(f"Top performing strategy: **{best_overall['name']}** with total P&L of ${best_overall['total_pnl']:,.2f}")
