"""Compliance & Audit Dashboard - PRD-71.

Compliance management features:
- Audit log viewer with filters
- Restricted securities list
- Compliance rules management
- Violation tracking and resolution
- Pre-trade compliance checks
- Regulatory report generation
"""

import sys
import os
from datetime import datetime, date, timedelta
import random
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

try:
    st.set_page_config(page_title="Compliance", page_icon="🛡️", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()


# Try to import enterprise modules
try:
    from src.enterprise.compliance import ComplianceManager, AuditLogger
    from src.enterprise.models import AuditAction
    COMPLIANCE_AVAILABLE = True
except ImportError:
    COMPLIANCE_AVAILABLE = False


def init_session_state():
    """Initialize session state."""
    if "demo_audit_logs" not in st.session_state:
        st.session_state.demo_audit_logs = generate_demo_audit_logs()
    if "demo_restricted" not in st.session_state:
        st.session_state.demo_restricted = generate_demo_restricted()
    if "demo_rules" not in st.session_state:
        st.session_state.demo_rules = generate_demo_rules()
    if "demo_violations" not in st.session_state:
        st.session_state.demo_violations = generate_demo_violations()


def generate_demo_audit_logs():
    """Generate demo audit log entries."""
    actions = [
        ("login", "auth", "success", None),
        ("login_failed", "auth", "failure", "Invalid password"),
        ("order_submit", "trading", "success", None),
        ("order_cancel", "trading", "success", None),
        ("order_fill", "trading", "success", None),
        ("rebalance", "trading", "success", None),
        ("strategy_create", "strategy", "success", None),
        ("strategy_update", "strategy", "success", None),
        ("account_update", "account", "success", None),
        ("setting_change", "admin", "success", None),
        ("api_key_create", "admin", "success", None),
        ("compliance_violation", "compliance", "warning", None),
    ]

    users = [
        ("user-001", "john@example.com"),
        ("user-002", "sarah@example.com"),
        ("user-003", "mike@example.com"),
    ]

    logs = []
    base_time = datetime.now()

    for i in range(100):
        action, category, status, error = random.choice(actions)
        user_id, email = random.choice(users)

        logs.append({
            "id": i + 1,
            "user_id": user_id,
            "user_email": email,
            "action": action,
            "action_category": category,
            "resource_type": random.choice(["order", "account", "strategy", "user", None]),
            "resource_id": f"res-{random.randint(100, 999)}",
            "status": status,
            "error_message": error,
            "ip_address": f"192.168.1.{random.randint(1, 255)}",
            "timestamp": base_time - timedelta(hours=i * 0.5 + random.random()),
        })

    return sorted(logs, key=lambda x: x["timestamp"], reverse=True)


def generate_demo_restricted():
    """Generate demo restricted securities list."""
    return [
        {
            "id": 1,
            "symbol": "XYZ",
            "reason": "insider",
            "restriction_type": "all",
            "notes": "Employee owns significant shares",
            "added_by": "John Smith",
            "start_date": date(2025, 11, 1),
            "end_date": date(2026, 3, 31),
            "is_active": True,
        },
        {
            "id": 2,
            "symbol": "ABC",
            "reason": "regulatory",
            "restriction_type": "buy_only",
            "notes": "Pending SEC investigation",
            "added_by": "Compliance Team",
            "start_date": date(2025, 12, 15),
            "end_date": None,
            "is_active": True,
        },
        {
            "id": 3,
            "symbol": "DEF",
            "reason": "risk_limit",
            "restriction_type": "all",
            "notes": "Excessive volatility",
            "added_by": "Risk Manager",
            "start_date": date(2026, 1, 10),
            "end_date": date(2026, 2, 28),
            "is_active": True,
        },
    ]


def generate_demo_rules():
    """Generate demo compliance rules."""
    return [
        {
            "id": "rule-001",
            "name": "Single Position Limit",
            "description": "No single position can exceed 15% of portfolio",
            "rule_type": "position_limit",
            "parameters": {"max_position_pct": 0.15},
            "severity": "critical",
            "is_active": True,
            "is_blocking": True,
        },
        {
            "id": "rule-002",
            "name": "Sector Concentration",
            "description": "No sector can exceed 35% of portfolio",
            "rule_type": "sector_limit",
            "parameters": {"max_sector_pct": 0.35},
            "severity": "warning",
            "is_active": True,
            "is_blocking": False,
        },
        {
            "id": "rule-003",
            "name": "Daily Loss Limit",
            "description": "Stop trading if daily loss exceeds 3%",
            "rule_type": "daily_loss_limit",
            "parameters": {"max_daily_loss_pct": 0.03},
            "severity": "critical",
            "is_active": True,
            "is_blocking": True,
        },
        {
            "id": "rule-004",
            "name": "Restricted Securities",
            "description": "Block trades on restricted securities list",
            "rule_type": "restricted_list",
            "parameters": {},
            "severity": "critical",
            "is_active": True,
            "is_blocking": True,
        },
    ]


def generate_demo_violations():
    """Generate demo compliance violations."""
    return [
        {
            "id": "vio-001",
            "rule_name": "Single Position Limit",
            "violation_type": "position_limit",
            "severity": "critical",
            "symbol": "NVDA",
            "action": "buy",
            "quantity": 100,
            "details": "Position would be 18.5% (limit: 15%)",
            "trade_blocked": True,
            "is_resolved": False,
            "timestamp": datetime(2026, 2, 5, 14, 30),
        },
        {
            "id": "vio-002",
            "rule_name": "Sector Concentration",
            "violation_type": "sector_limit",
            "severity": "warning",
            "symbol": "AAPL",
            "action": "buy",
            "quantity": 50,
            "details": "Technology sector would be 38% (limit: 35%)",
            "trade_blocked": False,
            "is_resolved": False,
            "timestamp": datetime(2026, 2, 4, 10, 15),
        },
        {
            "id": "vio-003",
            "rule_name": "Restricted Securities",
            "violation_type": "restricted_list",
            "severity": "critical",
            "symbol": "XYZ",
            "action": "buy",
            "quantity": 200,
            "details": "Symbol is on restricted list (reason: insider)",
            "trade_blocked": True,
            "is_resolved": True,
            "resolved_by": "John Smith",
            "resolved_at": datetime(2026, 2, 3, 16, 0),
            "resolution_notes": "Trade cancelled per compliance",
            "timestamp": datetime(2026, 2, 3, 11, 45),
        },
    ]


def render_audit_logs():
    """Render audit log viewer."""
    st.subheader("Audit Logs")

    logs = st.session_state.demo_audit_logs

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        action_filter = st.selectbox(
            "Action",
            ["All"] + list(set(log["action"] for log in logs)),
        )
    with col2:
        category_filter = st.selectbox(
            "Category",
            ["All", "auth", "trading", "strategy", "account", "admin", "compliance"],
        )
    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All", "success", "failure", "warning"],
        )
    with col4:
        user_filter = st.selectbox(
            "User",
            ["All"] + list(set(log["user_email"] for log in logs if log["user_email"])),
        )

    # Apply filters
    filtered = logs
    if action_filter != "All":
        filtered = [l for l in filtered if l["action"] == action_filter]
    if category_filter != "All":
        filtered = [l for l in filtered if l["action_category"] == category_filter]
    if status_filter != "All":
        filtered = [l for l in filtered if l["status"] == status_filter]
    if user_filter != "All":
        filtered = [l for l in filtered if l["user_email"] == user_filter]

    # Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Entries", len(filtered))
    with col2:
        success = len([l for l in filtered if l["status"] == "success"])
        st.metric("Successful", success)
    with col3:
        failures = len([l for l in filtered if l["status"] == "failure"])
        st.metric("Failures", failures, delta=f"-{failures}" if failures > 0 else None, delta_color="inverse")
    with col4:
        warnings = len([l for l in filtered if l["status"] == "warning"])
        st.metric("Warnings", warnings)

    st.divider()

    # Logs table
    if not filtered:
        st.info("No audit logs match your filters.")
        return

    for log in filtered[:50]:  # Show first 50
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2.5, 1.5, 1.5, 1.5, 1])

            with col1:
                status_icons = {"success": "✅", "failure": "❌", "warning": "⚠️"}
                icon = status_icons.get(log["status"], "📝")
                st.markdown(f"{icon} **{log['action'].replace('_', ' ').title()}**")
                st.caption(log["user_email"] or "System")

            with col2:
                st.text(log["action_category"].title() if log["action_category"] else "-")

            with col3:
                if log["resource_type"]:
                    st.text(f"{log['resource_type']}/{log['resource_id'][:8]}")
                else:
                    st.text("-")

            with col4:
                st.text(log["ip_address"])

            with col5:
                st.text(log["timestamp"].strftime("%H:%M"))
                st.caption(log["timestamp"].strftime("%b %d"))

            if log["error_message"]:
                st.error(f"Error: {log['error_message']}")


def render_restricted_securities():
    """Render restricted securities list."""
    st.subheader("Restricted Securities")

    restricted = st.session_state.demo_restricted

    # Add new restriction
    with st.expander("Add Restricted Security"):
        with st.form("add_restricted"):
            col1, col2 = st.columns(2)

            with col1:
                symbol = st.text_input("Symbol").upper()
                reason = st.selectbox(
                    "Reason",
                    ["insider", "regulatory", "risk_limit", "legal", "other"],
                )
                restriction_type = st.selectbox(
                    "Restriction Type",
                    ["all", "buy_only", "sell_only"],
                )

            with col2:
                start_date = st.date_input("Start Date", date.today())
                end_date = st.date_input("End Date (optional)", None)
                notes = st.text_area("Notes")

            if st.form_submit_button("Add Restriction", type="primary"):
                if symbol:
                    new_restriction = {
                        "id": len(restricted) + 1,
                        "symbol": symbol,
                        "reason": reason,
                        "restriction_type": restriction_type,
                        "notes": notes,
                        "added_by": "Current User",
                        "start_date": start_date,
                        "end_date": end_date,
                        "is_active": True,
                    }
                    st.session_state.demo_restricted.append(new_restriction)
                    st.success(f"Added {symbol} to restricted list")
                    st.rerun()

    st.divider()

    # Current restrictions table
    if not restricted:
        st.info("No restricted securities.")
        return

    for item in restricted:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 2, 2, 1])

            with col1:
                status = "🔴" if item["is_active"] else "⚪"
                st.markdown(f"{status} **{item['symbol']}**")

            with col2:
                restriction_labels = {
                    "all": "All Trading",
                    "buy_only": "Buy Restricted",
                    "sell_only": "Sell Restricted",
                }
                st.text(restriction_labels.get(item["restriction_type"], item["restriction_type"]))

            with col3:
                reason_labels = {
                    "insider": "🔒 Insider",
                    "regulatory": "⚖️ Regulatory",
                    "risk_limit": "📊 Risk Limit",
                    "legal": "📋 Legal",
                    "other": "📌 Other",
                }
                st.text(reason_labels.get(item["reason"], item["reason"]))
                if item["notes"]:
                    st.caption(item["notes"][:40] + "..." if len(item["notes"]) > 40 else item["notes"])

            with col4:
                end_str = item["end_date"].strftime("%b %d, %Y") if item["end_date"] else "Indefinite"
                st.text(f"{item['start_date'].strftime('%b %d')} → {end_str}")
                st.caption(f"Added by {item['added_by']}")

            with col5:
                if item["is_active"]:
                    if st.button("Remove", key=f"remove_{item['id']}", use_container_width=True):
                        item["is_active"] = False
                        st.rerun()

            st.divider()


def render_compliance_rules():
    """Render compliance rules management."""
    st.subheader("Compliance Rules")

    rules = st.session_state.demo_rules

    for rule in rules:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1])

            with col1:
                status = "🟢" if rule["is_active"] else "⚪"
                blocking = "🛑" if rule["is_blocking"] else ""
                st.markdown(f"{status} **{rule['name']}** {blocking}")
                st.caption(rule["description"])

            with col2:
                st.text(rule["rule_type"].replace("_", " ").title())

            with col3:
                severity_colors = {
                    "info": "🔵",
                    "warning": "🟡",
                    "critical": "🔴",
                }
                st.text(f"{severity_colors.get(rule['severity'], '⚪')} {rule['severity'].title()}")

            with col4:
                if st.button("Edit", key=f"edit_rule_{rule['id']}", use_container_width=True):
                    st.info("Rule editor would open here")

            st.divider()

    # Add new rule
    with st.expander("Create New Rule"):
        with st.form("create_rule"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Rule Name")
                description = st.text_area("Description")
                rule_type = st.selectbox(
                    "Rule Type",
                    ["position_limit", "sector_limit", "concentration", "daily_loss_limit", "custom"],
                )

            with col2:
                severity = st.selectbox("Severity", ["info", "warning", "critical"])
                is_blocking = st.checkbox("Block trades on violation")

                # Dynamic parameters based on rule type
                st.markdown("**Parameters**")
                if rule_type == "position_limit":
                    max_pct = st.slider("Max Position %", 5, 50, 15)
                elif rule_type == "sector_limit":
                    max_pct = st.slider("Max Sector %", 10, 60, 35)
                elif rule_type == "daily_loss_limit":
                    max_pct = st.slider("Max Daily Loss %", 1, 10, 3)

            if st.form_submit_button("Create Rule", type="primary"):
                if name:
                    st.success(f"Rule '{name}' created!")


def render_violations():
    """Render compliance violations."""
    st.subheader("Compliance Violations")

    violations = st.session_state.demo_violations

    # Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Violations", len(violations))
    with col2:
        unresolved = len([v for v in violations if not v["is_resolved"]])
        st.metric("Unresolved", unresolved, delta=f"+{unresolved}" if unresolved > 0 else None, delta_color="inverse")
    with col3:
        blocked = len([v for v in violations if v["trade_blocked"]])
        st.metric("Trades Blocked", blocked)
    with col4:
        critical = len([v for v in violations if v["severity"] == "critical"])
        st.metric("Critical", critical)

    st.divider()

    # Filter
    show_resolved = st.checkbox("Show resolved violations", value=False)

    filtered = violations if show_resolved else [v for v in violations if not v["is_resolved"]]

    if not filtered:
        st.success("No unresolved violations!")
        return

    for violation in filtered:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1])

            with col1:
                severity_icons = {"info": "🔵", "warning": "🟡", "critical": "🔴"}
                icon = severity_icons.get(violation["severity"], "⚪")
                resolved_badge = " ✓" if violation["is_resolved"] else ""

                st.markdown(f"{icon} **{violation['rule_name']}**{resolved_badge}")
                st.caption(violation["details"])

            with col2:
                blocked_text = "🛑 Blocked" if violation["trade_blocked"] else "⚠️ Warning"
                st.text(blocked_text)
                st.caption(f"{violation['action'].upper()} {violation['quantity']} {violation['symbol']}")

            with col3:
                st.text(violation["timestamp"].strftime("%b %d, %H:%M"))

            with col4:
                if not violation["is_resolved"]:
                    if st.button("Resolve", key=f"resolve_{violation['id']}", use_container_width=True):
                        violation["is_resolved"] = True
                        violation["resolved_at"] = datetime.now()
                        violation["resolved_by"] = "Current User"
                        st.rerun()
                else:
                    st.text("Resolved")
                    st.caption(violation.get("resolved_by", ""))

            st.divider()


def render_pretrade_check():
    """Render pre-trade compliance check simulator."""
    st.subheader("Pre-Trade Compliance Check")

    st.info("Simulate a pre-trade compliance check before submitting an order.")

    with st.form("pretrade_check"):
        col1, col2, col3 = st.columns(3)

        with col1:
            symbol = st.text_input("Symbol", value="AAPL").upper()
            action = st.selectbox("Action", ["buy", "sell"])

        with col2:
            quantity = st.number_input("Quantity", min_value=1, value=100)
            price = st.number_input("Price", min_value=0.01, value=185.50)

        with col3:
            account = st.selectbox("Account", ["Personal Brokerage", "Roth IRA", "Traditional IRA"])
            portfolio_value = st.number_input("Portfolio Value", value=142300)

        submitted = st.form_submit_button("Run Compliance Check", type="primary", use_container_width=True)

    if submitted:
        st.divider()
        st.subheader("Check Results")

        # Simulate checks
        order_value = quantity * price
        position_pct = order_value / portfolio_value

        checks = [
            {
                "rule": "Restricted Securities",
                "passed": symbol not in ["XYZ", "ABC", "DEF"],
                "message": f"{symbol} is not on restricted list" if symbol not in ["XYZ", "ABC", "DEF"] else f"{symbol} is RESTRICTED",
                "severity": "critical",
            },
            {
                "rule": "Single Position Limit",
                "passed": position_pct <= 0.15,
                "message": f"Position would be {position_pct*100:.1f}% (limit: 15%)",
                "severity": "critical",
            },
            {
                "rule": "Daily Loss Limit",
                "passed": True,
                "message": "Within daily loss limit",
                "severity": "critical",
            },
            {
                "rule": "Sector Concentration",
                "passed": True,
                "message": "Sector allocation within limits",
                "severity": "warning",
            },
        ]

        all_passed = all(c["passed"] for c in checks)
        blocking_failed = any(not c["passed"] and c["severity"] == "critical" for c in checks)

        # Display results
        if all_passed:
            st.success("✅ All compliance checks passed. Trade is allowed.")
        elif blocking_failed:
            st.error("🛑 Trade BLOCKED - Critical compliance violation detected.")
        else:
            st.warning("⚠️ Trade allowed with warnings.")

        # Show individual checks
        for check in checks:
            col1, col2 = st.columns([4, 1])
            with col1:
                icon = "✅" if check["passed"] else ("🛑" if check["severity"] == "critical" else "⚠️")
                st.markdown(f"{icon} **{check['rule']}**: {check['message']}")
            with col2:
                st.text("PASS" if check["passed"] else "FAIL")


def render_compliance_reports():
    """Render regulatory compliance reports."""
    st.subheader("Regulatory Reports")

    reports = [
        {"type": "Best Execution", "period": "Q4 2025", "status": "final", "submitted": datetime(2026, 1, 15)},
        {"type": "Audit Summary", "period": "2025", "status": "final", "submitted": datetime(2026, 1, 31)},
        {"type": "Trade Activity", "period": "January 2026", "status": "draft", "submitted": None},
    ]

    for report in reports:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1])

            with col1:
                status_icon = "✅" if report["status"] == "final" else "📝"
                st.markdown(f"{status_icon} **{report['type']} Report**")
                st.caption(f"Period: {report['period']}")

            with col2:
                st.text(report["status"].title())

            with col3:
                if report["submitted"]:
                    st.text(f"Submitted {report['submitted'].strftime('%b %d')}")
                else:
                    st.text("Not submitted")

            with col4:
                if report["status"] == "draft":
                    st.button("Finalize", key=f"finalize_{report['type']}", use_container_width=True)
                else:
                    st.button("Download", key=f"download_{report['type']}", use_container_width=True)

            st.divider()


def main():
    """Main application."""
    init_session_state()

    st.title("🛡️ Compliance & Audit")
    st.caption("Monitor compliance, manage restrictions, and review audit trails")

    # Check if enterprise features available
    if not COMPLIANCE_AVAILABLE:
        st.warning("Compliance features require Enterprise subscription. Using demo mode.")

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Audit Logs",
        "Restricted Securities",
        "Compliance Rules",
        "Violations",
        "Pre-Trade Check",
        "Reports",
    ])

    with tab1:
        render_audit_logs()

    with tab2:
        render_restricted_securities()

    with tab3:
        render_compliance_rules()

    with tab4:
        render_violations()

    with tab5:
        render_pretrade_check()

    with tab6:
        render_compliance_reports()

    # Sidebar stats
    with st.sidebar:
        st.subheader("Compliance Status")

        violations = st.session_state.demo_violations
        unresolved = len([v for v in violations if not v["is_resolved"]])
        restricted = len([r for r in st.session_state.demo_restricted if r["is_active"]])
        active_rules = len([r for r in st.session_state.demo_rules if r["is_active"]])

        if unresolved == 0:
            st.success("✅ All Clear")
        else:
            st.error(f"⚠️ {unresolved} Unresolved Violations")

        st.metric("Restricted Securities", restricted)
        st.metric("Active Rules", active_rules)
        st.metric("Audit Entries (24h)", len([l for l in st.session_state.demo_audit_logs if l["timestamp"] > datetime.now() - timedelta(hours=24)]))

        st.divider()

        st.subheader("Quick Actions")
        if st.button("Add Restriction", use_container_width=True):
            st.info("Navigate to Restricted Securities tab")

        if st.button("Run Compliance Check", use_container_width=True):
            st.info("Navigate to Pre-Trade Check tab")



main()
