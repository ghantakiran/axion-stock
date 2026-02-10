"""PRD-102: Resilience Patterns Dashboard."""

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()
import time
import random
from datetime import datetime

from src.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerOpen,
    CircuitState,
    RateLimiter,
    RateLimiterConfig,
    Bulkhead,
    BulkheadConfig,
    RetryConfig,
    ResilienceConfig,
)


def _generate_sample_circuit_metrics():
    """Generate sample circuit breaker metrics for display."""
    services = [
        ("polygon_api", CircuitState.CLOSED, 0, 1523, 1523, 0),
        ("alpaca_broker", CircuitState.CLOSED, 1, 892, 891, 0),
        ("redis_cache", CircuitState.HALF_OPEN, 3, 456, 420, 12),
        ("ml_serving", CircuitState.OPEN, 7, 234, 180, 47),
        ("websocket_feed", CircuitState.CLOSED, 0, 3201, 3201, 0),
        ("postgres_db", CircuitState.CLOSED, 2, 1876, 1870, 0),
    ]
    results = []
    for name, state, failures, total, success, rejected in services:
        results.append({
            "name": name,
            "state": state.value,
            "failure_count": failures,
            "success_count": success,
            "total_calls": total,
            "rejected_calls": rejected,
            "failure_threshold": 5,
            "recovery_timeout": 30.0,
        })
    return results


def _generate_sample_rate_metrics():
    """Generate sample rate limiter metrics."""
    clients = [
        ("192.168.1.10", 145, 3, 18.5),
        ("192.168.1.20", 89, 0, 20.0),
        ("10.0.0.5", 312, 15, 12.3),
        ("10.0.0.8", 67, 0, 20.0),
        ("172.16.0.1", 201, 8, 15.7),
    ]
    results = []
    for ip, allowed, rejected, tokens in clients:
        results.append({
            "client": ip,
            "total_allowed": allowed,
            "total_rejected": rejected,
            "available_tokens": round(tokens, 1),
            "rate_per_second": 100,
            "max_tokens": 20,
        })
    return results


def _generate_sample_bulkhead_metrics():
    """Generate sample bulkhead metrics."""
    partitions = [
        ("order_execution", 10, 3, 245, 2),
        ("market_data", 20, 8, 1502, 0),
        ("ml_inference", 5, 4, 89, 5),
        ("report_generation", 3, 1, 34, 0),
        ("notification_service", 8, 0, 567, 1),
    ]
    results = []
    for name, max_c, active, accepted, rejected in partitions:
        results.append({
            "name": name,
            "max_concurrent": max_c,
            "active_count": active,
            "available_slots": max_c - active,
            "total_accepted": accepted,
            "total_rejected": rejected,
        })
    return results


def _generate_sample_retry_metrics():
    """Generate sample retry history."""
    entries = []
    operations = [
        "fetch_market_data", "place_order", "get_positions",
        "update_portfolio", "send_notification", "sync_accounts",
        "calculate_risk", "generate_report",
    ]
    for i in range(15):
        op = random.choice(operations)
        attempts = random.randint(1, 4)
        success = random.random() > 0.2
        entries.append({
            "operation": op,
            "attempts": attempts,
            "success": success,
            "total_delay_s": round(random.uniform(0.5, 15.0), 2) if attempts > 1 else 0,
            "last_error": "" if success else random.choice([
                "ConnectionError", "TimeoutError", "OSError"
            ]),
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        })
    return entries


def render():
    st.title("Resilience Patterns")

    tabs = st.tabs(["Circuit Breakers", "Rate Limiting", "Bulkheads", "Retry & Config"])

    # ── Tab 1: Circuit Breakers ───────────────────────────────────────
    with tabs[0]:
        st.subheader("Circuit Breaker Status")

        metrics = _generate_sample_circuit_metrics()

        # Summary
        states = [m["state"] for m in metrics]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Breakers", len(metrics))
        col2.metric("Closed", states.count("closed"))
        col3.metric("Half-Open", states.count("half_open"))
        col4.metric("Open", states.count("open"))

        # Details
        for m in metrics:
            color = {"closed": "green", "half_open": "orange", "open": "red"}.get(
                m["state"], "gray"
            )
            st.markdown(
                f":{color}[**{m['name'].upper()}**] ({m['state'].upper()}) -- "
                f"Failures: {m['failure_count']}/{m['failure_threshold']} | "
                f"Calls: {m['total_calls']:,} | "
                f"Rejected: {m['rejected_calls']}"
            )

        st.subheader("Circuit Breaker Transitions")
        st.info(
            "CLOSED -> OPEN: When failure count reaches threshold.\n\n"
            "OPEN -> HALF_OPEN: After recovery timeout expires.\n\n"
            "HALF_OPEN -> CLOSED: On successful test call.\n\n"
            "HALF_OPEN -> OPEN: On failed test call."
        )

    # ── Tab 2: Rate Limiting ──────────────────────────────────────────
    with tabs[1]:
        st.subheader("Rate Limiter Status")

        rate_metrics = _generate_sample_rate_metrics()

        total_allowed = sum(m["total_allowed"] for m in rate_metrics)
        total_rejected = sum(m["total_rejected"] for m in rate_metrics)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requests", f"{total_allowed + total_rejected:,}")
        col2.metric("Allowed", f"{total_allowed:,}")
        col3.metric("Rejected (429)", f"{total_rejected:,}")

        st.subheader("Per-Client Breakdown")
        rate_data = []
        for m in rate_metrics:
            rate_data.append({
                "Client": m["client"],
                "Allowed": m["total_allowed"],
                "Rejected": m["total_rejected"],
                "Available Tokens": m["available_tokens"],
                "Rate (req/s)": m["rate_per_second"],
            })
        st.dataframe(rate_data, use_container_width=True)

        st.subheader("Token Bucket Configuration")
        cfg = ResilienceConfig()
        st.write({
            "Rate (tokens/sec)": cfg.rate_limiter.rate,
            "Burst Size": cfg.rate_limiter.burst,
            "Algorithm": cfg.rate_limiter.algorithm.value,
        })

    # ── Tab 3: Bulkheads ─────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Bulkhead Partitions")

        bh_metrics = _generate_sample_bulkhead_metrics()

        total_active = sum(m["active_count"] for m in bh_metrics)
        total_capacity = sum(m["max_concurrent"] for m in bh_metrics)
        total_rejected_bh = sum(m["total_rejected"] for m in bh_metrics)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Partitions", len(bh_metrics))
        col2.metric("Active Workers", total_active)
        col3.metric("Total Capacity", total_capacity)
        col4.metric("Rejected", total_rejected_bh)

        for m in bh_metrics:
            usage_pct = m["active_count"] / m["max_concurrent"] if m["max_concurrent"] else 0
            color = "green" if usage_pct < 0.7 else ("orange" if usage_pct < 0.9 else "red")
            st.markdown(
                f":{color}[**{m['name'].upper()}**] -- "
                f"Active: {m['active_count']}/{m['max_concurrent']} | "
                f"Available: {m['available_slots']} | "
                f"Accepted: {m['total_accepted']:,} | "
                f"Rejected: {m['total_rejected']}"
            )

        bh_table = []
        for m in bh_metrics:
            bh_table.append({
                "Partition": m["name"],
                "Max Concurrent": m["max_concurrent"],
                "Active": m["active_count"],
                "Available": m["available_slots"],
                "Accepted": m["total_accepted"],
                "Rejected": m["total_rejected"],
            })
        st.dataframe(bh_table, use_container_width=True)

    # ── Tab 4: Retry & Config ─────────────────────────────────────────
    with tabs[3]:
        st.subheader("Recent Retry Activity")

        retry_entries = _generate_sample_retry_metrics()

        success_count = sum(1 for e in retry_entries if e["success"])
        fail_count = len(retry_entries) - success_count

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Operations", len(retry_entries))
        col2.metric("Succeeded", success_count)
        col3.metric("Exhausted", fail_count)

        retry_data = []
        for e in retry_entries:
            retry_data.append({
                "Operation": e["operation"],
                "Attempts": e["attempts"],
                "Success": "Yes" if e["success"] else "No",
                "Total Delay (s)": e["total_delay_s"],
                "Last Error": e["last_error"],
                "Time": e["timestamp"],
            })
        st.dataframe(retry_data, use_container_width=True)

        st.subheader("Resilience Configuration")
        cfg = ResilienceConfig()

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Circuit Breaker**")
            st.write({
                "Failure Threshold": cfg.circuit_breaker.failure_threshold,
                "Recovery Timeout (s)": cfg.circuit_breaker.recovery_timeout,
                "Half-Open Max Calls": cfg.circuit_breaker.half_open_max_calls,
            })
            st.write("**Retry**")
            st.write({
                "Max Retries": cfg.retry.max_retries,
                "Base Delay (s)": cfg.retry.base_delay,
                "Max Delay (s)": cfg.retry.max_delay,
                "Strategy": cfg.retry.strategy.value,
            })
        with col2:
            st.write("**Rate Limiter**")
            st.write({
                "Rate (tokens/s)": cfg.rate_limiter.rate,
                "Burst": cfg.rate_limiter.burst,
                "Algorithm": cfg.rate_limiter.algorithm.value,
            })
            st.write("**Bulkhead**")
            st.write({
                "Max Concurrent": cfg.bulkhead.max_concurrent,
                "Timeout (s)": cfg.bulkhead.timeout,
                "Type": cfg.bulkhead.bulkhead_type.value,
            })



render()
