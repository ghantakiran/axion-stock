"""PRD-174: Bot Alerting Dashboard.

4 tabs: Live Alerts, Rules, History, Channels.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from app.styles import inject_global_styles

try:
    st.set_page_config(page_title="Bot Alerting", page_icon="\U0001f6a8", layout="wide")
except Exception:
    pass

inject_global_styles()
st.title("\U0001f6a8 Bot Alerting")
st.caption("Live alerts, rule configuration, alert history, and delivery channel management")

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from src.alerting import AlertManager, AlertSeverity, AlertCategory, ChannelType
    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False

try:
    from src.bot_pipeline.orchestrator import BotOrchestrator
    BOT_AVAILABLE = True
except ImportError:
    BOT_AVAILABLE = False

np.random.seed(174)
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Demo Data
# ---------------------------------------------------------------------------

SEVERITY_LEVELS = ["critical", "error", "warning", "info"]

# Live alerts
live_alerts = []
alert_messages = [
    ("Kill Switch Activated", "Daily loss limit of $2,000 exceeded", "critical", "bot_pipeline"),
    ("Circuit Breaker Open", "3 consecutive failed fills triggered circuit breaker", "critical", "order_validator"),
    ("High Drawdown", "Intraday drawdown reached -3.2%, threshold is -3.0%", "error", "risk_monitor"),
    ("Position Mismatch", "NVDA internal qty=100 vs broker qty=95, diff=5", "error", "position_reconciler"),
    ("Stale Signal Rejected", "EMA cloud signal for TSLA was 45s old (max 30s)", "warning", "signal_guard"),
    ("Duplicate Signal Filtered", "Duplicate ema_cloud_bullish for AAPL within 60s window", "warning", "signal_guard"),
    ("Partial Fill Detected", "ORD-174023 filled 80/100 shares of META", "warning", "order_validator"),
    ("Slippage Alert", "AMZN fill slippage 0.35% exceeds 0.25% threshold", "warning", "fill_validator"),
    ("Reconnection Event", "WebSocket reconnected after 3.2s disconnect", "info", "ws_manager"),
    ("Config Updated", "Risk limit max_position_pct changed from 5% to 4%", "info", "config_manager"),
    ("Daily P&L Update", "Running P&L: +$1,245.67 across 5 positions", "info", "pnl_tracker"),
    ("Regime Change", "Market regime shifted from sideways to bull", "info", "regime_detector"),
]

for i, (title, message, severity, source) in enumerate(alert_messages):
    ts = NOW - timedelta(minutes=int(np.random.randint(1, 180)))
    ack = severity in ("critical", "error") and np.random.random() > 0.5
    live_alerts.append({
        "id": f"ALT-{174000 + i}",
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "severity": severity,
        "title": title,
        "message": message,
        "source": source,
        "acknowledged": ack,
        "acknowledged_by": "operator-1" if ack else None,
    })
live_alerts.sort(key=lambda a: a["timestamp"], reverse=True)

# Alert rules
ALERT_RULES = [
    {"Rule ID": "BR-001", "Name": "Daily Loss Limit", "Condition": "daily_pnl < -$2,000", "Severity": "critical", "Action": "Kill switch + notify all", "Enabled": True},
    {"Rule ID": "BR-002", "Name": "Consecutive Losses", "Condition": "consecutive_losses >= 5", "Severity": "critical", "Action": "Kill switch + notify all", "Enabled": True},
    {"Rule ID": "BR-003", "Name": "Drawdown Threshold", "Condition": "intraday_drawdown > 3%", "Severity": "error", "Action": "Pause bot + notify", "Enabled": True},
    {"Rule ID": "BR-004", "Name": "Position Mismatch", "Condition": "internal_qty != broker_qty", "Severity": "error", "Action": "Flag + reconcile", "Enabled": True},
    {"Rule ID": "BR-005", "Name": "High Slippage", "Condition": "fill_slippage > 0.25%", "Severity": "warning", "Action": "Log + notify", "Enabled": True},
    {"Rule ID": "BR-006", "Name": "Stale Signal", "Condition": "signal_age > 30s", "Severity": "warning", "Action": "Reject signal", "Enabled": True},
    {"Rule ID": "BR-007", "Name": "Fill Rate Low", "Condition": "fill_rate < 85% (rolling 1h)", "Severity": "warning", "Action": "Review broker connection", "Enabled": True},
    {"Rule ID": "BR-008", "Name": "Circuit Breaker Trip", "Condition": "3 consecutive failed fills", "Severity": "critical", "Action": "Open circuit breaker", "Enabled": True},
    {"Rule ID": "BR-009", "Name": "Volume Spike", "Condition": "volume > 3x 20d avg", "Severity": "info", "Action": "Log for review", "Enabled": False},
    {"Rule ID": "BR-010", "Name": "Regime Change", "Condition": "regime transition detected", "Severity": "info", "Action": "Adjust parameters", "Enabled": True},
]

# Alert history (larger dataset)
n_history = 50
history_alerts = []
for i in range(n_history):
    ts = NOW - timedelta(hours=int(np.random.randint(1, 168)))
    sev = np.random.choice(SEVERITY_LEVELS, p=[0.08, 0.15, 0.37, 0.40])
    resolved = np.random.random() > 0.2
    history_alerts.append({
        "ID": f"ALT-{173950 + i}",
        "Timestamp": ts.strftime("%Y-%m-%d %H:%M"),
        "Severity": sev,
        "Title": np.random.choice([a[0] for a in alert_messages]),
        "Source": np.random.choice([a[3] for a in alert_messages]),
        "Status": "resolved" if resolved else "open",
        "Resolution Time": f"{int(np.random.randint(1, 120))} min" if resolved else "-",
    })
history_alerts.sort(key=lambda a: a["Timestamp"], reverse=True)

# Channel config
CHANNELS = [
    {"Channel": "Slack", "Type": "webhook", "Target": "#bot-alerts", "Severities": "critical, error, warning", "Status": "Active", "Deliveries (24h)": int(np.random.randint(20, 80))},
    {"Channel": "Email", "Type": "smtp", "Target": "team@axion.io", "Severities": "critical, error", "Status": "Active", "Deliveries (24h)": int(np.random.randint(5, 25))},
    {"Channel": "SMS", "Type": "twilio", "Target": "+1-555-***-1234", "Severities": "critical", "Status": "Active", "Deliveries (24h)": int(np.random.randint(0, 5))},
    {"Channel": "PagerDuty", "Type": "api", "Target": "service-key-***", "Severities": "critical", "Status": "Active", "Deliveries (24h)": int(np.random.randint(0, 3))},
    {"Channel": "Discord", "Type": "webhook", "Target": "#trading-bot", "Severities": "all", "Status": "Paused", "Deliveries (24h)": 0},
    {"Channel": "In-App", "Type": "internal", "Target": "Dashboard", "Severities": "all", "Status": "Active", "Deliveries (24h)": int(np.random.randint(30, 120))},
]

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Live Alerts",
    "Rules",
    "History",
    "Channels",
])

# =====================================================================
# Tab 1 - Live Alerts
# =====================================================================
with tab1:
    st.subheader("Recent Bot Alerts")

    if not BOT_AVAILABLE:
        st.info("Bot pipeline module not installed. Showing demo alert data.")

    # Summary metrics
    critical_count = sum(1 for a in live_alerts if a["severity"] == "critical")
    error_count = sum(1 for a in live_alerts if a["severity"] == "error")
    warning_count = sum(1 for a in live_alerts if a["severity"] == "warning")
    info_count = sum(1 for a in live_alerts if a["severity"] == "info")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Critical", critical_count)
    c2.metric("Error", error_count)
    c3.metric("Warning", warning_count)
    c4.metric("Info", info_count)

    st.markdown("---")

    # Severity filter
    sev_filter = st.selectbox(
        "Filter by Severity",
        ["All"] + SEVERITY_LEVELS,
        key="live_sev_filter",
    )

    filtered = live_alerts
    if sev_filter != "All":
        filtered = [a for a in live_alerts if a["severity"] == sev_filter]

    if filtered:
        for alert in filtered:
            sev = alert["severity"]
            if sev == "critical":
                with st.container():
                    st.error(f"**[{sev.upper()}]** {alert['title']} -- {alert['message']} (Source: {alert['source']}, {alert['timestamp']})")
            elif sev == "error":
                with st.container():
                    st.error(f"**[{sev.upper()}]** {alert['title']} -- {alert['message']} (Source: {alert['source']}, {alert['timestamp']})")
            elif sev == "warning":
                with st.container():
                    st.warning(f"**[{sev.upper()}]** {alert['title']} -- {alert['message']} (Source: {alert['source']}, {alert['timestamp']})")
            else:
                with st.container():
                    st.info(f"**[{sev.upper()}]** {alert['title']} -- {alert['message']} (Source: {alert['source']}, {alert['timestamp']})")
    else:
        st.info("No alerts matching the selected filter.")

    st.markdown("---")
    st.subheader("Alert Summary Table")
    alert_table = pd.DataFrame([{
        "ID": a["id"],
        "Time": a["timestamp"],
        "Severity": a["severity"].upper(),
        "Title": a["title"],
        "Source": a["source"],
        "Ack": "Yes" if a["acknowledged"] else "No",
    } for a in filtered])
    st.dataframe(alert_table, use_container_width=True, hide_index=True)

# =====================================================================
# Tab 2 - Rules
# =====================================================================
with tab2:
    st.subheader("Alert Rule Configuration")

    enabled_count = sum(1 for r in ALERT_RULES if r["Enabled"])
    disabled_count = len(ALERT_RULES) - enabled_count

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rules", len(ALERT_RULES))
    c2.metric("Enabled", enabled_count)
    c3.metric("Disabled", disabled_count)

    st.markdown("---")
    st.dataframe(pd.DataFrame(ALERT_RULES), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Create New Rule")

    col1, col2 = st.columns(2)
    with col1:
        rule_name = st.text_input("Rule Name", placeholder="My Custom Alert Rule")
        rule_condition = st.text_input("Condition", placeholder="e.g., daily_pnl < -$1,000")
        rule_severity = st.selectbox("Severity", SEVERITY_LEVELS, key="new_rule_sev")
    with col2:
        rule_action = st.text_input("Action", placeholder="e.g., Notify + pause bot")
        rule_cooldown = st.number_input("Cooldown (minutes)", min_value=0, max_value=60, value=5)
        rule_enabled = st.checkbox("Enabled", value=True, key="new_rule_enabled")

    if st.button("Create Rule", type="primary"):
        if rule_name and rule_condition:
            st.success(f"Rule '{rule_name}' created successfully")
        else:
            st.error("Please provide rule name and condition")

    st.markdown("---")
    st.subheader("Rule Trigger Counts (Last 7 Days)")
    trigger_data = pd.DataFrame({
        "Rule": [r["Rule ID"] for r in ALERT_RULES],
        "Name": [r["Name"] for r in ALERT_RULES],
        "Triggers": np.random.randint(0, 25, len(ALERT_RULES)).tolist(),
    })
    trigger_chart = trigger_data.set_index("Rule")["Triggers"]
    st.bar_chart(trigger_chart)

# =====================================================================
# Tab 3 - History
# =====================================================================
with tab3:
    st.subheader("Alert History")

    # Summary stats
    total_alerts = len(history_alerts)
    resolved_alerts = sum(1 for a in history_alerts if a["Status"] == "resolved")
    open_alerts = total_alerts - resolved_alerts
    resolution_rate = round(resolved_alerts / total_alerts * 100, 1) if total_alerts > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total (7d)", total_alerts)
    c2.metric("Resolved", resolved_alerts)
    c3.metric("Open", open_alerts)
    c4.metric("Resolution Rate", f"{resolution_rate}%")

    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        hist_sev = st.selectbox("Severity", ["All"] + SEVERITY_LEVELS, key="hist_sev")
    with col2:
        hist_status = st.selectbox("Status", ["All", "open", "resolved"], key="hist_status")
    with col3:
        hist_source = st.selectbox("Source", ["All"] + sorted(set(a["Source"] for a in history_alerts)), key="hist_source")

    filtered_history = history_alerts
    if hist_sev != "All":
        filtered_history = [a for a in filtered_history if a["Severity"] == hist_sev]
    if hist_status != "All":
        filtered_history = [a for a in filtered_history if a["Status"] == hist_status]
    if hist_source != "All":
        filtered_history = [a for a in filtered_history if a["Source"] == hist_source]

    st.dataframe(pd.DataFrame(filtered_history), use_container_width=True, hide_index=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### Severity Distribution (7 Days)")
        sev_dist = pd.Series([a["Severity"] for a in history_alerts]).value_counts()
        st.bar_chart(sev_dist)

    with col_right:
        st.markdown("#### Alerts Per Day")
        dates = pd.date_range(end=NOW, periods=7, freq="D")
        daily_counts = np.random.randint(3, 18, size=7).tolist()
        daily_df = pd.DataFrame({"Alerts": daily_counts}, index=[d.strftime("%m/%d") for d in dates])
        st.line_chart(daily_df)

# =====================================================================
# Tab 4 - Channels
# =====================================================================
with tab4:
    st.subheader("Alert Delivery Channels")

    active_channels = sum(1 for c in CHANNELS if c["Status"] == "Active")
    total_deliveries = sum(c["Deliveries (24h)"] for c in CHANNELS)

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Channels", active_channels)
    c2.metric("Total Channels", len(CHANNELS))
    c3.metric("Deliveries (24h)", total_deliveries)

    st.markdown("---")
    st.dataframe(pd.DataFrame(CHANNELS), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Configure Channel")

    col1, col2 = st.columns(2)
    with col1:
        ch_type = st.selectbox("Channel Type", ["Slack", "Email", "SMS", "PagerDuty", "Discord", "Webhook"])
        ch_target = st.text_input("Target", placeholder="e.g., #channel, email@example.com, +1-555-...")
    with col2:
        ch_severities = st.multiselect(
            "Alert Severities",
            options=SEVERITY_LEVELS,
            default=["critical", "error"],
            key="ch_sev_select",
        )
        ch_enabled = st.checkbox("Enabled", value=True, key="ch_enabled")

    if st.button("Save Channel", type="primary"):
        if ch_target:
            st.success(f"{ch_type} channel configured successfully")
        else:
            st.error("Please provide a target")

    st.markdown("---")
    st.subheader("Delivery Statistics")

    delivery_chart = pd.DataFrame({
        "Deliveries (24h)": [c["Deliveries (24h)"] for c in CHANNELS],
    }, index=[c["Channel"] for c in CHANNELS])
    st.bar_chart(delivery_chart)

    st.markdown("---")
    st.subheader("Escalation Policy")
    escalation_data = {
        "level_0": {"timeout": "5 min", "channels": ["In-App", "Slack"], "targets": ["on-call"]},
        "level_1": {"timeout": "10 min", "channels": ["Email", "Slack"], "targets": ["team-lead"]},
        "level_2": {"timeout": "15 min", "channels": ["SMS", "PagerDuty"], "targets": ["director"]},
    }
    st.json(escalation_data)
