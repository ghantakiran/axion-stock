"""PRD-172: Bot API Dashboard.

4 tabs: Endpoints, WebSocket, Webhooks, API Keys.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Bot API", page_icon="\U0001f310", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f310 Bot API Dashboard")
st.caption("REST endpoints, WebSocket channels, webhooks, and API key management for bot control")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.bot_pipeline.orchestrator import BotOrchestrator
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False

np.random.seed(172)
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

REST_ENDPOINTS = [
    {"Method": "POST", "Path": "/bot/start", "Description": "Start the trading bot", "Auth": "Bearer Token", "Rate Limit": "10/min"},
    {"Method": "POST", "Path": "/bot/stop", "Description": "Gracefully stop the bot", "Auth": "Bearer Token", "Rate Limit": "10/min"},
    {"Method": "POST", "Path": "/bot/pause", "Description": "Pause signal processing (keep positions)", "Auth": "Bearer Token", "Rate Limit": "10/min"},
    {"Method": "POST", "Path": "/bot/resume", "Description": "Resume from paused state", "Auth": "Bearer Token", "Rate Limit": "10/min"},
    {"Method": "POST", "Path": "/bot/kill", "Description": "Activate kill switch (close all positions)", "Auth": "Bearer Token", "Rate Limit": "5/min"},
    {"Method": "POST", "Path": "/bot/kill/reset", "Description": "Reset kill switch and re-enable trading", "Auth": "Bearer Token", "Rate Limit": "5/min"},
    {"Method": "GET", "Path": "/bot/status", "Description": "Current bot state, uptime, and health", "Auth": "Bearer Token", "Rate Limit": "60/min"},
    {"Method": "GET", "Path": "/bot/positions", "Description": "List all open positions with P&L", "Auth": "Bearer Token", "Rate Limit": "60/min"},
    {"Method": "GET", "Path": "/bot/history", "Description": "Trade execution history with filters", "Auth": "Bearer Token", "Rate Limit": "30/min"},
    {"Method": "GET", "Path": "/bot/config", "Description": "Retrieve current bot configuration", "Auth": "Bearer Token", "Rate Limit": "30/min"},
    {"Method": "PUT", "Path": "/bot/config", "Description": "Update bot configuration (risk limits, symbols)", "Auth": "Bearer Token", "Rate Limit": "10/min"},
]

WS_CHANNELS = [
    {"Channel": "signals", "Description": "Real-time signal events (EMA cloud, mean-reversion, fusion)", "Format": "JSON", "Frequency": "Event-driven"},
    {"Channel": "orders", "Description": "Order placement, fill, and rejection updates", "Format": "JSON", "Frequency": "Event-driven"},
    {"Channel": "alerts", "Description": "Risk alerts, kill switch, circuit breaker state changes", "Format": "JSON", "Frequency": "Event-driven"},
    {"Channel": "lifecycle", "Description": "Bot start/stop/pause/resume lifecycle events", "Format": "JSON", "Frequency": "Event-driven"},
    {"Channel": "metrics", "Description": "Periodic performance snapshots (P&L, positions, drawdown)", "Format": "JSON", "Frequency": "Every 5s"},
]

# Recent API calls demo data
n_calls = 30
api_paths = np.random.choice(
    [e["Path"] for e in REST_ENDPOINTS], size=n_calls
).tolist()
api_methods = []
for p in api_paths:
    for e in REST_ENDPOINTS:
        if e["Path"] == p:
            api_methods.append(e["Method"])
            break
response_times = np.random.lognormal(mean=3.0, sigma=0.8, size=n_calls)
status_codes = np.random.choice([200, 200, 200, 200, 201, 400, 401, 429, 500],
                                 size=n_calls, p=[0.5, 0.15, 0.1, 0.05, 0.05, 0.05, 0.03, 0.04, 0.03]).tolist()
call_times = sorted([NOW - timedelta(minutes=int(np.random.randint(1, 120))) for _ in range(n_calls)])

# API keys demo data
API_KEYS = [
    {"Key ID": "ak_prod_1a2b3c", "Name": "Production Bot", "Created": "2025-11-01", "Last Used": "2026-02-09 14:22", "Permissions": "full", "Status": "Active"},
    {"Key ID": "ak_dev_4d5e6f", "Name": "Development Bot", "Created": "2025-12-15", "Last Used": "2026-02-08 09:11", "Permissions": "read-only", "Status": "Active"},
    {"Key ID": "ak_test_7g8h9i", "Name": "Backtest Runner", "Created": "2026-01-10", "Last Used": "2026-02-07 16:45", "Permissions": "read-only", "Status": "Active"},
    {"Key ID": "ak_old_0j1k2l", "Name": "Legacy Integration", "Created": "2025-06-01", "Last Used": "2025-09-14 11:03", "Permissions": "full", "Status": "Revoked"},
]

# Webhook demo data
WEBHOOKS = [
    {"ID": "wh_001", "URL": "https://hooks.slack.com/services/T0.../B0.../xxx", "Events": "kill_switch, circuit_breaker", "Status": "Active", "Last Triggered": "2026-02-09 13:05"},
    {"ID": "wh_002", "URL": "https://api.pagerduty.com/webhooks/xxx", "Events": "trade_error, position_mismatch", "Status": "Active", "Last Triggered": "2026-02-08 22:17"},
    {"ID": "wh_003", "URL": "https://discord.com/api/webhooks/xxx/yyy", "Events": "daily_summary", "Status": "Paused", "Last Triggered": "2026-02-05 16:00"},
]

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Endpoints",
    "WebSocket",
    "Webhooks",
    "API Keys",
])

# =====================================================================
# Tab 1 - REST Endpoints
# =====================================================================
with tab1:
    st.subheader("REST API Endpoints")

    if not API_AVAILABLE:
        st.info("Bot pipeline module not installed. Showing API reference documentation.")

    st.dataframe(pd.DataFrame(REST_ENDPOINTS), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Recent API Activity")

    total_calls = n_calls
    success_calls = sum(1 for s in status_codes if 200 <= s < 300)
    avg_latency = round(float(np.mean(response_times)), 1)
    error_calls = sum(1 for s in status_codes if s >= 400)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Calls (2h)", total_calls)
    c2.metric("Success Rate", f"{success_calls / total_calls * 100:.1f}%")
    c3.metric("Avg Latency", f"{avg_latency} ms")
    c4.metric("Errors", error_calls)

    call_df = pd.DataFrame({
        "Time": [t.strftime("%H:%M:%S") for t in call_times],
        "Method": api_methods,
        "Path": api_paths,
        "Status": status_codes,
        "Latency (ms)": [round(float(r), 1) for r in response_times],
    })
    st.dataframe(call_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Status Code Distribution")
        code_counts = pd.Series(status_codes).value_counts().sort_index()
        st.bar_chart(code_counts)
    with col_right:
        st.markdown("#### Latency Over Time")
        latency_df = pd.DataFrame({
            "Latency (ms)": [round(float(r), 1) for r in response_times],
        }, index=[t.strftime("%H:%M") for t in call_times])
        st.line_chart(latency_df)

# =====================================================================
# Tab 2 - WebSocket
# =====================================================================
with tab2:
    st.subheader("WebSocket Connection")

    st.code("ws://localhost:8000/ws/bot", language="text")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Connection Parameters")
        connection_info = {
            "url": "ws://<host>/ws/bot",
            "protocol": "WebSocket (RFC 6455)",
            "authentication": "Bearer token in query param or header",
            "heartbeat_interval": "30s",
            "reconnect_policy": "Exponential backoff (1s, 2s, 4s, ... max 60s)",
            "max_message_size": "64 KB",
        }
        st.json(connection_info)

    with col2:
        st.markdown("#### Connection Example")
        st.code("""
import websocket
import json

ws = websocket.WebSocket()
ws.connect("ws://localhost:8000/ws/bot?token=<API_KEY>")

# Subscribe to channels
ws.send(json.dumps({
    "action": "subscribe",
    "channels": ["signals", "orders", "alerts"]
}))

while True:
    msg = json.loads(ws.recv())
    print(f"[{msg['channel']}] {msg['data']}")
""", language="python")

    st.markdown("---")
    st.subheader("Available Channels")
    st.dataframe(pd.DataFrame(WS_CHANNELS), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Channel Message Samples")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Signal Event**")
        st.json({
            "channel": "signals",
            "timestamp": NOW.isoformat(),
            "data": {
                "signal_type": "ema_cloud_bullish",
                "ticker": "AAPL",
                "conviction": 78,
                "strategy": "ema_cloud",
                "timeframe": "5m",
            }
        })

        st.markdown("**Order Event**")
        st.json({
            "channel": "orders",
            "timestamp": NOW.isoformat(),
            "data": {
                "order_id": "ORD-172001",
                "action": "filled",
                "ticker": "AAPL",
                "side": "buy",
                "qty": 50,
                "fill_price": 189.42,
            }
        })

    with col2:
        st.markdown("**Alert Event**")
        st.json({
            "channel": "alerts",
            "timestamp": NOW.isoformat(),
            "data": {
                "alert_type": "circuit_breaker",
                "severity": "warning",
                "message": "Circuit breaker moved to half_open state",
            }
        })

        st.markdown("**Metrics Snapshot**")
        st.json({
            "channel": "metrics",
            "timestamp": NOW.isoformat(),
            "data": {
                "daily_pnl": 1245.67,
                "open_positions": 5,
                "drawdown_pct": -1.8,
                "win_rate": 0.62,
                "uptime_hours": 14.3,
            }
        })

    st.markdown("---")
    st.subheader("Live Connection Stats")
    ws_c1, ws_c2, ws_c3, ws_c4 = st.columns(4)
    ws_c1.metric("Active Connections", int(np.random.randint(1, 5)))
    ws_c2.metric("Messages Sent (1h)", int(np.random.randint(500, 2000)))
    ws_c3.metric("Avg Delivery (ms)", round(float(np.random.uniform(1.5, 8.0)), 1))
    ws_c4.metric("Reconnections (24h)", int(np.random.randint(0, 4)))

# =====================================================================
# Tab 3 - Webhooks
# =====================================================================
with tab3:
    st.subheader("Webhook Configuration")

    st.dataframe(pd.DataFrame(WEBHOOKS), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Register New Webhook")

    col1, col2 = st.columns(2)
    with col1:
        wh_url = st.text_input("Webhook URL", placeholder="https://your-service.com/webhook")
        wh_secret = st.text_input("Signing Secret (optional)", type="password", placeholder="whsec_...")
    with col2:
        wh_events = st.multiselect(
            "Events to Subscribe",
            options=["kill_switch", "circuit_breaker", "trade_error", "position_mismatch",
                     "daily_summary", "signal_generated", "order_filled", "drawdown_alert"],
            default=["kill_switch", "trade_error"],
        )
        wh_format = st.selectbox("Payload Format", ["JSON", "Form-Encoded"])

    if st.button("Register Webhook", type="primary"):
        if wh_url:
            st.success(f"Webhook registered for {len(wh_events)} event(s)")
        else:
            st.error("Please provide a webhook URL")

    st.markdown("---")
    st.subheader("Webhook Delivery Log")

    n_deliveries = 15
    delivery_times = sorted([NOW - timedelta(minutes=int(np.random.randint(5, 1440))) for _ in range(n_deliveries)])
    delivery_events = np.random.choice(
        ["kill_switch", "trade_error", "daily_summary", "circuit_breaker", "order_filled"],
        size=n_deliveries,
    ).tolist()
    delivery_statuses = np.random.choice(
        ["delivered", "delivered", "delivered", "failed", "retrying"],
        size=n_deliveries, p=[0.7, 0.1, 0.05, 0.1, 0.05],
    ).tolist()
    delivery_codes = []
    for ds in delivery_statuses:
        if ds == "delivered":
            delivery_codes.append(200)
        elif ds == "failed":
            delivery_codes.append(int(np.random.choice([500, 502, 503, 408])))
        else:
            delivery_codes.append(0)

    delivery_df = pd.DataFrame({
        "Time": [t.strftime("%Y-%m-%d %H:%M") for t in delivery_times],
        "Event": delivery_events,
        "Target": [f"wh_00{int(np.random.randint(1, 4))}" for _ in range(n_deliveries)],
        "Status": delivery_statuses,
        "HTTP Code": delivery_codes,
        "Latency (ms)": [round(float(np.random.lognormal(4.0, 0.5)), 0) if s != 0 else 0 for s in delivery_codes],
    })
    st.dataframe(delivery_df, use_container_width=True, hide_index=True)

    total_deliveries = n_deliveries
    success_deliveries = sum(1 for s in delivery_statuses if s == "delivered")
    failed_deliveries = sum(1 for s in delivery_statuses if s == "failed")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Deliveries (24h)", total_deliveries)
    c2.metric("Success Rate", f"{success_deliveries / total_deliveries * 100:.0f}%")
    c3.metric("Failed", failed_deliveries)

# =====================================================================
# Tab 4 - API Keys
# =====================================================================
with tab4:
    st.subheader("API Key Management")

    st.dataframe(pd.DataFrame(API_KEYS), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Create New API Key")

    col1, col2 = st.columns(2)
    with col1:
        key_name = st.text_input("Key Name", placeholder="My Trading Bot Key")
        key_perms = st.selectbox("Permissions", ["full", "read-only", "trade-only"])
    with col2:
        key_expiry = st.selectbox("Expiration", ["Never", "30 days", "90 days", "1 year"])
        ip_whitelist = st.text_input("IP Whitelist (optional)", placeholder="192.168.1.0/24, 10.0.0.1")

    if st.button("Generate API Key", type="primary"):
        if key_name:
            st.success("API key generated successfully")
            st.code("ak_new_xYz789AbCdEfGhIjKlMnOpQr", language="text")
            st.warning("Copy this key now. It will not be shown again.")
        else:
            st.error("Please provide a key name")

    st.markdown("---")
    st.subheader("API Usage by Key (Last 7 Days)")

    usage_data = []
    for key in API_KEYS:
        if key["Status"] == "Active":
            usage_data.append({
                "Key": key["Key ID"],
                "Name": key["Name"],
                "Calls (7d)": int(np.random.randint(100, 5000)),
                "Errors (7d)": int(np.random.randint(0, 50)),
                "Last Endpoint": np.random.choice([e["Path"] for e in REST_ENDPOINTS]),
                "Avg Latency (ms)": round(float(np.random.uniform(15, 80)), 1),
            })
    st.dataframe(pd.DataFrame(usage_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Security Settings")
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("Require IP whitelist for all keys", value=False)
        st.checkbox("Enable request signing (HMAC-SHA256)", value=True)
    with col2:
        st.number_input("Global rate limit (requests/min)", min_value=10, max_value=1000, value=120)
        st.number_input("Max active keys per account", min_value=1, max_value=20, value=5)
