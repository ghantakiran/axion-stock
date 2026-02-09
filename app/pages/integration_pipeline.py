"""Pipeline Monitor Dashboard (PRD-169).

4 tabs: Pipeline Flow, Signal Trace, Module Health, Performance.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Pipeline Monitor", page_icon="🔗", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("🔗 Pipeline Monitor")
st.caption("End-to-end signal pipeline monitoring from generation through execution")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════
# Demo Data
# ═══════════════════════════════════════════════════════════════════════

np.random.seed(169)

# Pipeline flow counts
total_signals = 100
fused_count = 78
risk_approved = 62
executed_count = 55

# Signal trace data
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN", "AMD", "JPM", "V"]
SOURCES = ["ema_cloud", "social", "momentum", "volume", "breakout", "mean_reversion"]
DIRECTIONS = ["long", "short"]

signals = []
for i in range(total_signals):
    sig_id = f"SIG-{i+1:04d}"
    source = np.random.choice(SOURCES)
    ticker = np.random.choice(TICKERS)
    direction = np.random.choice(DIRECTIONS, p=[0.6, 0.4])
    strength = np.random.randint(30, 95)

    # Determine if fused
    is_fused = i < fused_count
    fusion_score = np.random.randint(40, 90) if is_fused else None

    # Determine if risk approved
    is_approved = i < risk_approved
    risk_verdict = "Approved" if is_approved else ("Rejected" if is_fused else "Not Reached")

    # Determine if executed
    is_executed = i < executed_count
    exec_status = "Filled" if is_executed else ("Pending" if is_approved else "Blocked")

    # P&L for executed trades
    pnl = round(float(np.random.normal(50, 200)), 2) if is_executed else None

    signals.append({
        "signal_id": sig_id,
        "source": source,
        "ticker": ticker,
        "direction": direction,
        "strength": strength,
        "fusion_score": fusion_score,
        "risk_verdict": risk_verdict,
        "exec_status": exec_status,
        "pnl": pnl,
    })

# Module health data
modules = [
    "signal_persistence",
    "unified_risk",
    "strategy_selector",
    "signal_feedback",
    "enhanced_backtest",
]
module_statuses = ["healthy", "healthy", "healthy", "degraded", "healthy"]
status_icons = {"healthy": "OK", "degraded": "WARN", "error": "ERR"}
last_checks = [
    (datetime.now() - timedelta(seconds=np.random.randint(5, 120))).strftime("%H:%M:%S")
    for _ in modules
]
signals_processed = np.random.randint(500, 5000, len(modules))
avg_latencies = np.random.uniform(5, 120, len(modules))
error_rates = np.random.uniform(0, 0.05, len(modules))
error_rates[3] = 0.032  # degraded module has higher error rate

# Performance time series data (signals per minute, last 60 minutes)
n_minutes = 60
timestamps = [(datetime.now() - timedelta(minutes=n_minutes - i)).strftime("%H:%M") for i in range(n_minutes)]
throughput = np.random.poisson(8, n_minutes).astype(float)
latency_ts = np.random.lognormal(3.5, 0.5, n_minutes)
error_rate_ts = np.random.uniform(0, 0.03, n_minutes)

# ═══════════════════════════════════════════════════════════════════════
# Dashboard Tabs
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "Pipeline Flow",
    "Signal Trace",
    "Module Health",
    "Performance",
])


# ── Tab 1: Pipeline Flow ──────────────────────────────────────────────

with tab1:
    st.subheader("Signal Pipeline Funnel")

    fusion_rate = fused_count / total_signals
    risk_rate = risk_approved / fused_count if fused_count > 0 else 0
    exec_rate = executed_count / risk_approved if risk_approved > 0 else 0
    overall_rate = executed_count / total_signals

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Signals", total_signals)
    m2.metric("Fusion Rate", f"{fusion_rate:.1%}")
    m3.metric("Risk Approval Rate", f"{risk_rate:.1%}")
    m4.metric("Execution Rate", f"{exec_rate:.1%}")

    st.divider()
    st.subheader("Pipeline Stages")

    # Funnel-like display using columns and metrics
    stages = [
        ("Signals Generated", total_signals, "100%"),
        ("Fused", fused_count, f"{fusion_rate:.1%}"),
        ("Risk Checked", risk_approved, f"{risk_approved / total_signals:.1%}"),
        ("Executed", executed_count, f"{overall_rate:.1%}"),
    ]

    cols = st.columns(4)
    for col, (stage_name, count, pct) in zip(cols, stages):
        with col:
            st.metric(stage_name, count, pct)

    # Funnel bar chart
    funnel_df = pd.DataFrame({
        "Count": [total_signals, fused_count, risk_approved, executed_count],
    }, index=["Generated", "Fused", "Risk Approved", "Executed"])
    st.bar_chart(funnel_df)

    st.divider()
    st.subheader("Drop-Off Analysis")
    col1, col2, col3 = st.columns(3)
    col1.metric("Lost at Fusion", total_signals - fused_count, f"-{total_signals - fused_count}")
    col2.metric("Lost at Risk Check", fused_count - risk_approved, f"-{fused_count - risk_approved}")
    col3.metric("Lost at Execution", risk_approved - executed_count, f"-{risk_approved - executed_count}")


# ── Tab 2: Signal Trace ───────────────────────────────────────────────

with tab2:
    st.subheader("Individual Signal Trace")

    m1, m2, m3 = st.columns(3)
    executed_signals = [s for s in signals if s["exec_status"] == "Filled"]
    profitable = sum(1 for s in executed_signals if s["pnl"] and s["pnl"] > 0)
    total_pnl = sum(s["pnl"] for s in executed_signals if s["pnl"])
    m1.metric("Traced Signals", total_signals)
    m2.metric("Profitable Executions", f"{profitable}/{len(executed_signals)}")
    m3.metric("Total P&L", f"${total_pnl:,.2f}")

    st.divider()

    trace_df = pd.DataFrame({
        "Signal ID": [s["signal_id"] for s in signals],
        "Source": [s["source"] for s in signals],
        "Ticker": [s["ticker"] for s in signals],
        "Direction": [s["direction"] for s in signals],
        "Strength": [s["strength"] for s in signals],
        "Fusion Score": [s["fusion_score"] if s["fusion_score"] else "-" for s in signals],
        "Risk Verdict": [s["risk_verdict"] for s in signals],
        "Execution": [s["exec_status"] for s in signals],
        "P&L": [f"${s['pnl']:,.2f}" if s["pnl"] else "-" for s in signals],
    })
    st.dataframe(trace_df, use_container_width=True)

    st.divider()
    st.subheader("Trace Detail")
    selected_signal = st.selectbox(
        "Select Signal",
        [s["signal_id"] for s in signals[:20]],
        key="trace_select",
    )
    sig = next(s for s in signals if s["signal_id"] == selected_signal)
    with st.expander(f"Full trace for {selected_signal}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Source:** {sig['source']}")
            st.markdown(f"**Ticker:** {sig['ticker']}")
            st.markdown(f"**Direction:** {sig['direction']}")
            st.markdown(f"**Strength:** {sig['strength']}")
        with col2:
            st.markdown(f"**Fusion Score:** {sig['fusion_score'] or 'N/A'}")
            st.markdown(f"**Risk Verdict:** {sig['risk_verdict']}")
            st.markdown(f"**Execution Status:** {sig['exec_status']}")
            pnl_display = f"${sig['pnl']:,.2f}" if sig["pnl"] else "N/A"
            st.markdown(f"**P&L:** {pnl_display}")


# ── Tab 3: Module Health ──────────────────────────────────────────────

with tab3:
    st.subheader("Pipeline Module Health")

    healthy_count = sum(1 for s in module_statuses if s == "healthy")
    degraded_count = sum(1 for s in module_statuses if s == "degraded")
    error_count = sum(1 for s in module_statuses if s == "error")

    m1, m2, m3 = st.columns(3)
    m1.metric("Healthy", healthy_count)
    m2.metric("Degraded", degraded_count)
    m3.metric("Error", error_count)

    st.divider()

    health_rows = []
    for i, mod in enumerate(modules):
        status = module_statuses[i]
        icon = "OK" if status == "healthy" else ("WARN" if status == "degraded" else "ERR")
        health_rows.append({
            "Module": mod,
            "Status": icon,
            "Last Check": last_checks[i],
            "Signals Processed": int(signals_processed[i]),
            "Avg Latency (ms)": f"{avg_latencies[i]:.1f}",
            "Error Rate": f"{error_rates[i]:.2%}",
        })

    st.dataframe(pd.DataFrame(health_rows), use_container_width=True)

    st.divider()
    st.subheader("Latency by Module")
    latency_chart_df = pd.DataFrame({
        "Avg Latency (ms)": avg_latencies,
    }, index=modules)
    st.bar_chart(latency_chart_df)

    st.divider()
    st.subheader("Error Rate by Module")
    error_chart_df = pd.DataFrame({
        "Error Rate": error_rates,
    }, index=modules)
    st.bar_chart(error_chart_df)

    # Alert for degraded modules
    for i, mod in enumerate(modules):
        if module_statuses[i] == "degraded":
            st.warning(f"Module **{mod}** is degraded -- Error rate: {error_rates[i]:.2%}, Latency: {avg_latencies[i]:.1f}ms")
        elif module_statuses[i] == "error":
            st.error(f"Module **{mod}** has errors -- Error rate: {error_rates[i]:.2%}, Latency: {avg_latencies[i]:.1f}ms")


# ── Tab 4: Performance ────────────────────────────────────────────────

with tab4:
    st.subheader("Pipeline Performance Metrics")

    avg_throughput = float(np.mean(throughput))
    avg_latency_overall = float(np.mean(latency_ts))
    avg_error_rate = float(np.mean(error_rate_ts))
    p99_latency = float(np.percentile(latency_ts, 99))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg Throughput", f"{avg_throughput:.1f} sig/min")
    m2.metric("Avg Latency", f"{avg_latency_overall:.1f} ms")
    m3.metric("P99 Latency", f"{p99_latency:.1f} ms")
    m4.metric("Avg Error Rate", f"{avg_error_rate:.2%}")

    st.divider()
    st.subheader("Throughput (signals/minute)")
    throughput_df = pd.DataFrame({
        "Signals/min": throughput,
    }, index=timestamps)
    st.line_chart(throughput_df)

    st.divider()
    st.subheader("Latency Distribution (ms)")
    latency_df = pd.DataFrame({
        "Latency (ms)": latency_ts,
    }, index=timestamps)
    st.line_chart(latency_df)

    st.divider()
    st.subheader("Error Rate Over Time")
    error_df = pd.DataFrame({
        "Error Rate": error_rate_ts,
    }, index=timestamps)
    st.line_chart(error_df)

    st.divider()
    st.subheader("Latency Percentiles")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("P50", f"{np.percentile(latency_ts, 50):.1f} ms")
    col2.metric("P75", f"{np.percentile(latency_ts, 75):.1f} ms")
    col3.metric("P95", f"{np.percentile(latency_ts, 95):.1f} ms")
    col4.metric("P99", f"{p99_latency:.1f} ms")
