"""Bot Pipeline & Robustness Dashboard (PRD-170).

4 tabs: Pipeline Health, Order Validation, Position Reconciliation, State Management.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Bot Pipeline", page_icon="\U0001f512", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f512 Bot Pipeline & Robustness")
st.caption("Hardened trading pipeline with order validation, state persistence, and position reconciliation")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(170)

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD"]
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001f4ca Pipeline Health",
    "\u2705 Order Validation",
    "\U0001f504 Position Reconciliation",
    "\U0001f6e1\ufe0f State Management",
])

# =====================================================================
# Tab 1 - Pipeline Health
# =====================================================================
with tab1:
    st.subheader("Pipeline Health Overview")

    total_signals = int(np.random.randint(800, 1200))
    success_count = int(total_signals * np.random.uniform(0.88, 0.95))
    success_rate = round(success_count / total_signals * 100, 1)
    open_positions = len(TICKERS)
    daily_pnl = round(float(np.random.uniform(-500, 2500)), 2)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Signals Processed", f"{total_signals:,}")
    c2.metric("Success Rate", f"{success_rate}%")
    c3.metric("Open Positions", open_positions)
    c4.metric("Daily P&L", f"${daily_pnl:,.2f}", delta=f"{'+'if daily_pnl>=0 else ''}{daily_pnl:,.2f}")

    st.markdown("---")
    st.markdown("#### Pipeline Stage Breakdown")

    stages = ["signal_received", "kill_switch", "risk_assessment", "order_placed",
              "fill_validation", "completed", "rejected"]
    stage_counts = [total_signals,
                    total_signals - int(np.random.randint(5, 20)),
                    total_signals - int(np.random.randint(30, 60)),
                    success_count + int(np.random.randint(10, 30)),
                    success_count + int(np.random.randint(2, 10)),
                    success_count,
                    total_signals - success_count]
    stage_df = pd.DataFrame({
        "Stage": stages,
        "Count": stage_counts,
        "Pct of Total": [round(c / total_signals * 100, 1) for c in stage_counts],
    })
    st.dataframe(stage_df, use_container_width=True, hide_index=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Rejection Reasons")
        reasons = ["kill_switch_active", "max_position_limit", "insufficient_margin",
                   "high_slippage", "stale_signal", "circuit_breaker_open", "risk_limit_exceeded"]
        reason_counts = np.random.randint(2, 35, size=len(reasons))
        reason_df = pd.DataFrame({"Reason": reasons, "Count": reason_counts.tolist()})
        reason_df = reason_df.sort_values("Count", ascending=False).reset_index(drop=True)
        st.bar_chart(reason_df.set_index("Reason")["Count"])

    with col_right:
        st.markdown("#### Pipeline Throughput (Last 24h)")
        hours = pd.date_range(end=NOW, periods=24, freq="h")
        throughput = np.random.poisson(lam=40, size=24).tolist()
        tp_df = pd.DataFrame({"Time": hours, "Signals": throughput}).set_index("Time")
        st.line_chart(tp_df)

# =====================================================================
# Tab 2 - Order Validation
# =====================================================================
with tab2:
    st.subheader("Order Validation & Fill Analysis")

    n_orders = 50
    total_orders = n_orders
    statuses = np.random.choice(["filled", "partial_fill", "rejected", "cancelled"],
                                size=n_orders, p=[0.72, 0.12, 0.10, 0.06])
    filled_count = int((statuses == "filled").sum() + (statuses == "partial_fill").sum())
    fill_rate = round(filled_count / n_orders * 100, 1)
    slippages = np.random.normal(0.05, 0.15, size=n_orders)
    avg_slippage = round(float(np.mean(np.abs(slippages))), 3)
    rejected_fills = int((statuses == "rejected").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total_orders)
    c2.metric("Fill Rate", f"{fill_rate}%")
    c3.metric("Avg Slippage", f"{avg_slippage}%")
    c4.metric("Rejected Fills", rejected_fills)

    st.markdown("---")
    st.markdown("#### Order Validation History")

    order_ids = [f"ORD-{170000 + i}" for i in range(n_orders)]
    tickers = np.random.choice(TICKERS, size=n_orders).tolist()
    expected_qtys = np.random.randint(10, 200, size=n_orders)
    filled_qtys = []
    fill_prices = []
    is_valid_list = []
    reason_list = []

    for i in range(n_orders):
        s = statuses[i]
        eq = int(expected_qtys[i])
        if s == "filled":
            fq = eq
            is_valid_list.append(True)
            reason_list.append("ok")
        elif s == "partial_fill":
            fq = int(eq * np.random.uniform(0.3, 0.9))
            is_valid_list.append(False)
            reason_list.append("partial_fill_below_threshold")
        elif s == "rejected":
            fq = 0
            is_valid_list.append(False)
            reason_list.append(np.random.choice(["price_moved", "insufficient_liquidity", "stale_quote"]))
        else:
            fq = 0
            is_valid_list.append(False)
            reason_list.append("user_cancelled")
        filled_qtys.append(fq)
        base_price = round(float(np.random.uniform(50, 500)), 2)
        fill_prices.append(base_price if fq > 0 else 0.0)

    orders_df = pd.DataFrame({
        "order_id": order_ids,
        "ticker": tickers,
        "status": statuses.tolist(),
        "expected_qty": expected_qtys.tolist(),
        "filled_qty": filled_qtys,
        "fill_price": fill_prices,
        "slippage_pct": [round(float(s), 4) for s in slippages],
        "is_valid": is_valid_list,
        "reason": reason_list,
    })
    st.dataframe(orders_df, use_container_width=True, hide_index=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Slippage Distribution")
        slip_hist = pd.DataFrame({"slippage_pct": slippages.tolist()})
        st.bar_chart(slip_hist["slippage_pct"].value_counts(bins=20).sort_index())

    with col_right:
        st.markdown("#### Partial Fill Analysis")
        partial_df = orders_df[orders_df["status"] == "partial_fill"].copy()
        if not partial_df.empty:
            partial_df["fill_ratio"] = (partial_df["filled_qty"] / partial_df["expected_qty"]).round(2)
            st.dataframe(
                partial_df[["order_id", "ticker", "expected_qty", "filled_qty", "fill_ratio"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("No partial fills in current window.")

# =====================================================================
# Tab 3 - Position Reconciliation
# =====================================================================
with tab3:
    st.subheader("Position Reconciliation")

    last_recon = (NOW - timedelta(minutes=int(np.random.randint(1, 15)))).strftime("%Y-%m-%d %H:%M:%S")
    matched = len(TICKERS) - int(np.random.randint(0, 2))
    ghosts_found = int(np.random.choice([0, 0, 0, 1], p=[0.6, 0.15, 0.15, 0.1]))
    orphaned_found = int(np.random.choice([0, 0, 1], p=[0.6, 0.2, 0.2]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last Reconciliation", last_recon)
    c2.metric("Matched", matched)
    c3.metric("Ghosts Found", ghosts_found)
    c4.metric("Orphaned Found", orphaned_found)

    st.markdown("---")
    st.markdown("#### Current Reconciliation Report")

    recon_rows = []
    for t in TICKERS:
        internal_qty = int(np.random.randint(10, 200))
        broker_qty = internal_qty if np.random.random() > 0.15 else internal_qty + int(np.random.choice([-5, 5, -10, 10]))
        diff = broker_qty - internal_qty
        status = "matched" if diff == 0 else "mismatch"
        severity = "none"
        if diff != 0:
            severity = np.random.choice(["critical", "high", "medium", "low"])
        recon_rows.append({
            "ticker": t,
            "internal_qty": internal_qty,
            "broker_qty": broker_qty,
            "diff": diff,
            "status": status,
            "severity": severity,
            "last_checked": last_recon,
        })
    recon_df = pd.DataFrame(recon_rows)
    st.dataframe(recon_df, use_container_width=True, hide_index=True)

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Historical Reconciliation Results (Last 30 Days)")
        dates = pd.date_range(end=NOW, periods=30, freq="D")
        matched_hist = np.random.randint(6, 9, size=30)
        mismatched_hist = 8 - matched_hist
        hist_df = pd.DataFrame({
            "Date": dates,
            "Matched": matched_hist.tolist(),
            "Mismatched": mismatched_hist.tolist(),
        }).set_index("Date")
        st.line_chart(hist_df)

    with col_right:
        st.markdown("#### Mismatch Severity Breakdown")
        severity_levels = ["critical", "high", "medium", "low"]
        severity_counts = [int(np.random.randint(0, 3)),
                           int(np.random.randint(1, 5)),
                           int(np.random.randint(2, 8)),
                           int(np.random.randint(3, 12))]
        sev_df = pd.DataFrame({"Severity": severity_levels, "Count": severity_counts})
        st.bar_chart(sev_df.set_index("Severity")["Count"])

# =====================================================================
# Tab 4 - State Management
# =====================================================================
with tab4:
    st.subheader("State Management & Circuit Breakers")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Kill Switch Status")
        kill_switch_active = bool(np.random.choice([False, False, False, True]))
        if kill_switch_active:
            st.error("\U0001f534 Kill Switch: **ACTIVE** - All trading halted")
        else:
            st.success("\U0001f7e2 Kill Switch: **INACTIVE** - Trading enabled")

        st.markdown("#### Circuit Breaker Status")
        cb_state = str(np.random.choice(["closed", "closed", "closed", "half_open", "open"],
                                        p=[0.6, 0.15, 0.1, 0.1, 0.05]))
        if cb_state == "closed":
            st.success(f"\U0001f7e2 Circuit Breaker: **{cb_state.upper()}** - Normal operation")
        elif cb_state == "half_open":
            st.warning(f"\U0001f7e1 Circuit Breaker: **{cb_state.upper()}** - Testing recovery")
        else:
            st.error(f"\U0001f534 Circuit Breaker: **{cb_state.upper()}** - Trading suspended")

        st.markdown("#### Consecutive Loss Counter")
        consec_losses = int(np.random.randint(0, 5))
        max_consec = 5
        st.metric("Consecutive Losses", f"{consec_losses} / {max_consec}")
        st.progress(min(consec_losses / max_consec, 1.0))
        if consec_losses >= max_consec:
            st.error("Maximum consecutive losses reached - kill switch will activate.")
        elif consec_losses >= max_consec - 1:
            st.warning("Approaching consecutive loss limit.")

    with col_right:
        st.markdown("#### Daily P&L Tracking")
        trading_days = pd.date_range(end=NOW, periods=20, freq="B")
        daily_pnls = np.random.normal(150, 600, size=20)
        running_total = np.cumsum(daily_pnls)
        pnl_df = pd.DataFrame({
            "Date": trading_days,
            "Daily P&L": [round(float(v), 2) for v in daily_pnls],
            "Running Total": [round(float(v), 2) for v in running_total],
        }).set_index("Date")
        st.line_chart(pnl_df)

        st.markdown("#### State Snapshot")
        state_snapshot = {
            "bot_status": "running" if not kill_switch_active else "halted",
            "circuit_breaker": cb_state,
            "kill_switch": kill_switch_active,
            "open_positions": len(TICKERS),
            "daily_pnl": round(float(daily_pnls[-1]), 2),
            "running_pnl": round(float(running_total[-1]), 2),
            "consecutive_losses": consec_losses,
            "max_consecutive_losses": max_consec,
            "last_signal_time": (NOW - timedelta(seconds=int(np.random.randint(10, 300)))).isoformat(),
            "uptime_hours": round(float(np.random.uniform(12, 72)), 1),
        }
        st.json(state_snapshot)

    st.markdown("---")
    st.markdown("#### Regime Transition History")
    n_transitions = 12
    transition_times = sorted([NOW - timedelta(hours=int(np.random.randint(1, 168))) for _ in range(n_transitions)])
    regimes = ["normal", "volatile", "trending_up", "trending_down", "low_liquidity", "crisis"]
    from_regimes = [np.random.choice(regimes) for _ in range(n_transitions)]
    to_regimes = []
    for fr in from_regimes:
        candidates = [r for r in regimes if r != fr]
        to_regimes.append(np.random.choice(candidates))

    transition_df = pd.DataFrame({
        "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in transition_times],
        "from_regime": from_regimes,
        "to_regime": to_regimes,
        "trigger": [np.random.choice(["volatility_spike", "drawdown_threshold", "volume_shift",
                                       "correlation_break", "scheduled_review", "manual_override"])
                    for _ in range(n_transitions)],
        "confidence": [round(float(np.random.uniform(0.55, 0.98)), 2) for _ in range(n_transitions)],
    })
    st.dataframe(transition_df, use_container_width=True, hide_index=True)
