"""Signal Feedback Dashboard (PRD-166).

4 tabs: Source Performance, Weight Adjustments, Rolling Metrics, Weight History.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Signal Feedback", page_icon="🔄", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🔄 Signal Feedback")
st.caption("Closed-loop performance tracking with adaptive weight adjustment")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(166)

SOURCES = ["ema_cloud", "social", "momentum", "volume", "breakout", "mean_reversion"]

# Generate per-source trade data
trade_counts = [185, 120, 95, 78, 62, 50]
source_data = {}
for src, count in zip(SOURCES, trade_counts):
    wins = int(count * np.random.uniform(0.48, 0.68))
    losses = count - wins
    win_pnls = np.random.uniform(50, 500, wins)
    loss_pnls = np.random.uniform(-300, -30, losses)
    all_pnls = np.concatenate([win_pnls, loss_pnls])
    np.random.shuffle(all_pnls)
    source_data[src] = {
        "trades": count,
        "wins": wins,
        "pnls": all_pnls,
        "total_pnl": float(np.sum(all_pnls)),
        "avg_pnl": float(np.mean(all_pnls)),
        "win_rate": wins / count,
    }

# Compute Sharpe and Profit Factor per source
for src in SOURCES:
    d = source_data[src]
    pnls = d["pnls"]
    d["sharpe"] = float(np.mean(pnls) / np.std(pnls)) * np.sqrt(252) if np.std(pnls) > 0 else 0.0
    gross_profit = float(np.sum(pnls[pnls > 0]))
    gross_loss = float(abs(np.sum(pnls[pnls < 0])))
    d["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else 0.0

# Weight data
old_weights = {"ema_cloud": 0.25, "social": 0.15, "momentum": 0.20,
               "volume": 0.15, "breakout": 0.15, "mean_reversion": 0.10}


def compute_new_weight(src):
    d = source_data[src]
    factor = 1.0
    if d["sharpe"] > 1.5:
        factor = 1.15
    elif d["sharpe"] > 0.5:
        factor = 1.05
    elif d["sharpe"] < 0:
        factor = 0.80
    else:
        factor = 0.95
    return round(old_weights[src] * factor, 3)


new_weights = {src: compute_new_weight(src) for src in SOURCES}
# Normalize
total_w = sum(new_weights.values())
new_weights = {src: round(w / total_w, 3) for src, w in new_weights.items()}

# Rolling metrics data (50 data points per source)
n_rolling = 50
rolling_data = {}
for src in SOURCES:
    d = source_data[src]
    base_sharpe = d["sharpe"] / (np.sqrt(252) if d["sharpe"] != 0 else 1)
    rolling_sharpes = np.random.normal(base_sharpe, 0.3, n_rolling).cumsum() / np.arange(1, n_rolling + 1) * np.sqrt(252)
    rolling_winrates = np.random.uniform(
        max(0.3, d["win_rate"] - 0.1),
        min(0.9, d["win_rate"] + 0.1),
        n_rolling,
    )
    rolling_pfs = np.random.uniform(
        max(0.5, d["profit_factor"] - 0.3),
        d["profit_factor"] + 0.3,
        n_rolling,
    )
    rolling_data[src] = {
        "sharpe": rolling_sharpes,
        "win_rate": rolling_winrates,
        "profit_factor": rolling_pfs,
    }

# Weight history (20 adjustment cycles)
n_cycles = 20
weight_history = {}
for src in SOURCES:
    base = old_weights[src]
    drift = np.random.normal(0, 0.01, n_cycles).cumsum()
    weights_over_time = np.clip(base + drift, 0.05, 0.40)
    weight_history[src] = weights_over_time

# ═══════════════════════════════════════════════════════════════════════
# Dashboard Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Source Performance",
    "Weight Adjustments",
    "Rolling Metrics",
    "Weight History",
])


# ── Tab 1: Source Performance ──────────────────────────────────────────

with tab1:
    st.subheader("Per-Source Performance Metrics")

    m1, m2, m3 = st.columns(3)
    total_trades = sum(source_data[s]["trades"] for s in SOURCES)
    total_pnl = sum(source_data[s]["total_pnl"] for s in SOURCES)
    avg_sharpe = np.mean([source_data[s]["sharpe"] for s in SOURCES])
    m1.metric("Total Trades", f"{total_trades:,}")
    m2.metric("Total P&L", f"${total_pnl:,.2f}")
    m3.metric("Avg Sharpe", f"{avg_sharpe:.2f}")

    st.divider()

    perf_rows = []
    for src in SOURCES:
        d = source_data[src]
        perf_rows.append({
            "Source": src,
            "Trade Count": d["trades"],
            "Win Count": d["wins"],
            "Win Rate": f"{d['win_rate']:.1%}",
            "Total P&L": f"${d['total_pnl']:,.2f}",
            "Avg P&L": f"${d['avg_pnl']:,.2f}",
            "Sharpe Ratio": f"{d['sharpe']:.2f}",
            "Profit Factor": f"{d['profit_factor']:.2f}",
        })

    st.dataframe(pd.DataFrame(perf_rows), use_container_width=True)

    # Highlights
    best_src = max(SOURCES, key=lambda s: source_data[s]["sharpe"])
    worst_src = min(SOURCES, key=lambda s: source_data[s]["sharpe"])
    col1, col2 = st.columns(2)
    with col1:
        st.success(
            f"Best: **{best_src}** -- Sharpe {source_data[best_src]['sharpe']:.2f}, "
            f"Win Rate {source_data[best_src]['win_rate']:.1%}"
        )
    with col2:
        st.error(
            f"Worst: **{worst_src}** -- Sharpe {source_data[worst_src]['sharpe']:.2f}, "
            f"Win Rate {source_data[worst_src]['win_rate']:.1%}"
        )


# ── Tab 2: Weight Adjustments ─────────────────────────────────────────

with tab2:
    st.subheader("Current vs Recommended Weights")

    weight_chart_df = pd.DataFrame({
        "Old Weight": [old_weights[s] for s in SOURCES],
        "New Weight": [new_weights[s] for s in SOURCES],
    }, index=SOURCES)
    st.bar_chart(weight_chart_df)

    st.divider()
    st.subheader("Adjustment Details")

    adj_rows = []
    for src in SOURCES:
        old_w = old_weights[src]
        new_w = new_weights[src]
        diff = new_w - old_w
        if diff > 0.005:
            action = "Increase"
        elif diff < -0.005:
            action = "Decrease"
        else:
            action = "Hold"
        d = source_data[src]
        adj_rows.append({
            "Source": src,
            "Action": action,
            "Sharpe": f"{d['sharpe']:.2f}",
            "Profit Factor": f"{d['profit_factor']:.2f}",
            "Old Weight": f"{old_w:.1%}",
            "New Weight": f"{new_w:.1%}",
        })

    st.dataframe(pd.DataFrame(adj_rows), use_container_width=True)

    increased = sum(1 for r in adj_rows if r["Action"] == "Increase")
    decreased = sum(1 for r in adj_rows if r["Action"] == "Decrease")
    col1, col2 = st.columns(2)
    col1.metric("Sources Increased", increased)
    col2.metric("Sources Decreased", decreased)


# ── Tab 3: Rolling Metrics ────────────────────────────────────────────

with tab3:
    st.subheader("Rolling Performance Metrics")

    st.markdown("**Rolling Sharpe Ratio (annualized)**")
    sharpe_df = pd.DataFrame({
        src: rolling_data[src]["sharpe"] for src in SOURCES
    })
    st.line_chart(sharpe_df)

    st.divider()
    st.markdown("**Rolling Win Rate**")
    winrate_df = pd.DataFrame({
        src: rolling_data[src]["win_rate"] for src in SOURCES
    })
    st.line_chart(winrate_df)

    st.divider()
    st.markdown("**Rolling Profit Factor**")
    pf_df = pd.DataFrame({
        src: rolling_data[src]["profit_factor"] for src in SOURCES
    })
    st.line_chart(pf_df)


# ── Tab 4: Weight History ─────────────────────────────────────────────

with tab4:
    st.subheader("Weight Evolution Over Time")

    cycle_labels = [f"Cycle {i+1}" for i in range(n_cycles)]
    history_df = pd.DataFrame({
        src: weight_history[src] for src in SOURCES
    }, index=cycle_labels)
    st.line_chart(history_df)

    st.divider()
    st.subheader("Weight Snapshots")

    snapshot_rows = []
    for i in [0, 4, 9, 14, 19]:
        row = {"Cycle": i + 1}
        for src in SOURCES:
            row[src] = f"{weight_history[src][i]:.1%}"
        snapshot_rows.append(row)

    st.dataframe(pd.DataFrame(snapshot_rows).set_index("Cycle"), use_container_width=True)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Most Stable Source**")
        stabilities = {src: float(np.std(weight_history[src])) for src in SOURCES}
        most_stable = min(stabilities, key=stabilities.get)
        st.metric(most_stable, f"Std: {stabilities[most_stable]:.4f}")
    with col2:
        st.markdown("**Most Volatile Source**")
        most_volatile = max(stabilities, key=stabilities.get)
        st.metric(most_volatile, f"Std: {stabilities[most_volatile]:.4f}")
