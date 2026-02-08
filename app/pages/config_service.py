"""Configuration Management Dashboard (PRD-111).

Displays config browser, feature flags, secrets metadata,
and validation results.
"""

import streamlit as st

from src.config_service.config import (
    ConfigNamespace,
    ConfigValueType,
    Environment,
    FeatureFlagType,
    ServiceConfig,
)
from src.config_service.feature_flags import FlagStatus

try:
    st.set_page_config(page_title="Configuration", page_icon="⚙️", layout="wide")
except st.errors.StreamlitAPIException:
    pass

st.title("⚙️ Configuration Management")

tab1, tab2, tab3, tab4 = st.tabs([
    "Config Browser",
    "Feature Flags",
    "Secrets",
    "Validation",
])

with tab1:
    st.header("Configuration Browser")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Entries", "156")
    col2.metric("Namespaces", str(len(ConfigNamespace)))
    col3.metric("Sensitive Keys", "12")
    col4.metric("Recent Changes", "8")

    st.subheader("Entries by Namespace")
    ns_data = {
        "trading": 32,
        "ml": 28,
        "risk": 24,
        "api": 18,
        "data": 20,
        "system": 15,
        "broker": 12,
        "notification": 7,
    }
    st.bar_chart(ns_data)

    st.subheader("Recent Changes")
    changes = [
        {"key": "trading.max_positions", "old": "50", "new": "100", "by": "admin"},
        {"key": "ml.model_version", "old": "2.1", "new": "2.2", "by": "ml_team"},
        {"key": "risk.max_var", "old": "0.05", "new": "0.03", "by": "risk_mgr"},
        {"key": "api.rate_limit", "old": "60", "new": "120", "by": "admin"},
    ]
    for ch in changes:
        st.write(
            f"**{ch['key']}**: `{ch['old']}` → `{ch['new']}` (by {ch['by']})"
        )

with tab2:
    st.header("Feature Flags")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Flags", "18")
    col2.metric("Boolean", "10")
    col3.metric("Percentage", "5")
    col4.metric("User List", "3")

    st.subheader("Active Feature Flags")
    flags = [
        {"name": "new_ranking_model_v2", "type": "percentage", "value": "25%",
         "status": "active"},
        {"name": "dark_pool_routing", "type": "boolean", "value": "True",
         "status": "active"},
        {"name": "earnings_ml_v3", "type": "percentage", "value": "10%",
         "status": "active"},
        {"name": "beta_dashboard", "type": "user_list", "value": "5 users",
         "status": "active"},
        {"name": "legacy_factor_engine", "type": "boolean", "value": "True",
         "status": "deprecated"},
    ]
    for f in flags:
        icon = "🟢" if f["status"] == "active" else "🟡"
        st.write(
            f"{icon} **{f['name']}** [{f['type']}] = {f['value']} "
            f"({f['status']})"
        )

    st.subheader("Flag Types")
    st.info(
        "**Boolean**: Simple on/off toggle\n\n"
        "**Percentage**: Gradual rollout (deterministic per user)\n\n"
        "**User List**: Targeted rollout to specific users"
    )

with tab3:
    st.header("Secrets Management")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Secrets", "15")
    col2.metric("Expired", "1")
    col3.metric("Rotations (30d)", "4")

    st.subheader("Registered Secrets")
    secrets = [
        {"name": "POLYGON_API_KEY", "rotated": "5 days ago", "expired": False},
        {"name": "ALPACA_API_KEY", "rotated": "12 days ago", "expired": False},
        {"name": "ALPACA_SECRET_KEY", "rotated": "12 days ago", "expired": False},
        {"name": "DB_PASSWORD", "rotated": "30 days ago", "expired": False},
        {"name": "REDIS_PASSWORD", "rotated": "30 days ago", "expired": False},
        {"name": "JWT_SECRET", "rotated": "45 days ago", "expired": False},
        {"name": "OLD_API_TOKEN", "rotated": "90 days ago", "expired": True},
    ]
    for s in secrets:
        icon = "🔴" if s["expired"] else "🟢"
        st.write(
            f"{icon} **{s['name']}** — Last rotated: {s['rotated']}"
            f"{' (EXPIRED)' if s['expired'] else ''}"
        )

    st.subheader("Access Log (Recent)")
    accesses = [
        {"secret": "POLYGON_API_KEY", "by": "data_service", "action": "read"},
        {"secret": "ALPACA_API_KEY", "by": "broker_service", "action": "read"},
        {"secret": "DB_PASSWORD", "by": "api_server", "action": "read"},
        {"secret": "POLYGON_API_KEY", "by": "admin", "action": "rotate"},
    ]
    for a in accesses:
        st.write(f"  {a['action'].upper()}: **{a['secret']}** by {a['by']}")

with tab4:
    st.header("Configuration Validation")

    st.subheader("Validation Report")
    config = ServiceConfig()
    st.json({
        "valid": True,
        "rules_checked": 42,
        "keys_validated": 38,
        "errors": 0,
        "warnings": 3,
        "info": 5,
    })

    st.subheader("Warnings")
    warnings = [
        "trading.max_drawdown: Value 0.25 exceeds recommended maximum 0.20",
        "api.cors_origins: Contains wildcard '*' — restrict in production",
        "ml.training_timeout: Value 7200s is above recommended 3600s",
    ]
    for w in warnings:
        st.warning(w)

    st.subheader("Environment Comparison")
    st.write("**Development vs Production differences:**")
    diffs = {
        "debug": {"development": True, "production": False},
        "db_host": {"development": "localhost", "production": "prod-db.axion.io"},
        "replicas": {"development": 1, "production": 3},
        "log_level": {"development": "DEBUG", "production": "WARNING"},
    }
    st.json(diffs)
