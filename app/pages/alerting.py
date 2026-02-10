"""PRD-114: Notification & Alerting System Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timedelta
import random

from src.alerting import (
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    ChannelType,
    AlertConfig,
    Alert,
    AlertManager,
    RoutingRule,
    RoutingEngine,
    EscalationLevel,
    EscalationPolicy,
    EscalationManager,
)

try:
    st.set_page_config(page_title="Alerting", page_icon="\U0001f514")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()



def _generate_sample_alerts(manager: AlertManager) -> None:
    """Generate sample alerts for demonstration."""
    samples = [
        ("High CPU Usage", "CPU utilization at 95% on server-1", AlertSeverity.WARNING, AlertCategory.SYSTEM, "monitoring"),
        ("Trade Execution Failure", "Order AAPL-12345 failed to execute", AlertSeverity.ERROR, AlertCategory.TRADING, "execution_engine"),
        ("Data Feed Stale", "Polygon feed not updated in 5 minutes", AlertSeverity.WARNING, AlertCategory.DATA, "data_pipeline"),
        ("Unauthorized Access Attempt", "3 failed login attempts from 192.168.1.100", AlertSeverity.CRITICAL, AlertCategory.SECURITY, "auth_service"),
        ("Position Limit Breach", "TSLA position exceeds 10% portfolio limit", AlertSeverity.ERROR, AlertCategory.COMPLIANCE, "risk_engine"),
        ("Memory Pressure", "Server-2 memory at 88%", AlertSeverity.INFO, AlertCategory.SYSTEM, "monitoring"),
        ("Order Latency Spike", "Mean order latency jumped to 450ms", AlertSeverity.WARNING, AlertCategory.TRADING, "execution_engine"),
        ("Missing Market Data", "No quotes received for 12 symbols", AlertSeverity.ERROR, AlertCategory.DATA, "market_data"),
        ("API Rate Limit", "Approaching Polygon API rate limit (90%)", AlertSeverity.INFO, AlertCategory.SYSTEM, "api_gateway"),
        ("Wash Trade Detected", "Potential wash trade pattern on MSFT", AlertSeverity.CRITICAL, AlertCategory.COMPLIANCE, "surveillance"),
    ]

    for title, message, severity, category, source in samples:
        manager.fire(
            title=title,
            message=message,
            severity=severity,
            category=category,
            source=source,
            tags={"env": "production", "region": "us-east-1"},
        )

    # Acknowledge and resolve some alerts
    all_alerts = manager.get_alerts()
    if len(all_alerts) > 2:
        manager.acknowledge(all_alerts[5].alert_id, by="operator-1")
        manager.resolve(all_alerts[8].alert_id)


def _generate_sample_rules() -> list:
    """Generate sample routing rules."""
    return [
        RoutingRule(
            rule_id="R1",
            name="Critical to All Channels",
            severity_min=AlertSeverity.CRITICAL,
            channels=[ChannelType.EMAIL, ChannelType.SLACK, ChannelType.SMS, ChannelType.IN_APP],
            priority=100,
        ),
        RoutingRule(
            rule_id="R2",
            name="Errors to Email & Slack",
            severity_min=AlertSeverity.ERROR,
            channels=[ChannelType.EMAIL, ChannelType.SLACK],
            priority=50,
        ),
        RoutingRule(
            rule_id="R3",
            name="Security to SMS",
            severity_min=AlertSeverity.WARNING,
            categories=[AlertCategory.SECURITY],
            channels=[ChannelType.SMS, ChannelType.EMAIL],
            priority=80,
        ),
        RoutingRule(
            rule_id="R4",
            name="Trading Warnings to Slack",
            severity_min=AlertSeverity.WARNING,
            categories=[AlertCategory.TRADING],
            channels=[ChannelType.SLACK, ChannelType.IN_APP],
            priority=30,
        ),
        RoutingRule(
            rule_id="R5",
            name="Default In-App",
            severity_min=AlertSeverity.INFO,
            channels=[ChannelType.IN_APP],
            priority=0,
        ),
    ]


def _generate_sample_policies() -> list:
    """Generate sample escalation policies."""
    return [
        EscalationPolicy(
            policy_id="EP1",
            name="Standard Escalation",
            levels=[
                EscalationLevel(level=0, timeout_seconds=300, channels=[ChannelType.IN_APP], notify_targets=["on-call"]),
                EscalationLevel(level=1, timeout_seconds=600, channels=[ChannelType.EMAIL, ChannelType.SLACK], notify_targets=["team-lead"]),
                EscalationLevel(level=2, timeout_seconds=900, channels=[ChannelType.SMS], notify_targets=["director"]),
            ],
        ),
        EscalationPolicy(
            policy_id="EP2",
            name="Critical Fast Track",
            levels=[
                EscalationLevel(level=0, timeout_seconds=60, channels=[ChannelType.EMAIL, ChannelType.SMS], notify_targets=["on-call", "team-lead"]),
                EscalationLevel(level=1, timeout_seconds=180, channels=[ChannelType.SMS], notify_targets=["director", "cto"]),
            ],
        ),
    ]


def render():
    st.title("\U0001f514 Notification & Alerting System")

    tabs = st.tabs(["Active Alerts", "Alert History", "Routing Rules", "Escalation"])

    # Initialize manager and sample data
    manager = AlertManager()
    _generate_sample_alerts(manager)
    sample_rules = _generate_sample_rules()
    sample_policies = _generate_sample_policies()

    severity_colors = {
        "info": "blue",
        "warning": "orange",
        "error": "red",
        "critical": "red",
    }

    # ── Tab 1: Active Alerts ─────────────────────────────────────────
    with tabs[0]:
        st.subheader("Active Alerts")

        # Summary metrics
        counts = manager.get_alert_count_by_severity()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Critical", counts.get("critical", 0))
        col2.metric("Error", counts.get("error", 0))
        col3.metric("Warning", counts.get("warning", 0))
        col4.metric("Info", counts.get("info", 0))

        # Active alerts table
        active = manager.get_active_alerts()
        if active:
            alert_data = []
            for a in active:
                alert_data.append({
                    "ID": a.alert_id[:8],
                    "Severity": a.severity.value.upper(),
                    "Category": a.category.value.upper(),
                    "Title": a.title,
                    "Source": a.source,
                    "Occurrences": a.occurrence_count,
                    "Created": a.created_at.strftime("%H:%M:%S"),
                })
            st.dataframe(alert_data, use_container_width=True)
        else:
            st.info("No active alerts.")

        # Channel delivery stats
        st.subheader("Delivery Statistics")
        stats = manager.dispatcher.get_channel_stats()
        if stats:
            channel_data = [{"Channel": k.upper(), "Deliveries": v} for k, v in stats.items()]
            st.dataframe(channel_data, use_container_width=True)
        else:
            st.info("No deliveries yet.")

    # ── Tab 2: Alert History ─────────────────────────────────────────
    with tabs[1]:
        st.subheader("Alert History")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox(
                "Status",
                ["All"] + [s.value for s in AlertStatus],
            )
        with col2:
            severity_filter = st.selectbox(
                "Severity",
                ["All"] + [s.value for s in AlertSeverity],
            )
        with col3:
            category_filter = st.selectbox(
                "Category",
                ["All"] + [c.value for c in AlertCategory],
            )

        # Get filtered alerts
        filter_kwargs = {}
        if status_filter != "All":
            filter_kwargs["status"] = AlertStatus(status_filter)
        if severity_filter != "All":
            filter_kwargs["severity"] = AlertSeverity(severity_filter)
        if category_filter != "All":
            filter_kwargs["category"] = AlertCategory(category_filter)

        all_alerts = manager.get_alerts(**filter_kwargs)

        if all_alerts:
            history_data = []
            for a in all_alerts:
                history_data.append({
                    "ID": a.alert_id[:8],
                    "Status": a.status.value.upper(),
                    "Severity": a.severity.value.upper(),
                    "Category": a.category.value.upper(),
                    "Title": a.title,
                    "Source": a.source,
                    "Acknowledged By": a.acknowledged_by or "-",
                    "Created": a.created_at.strftime("%H:%M:%S"),
                })
            st.dataframe(history_data, use_container_width=True)
        else:
            st.info("No alerts match the selected filters.")

        st.subheader("Severity Distribution")
        sev_counts = manager.get_alert_count_by_severity()
        if sev_counts:
            chart_data = {k.upper(): v for k, v in sev_counts.items()}
            st.bar_chart(chart_data)

    # ── Tab 3: Routing Rules ─────────────────────────────────────────
    with tabs[2]:
        st.subheader("Routing Rules")
        st.caption("Rules are evaluated by priority (highest first). The first matching rule determines the notification channels.")

        if sample_rules:
            rule_data = []
            for r in sorted(sample_rules, key=lambda x: x.priority, reverse=True):
                rule_data.append({
                    "ID": r.rule_id,
                    "Name": r.name,
                    "Priority": r.priority,
                    "Min Severity": r.severity_min.value.upper(),
                    "Categories": ", ".join(c.value for c in r.categories) if r.categories else "All",
                    "Channels": ", ".join(c.value for c in r.channels),
                    "Enabled": r.enabled,
                })
            st.dataframe(rule_data, use_container_width=True)

        st.subheader("Channel Configuration")
        channel_config = [
            {"Channel": "Email", "Type": ChannelType.EMAIL.value, "Status": "Active", "Description": "SMTP-based email delivery"},
            {"Channel": "Slack", "Type": ChannelType.SLACK.value, "Status": "Active", "Description": "Slack webhook integration"},
            {"Channel": "SMS", "Type": ChannelType.SMS.value, "Status": "Active", "Description": "SMS via Twilio"},
            {"Channel": "Webhook", "Type": ChannelType.WEBHOOK.value, "Status": "Inactive", "Description": "Custom HTTP webhook"},
            {"Channel": "In-App", "Type": ChannelType.IN_APP.value, "Status": "Active", "Description": "In-application notification"},
        ]
        st.dataframe(channel_config, use_container_width=True)

    # ── Tab 4: Escalation ────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Escalation Policies")

        for policy in sample_policies:
            with st.expander(f"{policy.name} ({policy.policy_id})", expanded=True):
                st.markdown(f"**Enabled:** {'Yes' if policy.enabled else 'No'}")
                level_data = []
                for lvl in policy.levels:
                    level_data.append({
                        "Level": lvl.level,
                        "Timeout (s)": lvl.timeout_seconds,
                        "Channels": ", ".join(c.value for c in lvl.channels),
                        "Notify Targets": ", ".join(lvl.notify_targets),
                    })
                st.dataframe(level_data, use_container_width=True)

        st.subheader("Active Escalations")
        esc_manager = EscalationManager()
        for policy in sample_policies:
            esc_manager.add_policy(policy)

        # Simulate an active escalation
        critical_alerts = manager.get_alerts(severity=AlertSeverity.CRITICAL)
        if critical_alerts:
            esc_manager.start_escalation(critical_alerts[0].alert_id, "EP2")
            state = esc_manager.get_escalation_state(critical_alerts[0].alert_id)
            if state:
                esc_data = [{
                    "Alert ID": critical_alerts[0].alert_id[:8],
                    "Alert Title": critical_alerts[0].title,
                    "Policy": state["policy_id"],
                    "Current Level": state["current_level"],
                    "Time Remaining (s)": f"{state['time_remaining_seconds']:.0f}",
                    "Started": state["started_at"].strftime("%H:%M:%S"),
                }]
                st.dataframe(esc_data, use_container_width=True)
        else:
            st.info("No active escalations.")



render()
