"""PRD-176: Adaptive Feedback Dashboard.

4 tabs: Current Weights, Weight History, Source Performance, Adjustment Log.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Adaptive Feedback", page_icon="\U0001f504", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f504 Adaptive Feedback")
st.caption("Closed-loop signal weight optimization with rolling performance tracking and Sharpe-proportional allocation")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.signal_feedback.tracker import PerformanceTracker
    from src.signal_feedback.adjuster import WeightAdjuster
    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False

np.random.seed(176)
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

SOURCES = ["ema_cloud", "social", "momentum", "volume", "breakout", "mean_reversion"]

# Current weights
current_weights = {
    "ema_cloud": 0.27,
    "social": 0.11,
    "momentum": 0.23,
    "volume": 0.14,
    "breakout": 0.15,
    "mean_reversion": 0.10,
}

# Previous weights (for delta)
previous_weights = {
    "ema_cloud": 0.25,
    "social": 0.15,
    "momentum": 0.20,
    "volume": 0.15,
    "breakout": 0.15,
    "mean_reversion": 0.10,
}

# Per-source performance data
source_perf = {}
for src in SOURCES:
    n_trades = int(np.random.randint(30, 200))
    wins = int(n_trades * np.random.uniform(0.42, 0.70))
    win_pnls = np.random.uniform(30, 500, wins)
    loss_pnls = np.random.uniform(-350, -20, n_trades - wins)
    all_pnls = np.concatenate([win_pnls, loss_pnls])
    np.random.shuffle(all_pnls)

    gross_profit = float(np.sum(win_pnls))
    gross_loss = float(abs(np.sum(loss_pnls)))

    source_perf[src] = {
        "trades": n_trades,
        "wins": wins,
        "win_rate": round(wins / n_trades * 100, 1),
        "total_pnl": round(float(np.sum(all_pnls)), 2),
        "avg_pnl": round(float(np.mean(all_pnls)), 2),
        "sharpe": round(float(np.mean(all_pnls) / np.std(all_pnls)) * np.sqrt(252), 2) if np.std(all_pnls) > 0 else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0,
        "max_winning_streak": int(np.random.randint(3, 12)),
        "max_losing_streak": int(np.random.randint(2, 8)),
        "avg_holding_min": round(float(np.random.uniform(5, 90)), 0),
    }

# Weight history (30 adjustment cycles)
n_cycles = 30
weight_history = {}
for src in SOURCES:
    base = previous_weights[src]
    drift = np.random.normal(0, 0.008, n_cycles).cumsum()
    weights_over_time = np.clip(base + drift, 0.04, 0.40)
    # Normalize each cycle
    weight_history[src] = weights_over_time

# Normalize across sources per cycle
for i in range(n_cycles):
    total = sum(weight_history[s][i] for s in SOURCES)
    for s in SOURCES:
        weight_history[s][i] = round(weight_history[s][i] / total, 4)

# Adjustment log
n_adjustments = 25
adjustment_log = []
for i in range(n_adjustments):
    ts = NOW - timedelta(hours=int(np.random.randint(1, 720)))
    src = np.random.choice(SOURCES)
    old_w = round(float(np.random.uniform(0.08, 0.30)), 3)
    sharpe_val = round(float(np.random.uniform(-0.5, 3.0)), 2)

    if sharpe_val > 1.5:
        factor = 1.15
        reason = "Strong Sharpe, increase weight"
    elif sharpe_val > 0.5:
        factor = 1.05
        reason = "Positive Sharpe, slight increase"
    elif sharpe_val > 0:
        factor = 0.95
        reason = "Weak Sharpe, slight decrease"
    else:
        factor = 0.80
        reason = "Negative Sharpe, significant decrease"

    new_w = round(old_w * factor, 3)

    adjustment_log.append({
        "Timestamp": ts.strftime("%Y-%m-%d %H:%M"),
        "Source": src,
        "Old Weight": old_w,
        "New Weight": new_w,
        "Delta": round(new_w - old_w, 4),
        "Sharpe": sharpe_val,
        "Reason": reason,
        "Cycle": n_adjustments - i,
    })
adjustment_log.sort(key=lambda a: a["Timestamp"], reverse=True)

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Current Weights",
    "Weight History",
    "Source Performance",
    "Adjustment Log",
])

# =====================================================================
# Tab 1 - Current Weights
# =====================================================================
with tab1:
    st.subheader("Current Signal Source Weights")

    if not FEEDBACK_AVAILABLE:
        st.info("Signal feedback module not installed. Showing demo weight data.")

    # Summary metrics
    total_weight = sum(current_weights.values())
    max_source = max(current_weights, key=current_weights.get)
    min_source = min(current_weights, key=current_weights.get)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Sources", len(SOURCES))
    c2.metric("Total Weight", f"{total_weight:.2f}")
    c3.metric("Highest Weight", f"{max_source} ({current_weights[max_source]:.1%})")
    c4.metric("Lowest Weight", f"{min_source} ({current_weights[min_source]:.1%})")

    st.markdown("---")
    st.markdown("#### Weight Distribution")

    weight_chart = pd.DataFrame({
        "Weight": list(current_weights.values()),
    }, index=list(current_weights.keys()))
    st.bar_chart(weight_chart)

    st.markdown("---")
    st.markdown("#### Current vs Previous Weights")

    comparison_df = pd.DataFrame({
        "Previous": list(previous_weights.values()),
        "Current": list(current_weights.values()),
    }, index=list(current_weights.keys()))
    st.bar_chart(comparison_df)

    st.markdown("---")
    st.markdown("#### Weight Detail")

    detail_rows = []
    for src in SOURCES:
        curr = current_weights[src]
        prev = previous_weights[src]
        delta = curr - prev
        if delta > 0.005:
            direction = "Increased"
        elif delta < -0.005:
            direction = "Decreased"
        else:
            direction = "Unchanged"
        detail_rows.append({
            "Source": src,
            "Previous Weight": f"{prev:.1%}",
            "Current Weight": f"{curr:.1%}",
            "Delta": f"{delta:+.1%}",
            "Direction": direction,
            "Sharpe": source_perf[src]["sharpe"],
        })
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

# =====================================================================
# Tab 2 - Weight History
# =====================================================================
with tab2:
    st.subheader("Weight Evolution Over Time")

    cycle_labels = [f"Cycle {i + 1}" for i in range(n_cycles)]
    history_df = pd.DataFrame({
        src: weight_history[src] for src in SOURCES
    }, index=cycle_labels)
    st.line_chart(history_df)

    st.markdown("---")
    st.subheader("Weight Snapshots")

    snapshot_indices = [0, 5, 10, 15, 20, 25, 29]
    snapshot_rows = []
    for i in snapshot_indices:
        if i < n_cycles:
            row = {"Cycle": i + 1}
            for src in SOURCES:
                row[src] = f"{weight_history[src][i]:.1%}"
            snapshot_rows.append(row)
    st.dataframe(pd.DataFrame(snapshot_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Most Stable Source")
        stabilities = {src: float(np.std(weight_history[src])) for src in SOURCES}
        most_stable = min(stabilities, key=stabilities.get)
        st.metric(most_stable, f"Std Dev: {stabilities[most_stable]:.4f}")
        st.caption("Lower standard deviation indicates more consistent weight allocation.")

    with col_right:
        st.markdown("#### Most Volatile Source")
        most_volatile = max(stabilities, key=stabilities.get)
        st.metric(most_volatile, f"Std Dev: {stabilities[most_volatile]:.4f}")
        st.caption("Higher standard deviation indicates more responsive weight adjustments.")

    st.markdown("---")
    st.markdown("#### Weight Stability Ranking")
    stability_df = pd.DataFrame({
        "Std Dev": list(stabilities.values()),
    }, index=list(stabilities.keys()))
    st.bar_chart(stability_df)

# =====================================================================
# Tab 3 - Source Performance
# =====================================================================
with tab3:
    st.subheader("Per-Source Performance Metrics")

    total_trades = sum(source_perf[s]["trades"] for s in SOURCES)
    total_pnl = sum(source_perf[s]["total_pnl"] for s in SOURCES)
    avg_sharpe = round(np.mean([source_perf[s]["sharpe"] for s in SOURCES]), 2)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Trades", f"{total_trades:,}")
    c2.metric("Total P&L", f"${total_pnl:,.2f}")
    c3.metric("Avg Sharpe", f"{avg_sharpe:.2f}")

    st.markdown("---")

    perf_rows = []
    for src in SOURCES:
        d = source_perf[src]
        perf_rows.append({
            "Source": src,
            "Trades": d["trades"],
            "Wins": d["wins"],
            "Win Rate": f"{d['win_rate']:.1f}%",
            "Total P&L": f"${d['total_pnl']:,.2f}",
            "Avg P&L": f"${d['avg_pnl']:,.2f}",
            "Sharpe": d["sharpe"],
            "Profit Factor": d["profit_factor"],
            "Max Win Streak": d["max_winning_streak"],
            "Max Loss Streak": d["max_losing_streak"],
        })
    st.dataframe(pd.DataFrame(perf_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Sharpe Ratio by Source")
        sharpe_chart = pd.DataFrame({
            "Sharpe": [source_perf[s]["sharpe"] for s in SOURCES],
        }, index=SOURCES)
        st.bar_chart(sharpe_chart)

    with col_right:
        st.markdown("#### Total P&L by Source")
        pnl_chart = pd.DataFrame({
            "Total P&L": [source_perf[s]["total_pnl"] for s in SOURCES],
        }, index=SOURCES)
        st.bar_chart(pnl_chart)

    st.markdown("---")
    best_src = max(SOURCES, key=lambda s: source_perf[s]["sharpe"])
    worst_src = min(SOURCES, key=lambda s: source_perf[s]["sharpe"])

    col1, col2 = st.columns(2)
    with col1:
        st.success(
            f"Best: **{best_src}** -- Sharpe {source_perf[best_src]['sharpe']:.2f}, "
            f"Win Rate {source_perf[best_src]['win_rate']:.1f}%"
        )
    with col2:
        st.error(
            f"Worst: **{worst_src}** -- Sharpe {source_perf[worst_src]['sharpe']:.2f}, "
            f"Win Rate {source_perf[worst_src]['win_rate']:.1f}%"
        )

# =====================================================================
# Tab 4 - Adjustment Log
# =====================================================================
with tab4:
    st.subheader("Weight Adjustment Log")

    total_adjustments = len(adjustment_log)
    increases = sum(1 for a in adjustment_log if a["Delta"] > 0)
    decreases = sum(1 for a in adjustment_log if a["Delta"] < 0)
    avg_delta = round(np.mean([abs(a["Delta"]) for a in adjustment_log]), 4)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Adjustments", total_adjustments)
    c2.metric("Increases", increases)
    c3.metric("Decreases", decreases)
    c4.metric("Avg Abs Delta", f"{avg_delta:.4f}")

    st.markdown("---")

    # Filter by source
    log_source = st.selectbox(
        "Filter by Source",
        ["All"] + SOURCES,
        key="log_source_filter",
    )

    filtered_log = adjustment_log
    if log_source != "All":
        filtered_log = [a for a in adjustment_log if a["Source"] == log_source]

    log_df = pd.DataFrame([{
        "Timestamp": a["Timestamp"],
        "Cycle": a["Cycle"],
        "Source": a["Source"],
        "Old Weight": f"{a['Old Weight']:.1%}",
        "New Weight": f"{a['New Weight']:.1%}",
        "Delta": f"{a['Delta']:+.2%}",
        "Sharpe": a["Sharpe"],
        "Reason": a["Reason"],
    } for a in filtered_log])
    st.dataframe(log_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Adjustments by Source")
        source_adj_counts = pd.Series([a["Source"] for a in adjustment_log]).value_counts()
        st.bar_chart(source_adj_counts)

    with col_right:
        st.markdown("#### Adjustment Reasons")
        reason_counts = pd.Series([a["Reason"] for a in adjustment_log]).value_counts()
        st.bar_chart(reason_counts)

    st.markdown("---")
    st.subheader("Feedback Loop Configuration")
    config = {
        "rolling_window_trades": 50,
        "min_trades_for_adjustment": 20,
        "adjustment_frequency": "Every 50 trades per source",
        "sharpe_increase_threshold": 1.5,
        "sharpe_decrease_threshold": 0.0,
        "max_weight_change_per_cycle": 0.05,
        "min_weight": 0.05,
        "max_weight": 0.40,
        "normalization": "Sharpe-proportional",
    }
    st.json(config)
