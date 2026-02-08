"""Structured Logging Dashboard (PRD-101).

Displays logging configuration, live log viewer simulation,
request tracing demo, and performance metrics.
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from src.logging_config.config import LogFormat, LoggingConfig, LogLevel
from src.logging_config.context import RequestContext, generate_request_id
from src.logging_config.performance import PerformanceTimer
from src.logging_config.setup import StructuredFormatter

st.set_page_config(page_title="Structured Logging", page_icon="📋", layout="wide")
st.title("📋 Structured Logging & Request Tracing")

tab1, tab2, tab3, tab4 = st.tabs([
    "Configuration",
    "Live Log Viewer",
    "Request Tracing",
    "Performance Metrics",
])


# --- Tab 1: Configuration ---
with tab1:
    st.header("Logging Configuration")

    config = LoggingConfig()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Current Settings")
        st.json({
            "level": config.level.value,
            "format": config.format.value,
            "include_caller": config.include_caller,
            "slow_threshold_ms": config.slow_threshold_ms,
            "service_name": config.service_name,
            "exclude_paths": config.exclude_paths,
        })

    with col2:
        st.subheader("Log Level Distribution")
        levels = {"DEBUG": 45, "INFO": 30, "WARNING": 15, "ERROR": 8, "CRITICAL": 2}
        st.bar_chart(levels)

    st.subheader("Environment Variables")
    st.code("""
# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export AXION_LOG_LEVEL=INFO

# Set log format (json for production, console for development)
export AXION_LOG_FORMAT=json
    """, language="bash")

    st.subheader("Sample Log Output")
    formatter = StructuredFormatter(service_name="axion")
    import logging
    record = logging.LogRecord(
        name="src.execution.order_manager", level=logging.INFO,
        pathname="order_manager.py", lineno=142,
        msg="Order submitted successfully", args=(), exc_info=None,
    )
    record.duration_ms = 23.5
    record.status_code = 200
    sample = json.loads(formatter.format(record))
    sample["request_id"] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    st.json(sample)


# --- Tab 2: Live Log Viewer ---
with tab2:
    st.header("Log Stream Viewer")

    log_level_filter = st.selectbox(
        "Filter by Level",
        ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    # Generate sample log entries
    sample_logs = []
    services = ["api", "execution", "data_pipeline", "ml_serving", "risk"]
    messages = [
        ("INFO", "Request processed", "api"),
        ("INFO", "Market data updated", "data_pipeline"),
        ("DEBUG", "Cache hit for AAPL quote", "api"),
        ("WARNING", "Slow query detected: 850ms", "data_pipeline"),
        ("INFO", "Order filled: BUY 100 AAPL @ 185.50", "execution"),
        ("ERROR", "Broker connection timeout", "execution"),
        ("INFO", "Risk check passed for portfolio rebalance", "risk"),
        ("WARNING", "Position size exceeds soft limit", "risk"),
        ("INFO", "ML model prediction generated", "ml_serving"),
        ("DEBUG", "Factor scores computed for 500 tickers", "data_pipeline"),
        ("ERROR", "Redis connection lost, reconnecting", "api"),
        ("INFO", "WebSocket client connected", "api"),
    ]

    now = datetime.now(timezone.utc)
    for i, (level, msg, svc) in enumerate(messages):
        ts = now - timedelta(seconds=random.randint(1, 300))
        sample_logs.append({
            "timestamp": ts.strftime("%H:%M:%S.%f")[:-3],
            "level": level,
            "service": svc,
            "message": msg,
            "request_id": generate_request_id()[:8],
        })

    # Filter
    if log_level_filter != "ALL":
        sample_logs = [l for l in sample_logs if l["level"] == log_level_filter]

    # Display as formatted log lines
    for entry in sample_logs:
        level = entry["level"]
        color = {
            "DEBUG": "gray", "INFO": "green", "WARNING": "orange",
            "ERROR": "red", "CRITICAL": "red",
        }.get(level, "white")

        st.markdown(
            f"<span style='color:{color};font-family:monospace'>"
            f"{entry['timestamp']} [{entry['level']:8s}] "
            f"{entry['service']:15s} | {entry['message']} "
            f"(req={entry['request_id']})</span>",
            unsafe_allow_html=True,
        )

    st.metric("Total Log Entries (24h)", "142,856")
    col1, col2, col3 = st.columns(3)
    col1.metric("Error Rate", "0.8%", "-0.2%")
    col2.metric("Avg Log Size", "284 bytes")
    col3.metric("Logs/Second", "1.65")


# --- Tab 3: Request Tracing ---
with tab3:
    st.header("Request Tracing")

    st.subheader("Active Request Contexts")

    # Simulate request traces
    traces = [
        {
            "request_id": generate_request_id(),
            "method": "POST",
            "path": "/api/v1/orders",
            "user_id": "user_42",
            "started": "12ms ago",
            "spans": [
                {"name": "auth.verify_token", "duration_ms": 2.1},
                {"name": "risk.pre_trade_check", "duration_ms": 4.5},
                {"name": "execution.submit_order", "duration_ms": 3.2},
                {"name": "db.insert_order", "duration_ms": 1.8},
            ],
        },
        {
            "request_id": generate_request_id(),
            "method": "GET",
            "path": "/api/v1/portfolio",
            "user_id": "user_17",
            "started": "45ms ago",
            "spans": [
                {"name": "auth.verify_token", "duration_ms": 1.5},
                {"name": "cache.get_portfolio", "duration_ms": 0.8},
                {"name": "optimizer.compute_metrics", "duration_ms": 38.2},
            ],
        },
    ]

    for trace in traces:
        with st.expander(
            f"{trace['method']} {trace['path']} — {trace['request_id'][:12]}..."
        ):
            st.write(f"**User:** {trace['user_id']} | **Started:** {trace['started']}")
            total = sum(s["duration_ms"] for s in trace["spans"])
            st.write(f"**Total Duration:** {total:.1f}ms")

            for span in trace["spans"]:
                pct = (span["duration_ms"] / total) * 100
                st.progress(pct / 100, text=f"{span['name']}: {span['duration_ms']:.1f}ms")

    st.subheader("Header Propagation")
    st.code("""
# Request headers propagated automatically:
X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
X-Correlation-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Response headers include:
x-request-id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
x-correlation-id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """)


# --- Tab 4: Performance Metrics ---
with tab4:
    st.header("Performance Metrics")

    st.subheader("Slow Operation Alerts")
    slow_ops = [
        {"function": "fetch_market_data", "duration_ms": 2340, "threshold_ms": 1000},
        {"function": "compute_factor_scores", "duration_ms": 1520, "threshold_ms": 1000},
        {"function": "execute_rebalance", "duration_ms": 3100, "threshold_ms": 2000},
    ]

    for op in slow_ops:
        over = op["duration_ms"] - op["threshold_ms"]
        st.warning(
            f"**{op['function']}** took {op['duration_ms']}ms "
            f"(+{over}ms over {op['threshold_ms']}ms threshold)"
        )

    st.subheader("Function Execution Times (P95)")
    perf_data = {
        "api.health_check": 2,
        "cache.get_quote": 5,
        "db.get_portfolio": 12,
        "auth.verify_token": 8,
        "risk.pre_trade": 45,
        "execution.submit": 85,
        "ml.predict": 120,
        "data.fetch_prices": 250,
        "backtest.run": 1500,
        "optimizer.solve": 890,
    }
    st.bar_chart(perf_data)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Median Response", "23ms", "-2ms")
    col2.metric("P95 Response", "145ms", "+8ms")
    col3.metric("P99 Response", "892ms", "+45ms")
    col4.metric("Slow Operations/hr", "12", "-3")
