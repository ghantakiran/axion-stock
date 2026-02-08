"""Application Lifecycle Dashboard (PRD-107).

Displays service status, health probes, shutdown history,
and lifecycle configuration.
"""

import random
from datetime import datetime, timedelta, timezone

import streamlit as st

from src.lifecycle.config import AppState, HealthStatus, LifecycleConfig, ShutdownPhase
from src.lifecycle.manager import LifecycleEvent, LifecycleManager

st.set_page_config(page_title="Lifecycle Management", page_icon="🔄", layout="wide")
st.title("🔄 Application Lifecycle Management")

tab1, tab2, tab3, tab4 = st.tabs([
    "Service Status",
    "Health Probes",
    "Shutdown History",
    "Configuration",
])

with tab1:
    st.header("Service Status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Application State", "RUNNING")
    col2.metric("Uptime", "14h 23m")
    col3.metric("Active Connections", "47")
    col4.metric("Registered Hooks", "12")

    st.subheader("Dependency Status")
    deps = {
        "PostgreSQL": ("healthy", "2.3ms"),
        "Redis": ("healthy", "0.8ms"),
        "Alpaca Broker": ("healthy", "45ms"),
        "Polygon Data": ("healthy", "12ms"),
        "ML Model Server": ("degraded", "350ms"),
    }
    for name, (status, latency) in deps.items():
        icon = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
        st.write(f"{icon} **{name}**: {status} ({latency})")

    st.subheader("Registered Startup Hooks")
    hooks = [
        {"name": "init_database", "priority": 10, "duration_ms": 234},
        {"name": "init_cache", "priority": 20, "duration_ms": 45},
        {"name": "init_broker_connections", "priority": 30, "duration_ms": 890},
        {"name": "init_ml_models", "priority": 40, "duration_ms": 2340},
        {"name": "init_websocket_server", "priority": 50, "duration_ms": 12},
    ]
    for hook in hooks:
        st.write(f"  Priority {hook['priority']}: **{hook['name']}** ({hook['duration_ms']}ms)")

with tab2:
    st.header("Health Probes")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Liveness")
        st.success("HEALTHY")
        st.json({"status": "healthy", "checks": {"process_alive": True}, "uptime_seconds": 51780})

    with col2:
        st.subheader("Readiness")
        st.success("HEALTHY")
        st.json({
            "status": "healthy",
            "checks": {
                "dep:database": True,
                "dep:cache": True,
                "dep:broker": True,
            },
            "uptime_seconds": 51780,
        })

    with col3:
        st.subheader("Startup")
        st.success("HEALTHY")
        st.json({"status": "healthy", "checks": {"initialization_complete": True}, "uptime_seconds": 51780})

    st.subheader("Probe Endpoints")
    st.code("""
GET /health/live    → Liveness probe (is process alive?)
GET /health/ready   → Readiness probe (are dependencies connected?)
GET /health/startup → Startup probe (has initialization completed?)
    """)

with tab3:
    st.header("Shutdown History")
    events = LifecycleManager.generate_sample_events(15)
    for event in events:
        st.write(
            f"**{event.event_type}** — {event.service_name} "
            f"({event.duration_ms:.0f}ms) — {event.details}"
        )

    st.subheader("Shutdown Phases")
    phases = [
        ("1. Drain Requests", "Stop accepting new requests, finish in-flight"),
        ("2. Close Connections", "Close database, Redis, broker connections"),
        ("3. Run Hooks", "Execute shutdown hooks in priority order"),
        ("4. Cleanup", "Restore signal handlers, release resources"),
        ("5. Completed", "Process exits cleanly"),
    ]
    for phase, desc in phases:
        st.write(f"**{phase}**: {desc}")

with tab4:
    st.header("Lifecycle Configuration")
    config = LifecycleConfig()
    st.json({
        "shutdown_timeout_seconds": config.shutdown_timeout_seconds,
        "drain_timeout_seconds": config.drain_timeout_seconds,
        "hook_timeout_seconds": config.hook_timeout_seconds,
        "enable_signal_handlers": config.enable_signal_handlers,
        "enable_health_probes": config.enable_health_probes,
        "service_name": config.service_name,
        "probe_endpoints": config.probe_endpoints,
        "registered_services": config.registered_services,
    })

    st.subheader("Signal Handling")
    st.code("""
# Signals handled:
SIGTERM → Graceful shutdown (default from Kubernetes/Docker)
SIGINT  → Graceful shutdown (Ctrl+C)

# Safety: After 3 consecutive signals, force-exit
    """)
