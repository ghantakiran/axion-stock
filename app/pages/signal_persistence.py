"""Signal Audit Trail Dashboard (PRD-162).

4 tabs: Signal Explorer, Fusion History, Risk Decisions, Pipeline Trace.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Signal Audit Trail", page_icon="🔍", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🔍 Signal Audit Trail")
st.caption("Full traceability from signal origin through fusion, risk, and execution")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(162)
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]
SOURCES = ["ema_cloud", "momentum", "volume", "breakout", "social", "mean_reversion"]
STATUSES = ["active", "fused", "executed", "expired", "rejected"]
base_time = datetime(2025, 4, 10, 9, 30)

n_signals = 50
demo_signals = pd.DataFrame({
    "signal_id": [f"SIG-{1000 + i}" for i in range(n_signals)],
    "timestamp": [(base_time + timedelta(minutes=i * 12)).strftime("%Y-%m-%d %H:%M") for i in range(n_signals)],
    "ticker": np.random.choice(TICKERS, n_signals),
    "source": np.random.choice(SOURCES, n_signals),
    "direction": np.random.choice(["long", "short"], n_signals, p=[0.65, 0.35]),
    "conviction": np.random.randint(30, 98, n_signals),
    "status": np.random.choice(STATUSES, n_signals, p=[0.15, 0.30, 0.25, 0.15, 0.15]),
})

n_fusions = 25
demo_fusions = pd.DataFrame({
    "fusion_id": [f"FUS-{500 + i}" for i in range(n_fusions)],
    "timestamp": [(base_time + timedelta(minutes=i * 25)).strftime("%Y-%m-%d %H:%M") for i in range(n_fusions)],
    "ticker": np.random.choice(TICKERS, n_fusions),
    "direction": np.random.choice(["long", "short"], n_fusions, p=[0.60, 0.40]),
    "composite_score": np.round(np.random.uniform(35.0, 95.0, n_fusions), 1),
    "agreement_ratio": np.round(np.random.uniform(0.40, 1.0, n_fusions), 2),
    "sources_count": np.random.randint(2, 6, n_fusions),
    "agreeing": np.random.randint(1, 5, n_fusions),
    "dissenting": np.random.randint(0, 3, n_fusions),
})

n_decisions = 30
reasons_approved = ["within_limits", "low_correlation", "regime_favorable", "size_ok"]
reasons_rejected = ["max_positions", "high_correlation", "drawdown_limit", "kill_switch", "vix_too_high"]
approved_flags = np.random.choice([True, False], n_decisions, p=[0.70, 0.30])
demo_decisions = pd.DataFrame({
    "decision_id": [f"RSK-{200 + i}" for i in range(n_decisions)],
    "timestamp": [(base_time + timedelta(minutes=i * 18)).strftime("%Y-%m-%d %H:%M") for i in range(n_decisions)],
    "fusion_id": [f"FUS-{500 + np.random.randint(0, n_fusions)}" for _ in range(n_decisions)],
    "ticker": np.random.choice(TICKERS, n_decisions),
    "approved": approved_flags,
    "reason": [
        np.random.choice(reasons_approved) if a else np.random.choice(reasons_rejected)
        for a in approved_flags
    ],
    "position_size_pct": np.round(np.random.uniform(0.5, 5.0, n_decisions), 1),
    "risk_score": np.random.randint(10, 90, n_decisions),
})

# ═══════════════════════════════════════════════════════════════════════
# Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Signal Explorer",
    "Fusion History",
    "Risk Decisions",
    "Pipeline Trace",
])

# ── Tab 1: Signal Explorer ────────────────────────────────────────────

with tab1:
    st.subheader("Signal Explorer")

    # Metric cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Signals", f"{n_signals}")
    m2.metric("Fused", len(demo_signals[demo_signals["status"] == "fused"]))
    m3.metric("Executed", len(demo_signals[demo_signals["status"] == "executed"]))
    m4.metric("Avg Conviction", f"{demo_signals['conviction'].mean():.1f}")

    st.divider()

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_ticker = st.selectbox(
            "Filter by Ticker", ["All"] + sorted(TICKERS), key="sig_ticker"
        )
    with col_f2:
        filter_source = st.selectbox(
            "Filter by Source", ["All"] + sorted(SOURCES), key="sig_source"
        )
    with col_f3:
        filter_status = st.selectbox(
            "Filter by Status", ["All"] + sorted(STATUSES), key="sig_status"
        )

    filtered = demo_signals.copy()
    if filter_ticker != "All":
        filtered = filtered[filtered["ticker"] == filter_ticker]
    if filter_source != "All":
        filtered = filtered[filtered["source"] == filter_source]
    if filter_status != "All":
        filtered = filtered[filtered["status"] == filter_status]

    st.dataframe(filtered, use_container_width=True)

    st.divider()
    st.subheader("Signals by Source")
    source_counts = demo_signals["source"].value_counts()
    st.bar_chart(source_counts)


# ── Tab 2: Fusion History ─────────────────────────────────────────────

with tab2:
    st.subheader("Fusion History")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Fusions", f"{n_fusions}")
    m2.metric("Avg Composite Score", f"{demo_fusions['composite_score'].mean():.1f}")
    m3.metric("Avg Agreement Ratio", f"{demo_fusions['agreement_ratio'].mean():.0%}")

    st.divider()
    st.dataframe(demo_fusions, use_container_width=True)

    st.divider()
    st.subheader("Composite Score Distribution")
    score_hist = pd.DataFrame({
        "Score": demo_fusions["composite_score"],
    })
    st.bar_chart(score_hist.value_counts(bins=10).sort_index())

    st.subheader("Agreement Ratio Over Time")
    agreement_chart = pd.DataFrame({
        "Agreement Ratio": demo_fusions["agreement_ratio"].values,
    }, index=range(n_fusions))
    st.line_chart(agreement_chart)


# ── Tab 3: Risk Decisions ─────────────────────────────────────────────

with tab3:
    st.subheader("Risk Gate Decisions")

    approved_count = demo_decisions["approved"].sum()
    rejected_count = n_decisions - approved_count

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Decisions", f"{n_decisions}")
    m2.metric("Approved", f"{approved_count}", f"{approved_count / n_decisions:.0%}")
    m3.metric("Rejected", f"{rejected_count}", f"-{rejected_count / n_decisions:.0%}")
    m4.metric("Avg Risk Score", f"{demo_decisions['risk_score'].mean():.0f}")

    st.divider()

    decision_view = st.selectbox(
        "Filter Decisions", ["All", "Approved Only", "Rejected Only"], key="dec_filter"
    )
    display_df = demo_decisions.copy()
    if decision_view == "Approved Only":
        display_df = display_df[display_df["approved"]]
    elif decision_view == "Rejected Only":
        display_df = display_df[~display_df["approved"]]

    st.dataframe(display_df, use_container_width=True)

    st.divider()
    st.subheader("Rejection Reasons")
    rejected_df = demo_decisions[~demo_decisions["approved"]]
    if len(rejected_df) > 0:
        reason_counts = rejected_df["reason"].value_counts()
        st.bar_chart(reason_counts)
    else:
        st.info("No rejected decisions in current data.")


# ── Tab 4: Pipeline Trace ─────────────────────────────────────────────

with tab4:
    st.subheader("End-to-End Pipeline Trace")
    st.markdown("Enter a signal ID to trace its full journey through the pipeline.")

    signal_ids = demo_signals["signal_id"].tolist()
    selected_id = st.selectbox("Select Signal ID", signal_ids, key="trace_sig_id")

    if st.button("Trace Pipeline", type="primary", use_container_width=True):
        # Look up signal
        sig_row = demo_signals[demo_signals["signal_id"] == selected_id].iloc[0]

        st.divider()

        # Stage 1: Signal
        st.markdown("### Stage 1: Signal Origin")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Signal ID", selected_id)
        c2.metric("Ticker", sig_row["ticker"])
        c3.metric("Source", sig_row["source"])
        c4.metric("Conviction", sig_row["conviction"])
        st.info(f"Direction: **{sig_row['direction']}** | Status: **{sig_row['status']}** | Time: {sig_row['timestamp']}")

        st.divider()

        # Stage 2: Fusion
        st.markdown("### Stage 2: Fusion")
        matching_fusions = demo_fusions[demo_fusions["ticker"] == sig_row["ticker"]]
        if len(matching_fusions) > 0:
            fus = matching_fusions.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Fusion ID", fus["fusion_id"])
            c2.metric("Composite Score", fus["composite_score"])
            c3.metric("Agreement", f"{fus['agreement_ratio']:.0%}")
            st.info(f"Sources: {fus['sources_count']} | Agreeing: {fus['agreeing']} | Dissenting: {fus['dissenting']}")
        else:
            st.warning("No fusion record found for this ticker.")

        st.divider()

        # Stage 3: Risk Decision
        st.markdown("### Stage 3: Risk Decision")
        matching_decisions = demo_decisions[demo_decisions["ticker"] == sig_row["ticker"]]
        if len(matching_decisions) > 0:
            dec = matching_decisions.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Decision ID", dec["decision_id"])
            c2.metric("Approved", "Yes" if dec["approved"] else "No")
            c3.metric("Risk Score", dec["risk_score"])
            if dec["approved"]:
                st.success(f"Approved -- Reason: {dec['reason']} | Position Size: {dec['position_size_pct']}%")
            else:
                st.error(f"Rejected -- Reason: {dec['reason']}")
        else:
            st.warning("No risk decision found for this ticker.")

        st.divider()

        # Stage 4: Execution
        st.markdown("### Stage 4: Execution")
        if sig_row["status"] == "executed":
            exec_price = round(np.random.uniform(150, 550), 2)
            exec_qty = np.random.randint(10, 200)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Exec Price", f"${exec_price}")
            c2.metric("Quantity", exec_qty)
            c3.metric("Fill Rate", "100%")
            c4.metric("Slippage", f"{round(np.random.uniform(0.01, 0.15), 3)}%")
            st.success("Trade executed successfully.")
        else:
            st.warning(f"Signal status is '{sig_row['status']}' -- not yet executed.")
