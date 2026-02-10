"""PRD-122: Data Isolation & Row-Level Security Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timezone

from src.multi_tenancy import (
    AccessLevel,
    ResourceType,
    PolicyAction,
    TenancyConfig,
    TenantContext,
    TenantContextManager,
    QueryFilter,
    DataIsolationMiddleware,
    Policy,
    PolicyEngine,
    PolicyEvaluation,
    ROLE_HIERARCHY,
    SHARED_RESOURCE_TABLES,
)


def render():
    st.title("Data Isolation & Row-Level Security")

    tabs = st.tabs(["Tenant Overview", "Policies", "Access Audit", "Isolation Health"])

    # Setup demo data
    config = TenancyConfig()
    ctx_manager = TenantContextManager()
    query_filter = QueryFilter(config=config, context_manager=ctx_manager)
    middleware = DataIsolationMiddleware(config=config, context_manager=ctx_manager)
    engine = PolicyEngine()

    # Add demo policies
    demo_policies = [
        Policy(
            policy_id="pol_admin_all",
            workspace_id="ws_demo",
            resource_type=ResourceType.PORTFOLIO,
            role="admin",
            access_level=AccessLevel.ADMIN,
            action=PolicyAction.ALLOW,
            priority=10,
            description="Admin full access to portfolios",
        ),
        Policy(
            policy_id="pol_editor_write",
            workspace_id="ws_demo",
            resource_type=ResourceType.TRADE,
            role="editor",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
            priority=5,
            description="Editor write access to trades",
        ),
        Policy(
            policy_id="pol_viewer_read",
            workspace_id="ws_demo",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
            priority=1,
            description="Viewer read-only access to portfolios",
        ),
        Policy(
            policy_id="pol_deny_model",
            workspace_id="ws_demo",
            resource_type=ResourceType.MODEL,
            role="viewer",
            access_level=AccessLevel.NONE,
            action=PolicyAction.DENY,
            priority=10,
            description="Deny viewer access to ML models",
        ),
    ]
    for p in demo_policies:
        engine.add_policy(p)

    # Simulate some requests for audit data
    demo_requests = [
        {"X-Workspace-ID": "ws_demo", "X-User-ID": "user_1", "X-User-Roles": "admin"},
        {"X-Workspace-ID": "ws_demo", "X-User-ID": "user_2", "X-User-Roles": "editor"},
        {"X-Workspace-ID": "ws_demo", "X-User-ID": "user_3", "X-User-Roles": "viewer"},
        {"X-Workspace-ID": "ws_other", "X-User-ID": "user_4", "X-User-Roles": "viewer"},
    ]
    for headers in demo_requests:
        ctx_manager.clear_context()
        middleware.process_request(headers, ip_address="10.0.0.1")

    # Simulate query filters
    demo_ctx = TenantContext(workspace_id="ws_demo", user_id="user_1", roles=["admin"])
    ctx_manager.set_context(demo_ctx)
    query_filter.filter_query("portfolios", context=demo_ctx)
    query_filter.filter_query("market_data", context=demo_ctx)
    query_filter.filter_query("trades", {"symbol": "AAPL"}, context=demo_ctx)

    # ── Tab 1: Tenant Overview ───────────────────────────────────────
    with tabs[0]:
        st.subheader("Tenant Configuration")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("RLS Enabled", "Yes" if config.enforce_rls else "No")
        col2.metric("Audit Logging", "Yes" if config.audit_logging else "No")
        col3.metric("Rate Limit", f"{config.rate_limit_per_workspace}/min")
        col4.metric("Shared Tables", len(config.shared_tables))

        st.subheader("Role Hierarchy")
        role_data = []
        for role, rank in sorted(ROLE_HIERARCHY.items(), key=lambda x: x[1], reverse=True):
            role_data.append({"Role": role.capitalize(), "Priority": rank})
        st.dataframe(role_data, use_container_width=True)

        st.subheader("Shared Resource Tables")
        shared_data = [{"Table": t} for t in sorted(SHARED_RESOURCE_TABLES)]
        st.dataframe(shared_data, use_container_width=True)

        st.subheader("Resource Types")
        resource_data = [{"Type": rt.value, "Enum": rt.name} for rt in ResourceType]
        st.dataframe(resource_data, use_container_width=True)

    # ── Tab 2: Policies ──────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Active Policies")

        policies = engine.list_policies()
        policy_data = []
        for p in policies:
            policy_data.append({
                "ID": p.policy_id,
                "Workspace": p.workspace_id,
                "Resource": p.resource_type.value,
                "Role": p.role,
                "Access": p.access_level.value,
                "Action": p.action.value,
                "Priority": p.priority,
                "Description": p.description,
            })
        st.dataframe(policy_data, use_container_width=True)

        st.subheader("Policy Evaluation Simulator")
        eval_ctx = TenantContext(workspace_id="ws_demo", user_id="sim_user", roles=["viewer"])
        evaluations = []
        for rt in ResourceType:
            result = engine.evaluate(eval_ctx, rt, AccessLevel.READ)
            evaluations.append({
                "Resource": rt.value,
                "Allowed": result.allowed,
                "Reason": result.reason,
                "Policy": result.policy_id or "N/A",
            })
        st.dataframe(evaluations, use_container_width=True)

        st.subheader("Engine Stats")
        stats = engine.get_stats()
        scol1, scol2, scol3 = st.columns(3)
        scol1.metric("Total Policies", stats["total_policies"])
        scol2.metric("Evaluations", stats["total_evaluations"])
        scol3.metric("Cache Hit Rate", f"{stats['cache_hit_rate']:.0%}")

    # ── Tab 3: Access Audit ──────────────────────────────────────────
    with tabs[2]:
        st.subheader("Middleware Audit Log")

        mw_audit = middleware.get_audit_log()
        mw_data = []
        for entry in mw_audit:
            mw_data.append({
                "Workspace": entry.workspace_id,
                "User": entry.user_id,
                "Action": entry.action,
                "IP": entry.ip_address,
                "Allowed": entry.allowed,
                "Reason": entry.reason,
                "Time": entry.timestamp.strftime("%H:%M:%S"),
            })
        st.dataframe(mw_data, use_container_width=True)

        mw_stats = middleware.get_stats()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requests", mw_stats["total_requests"])
        col2.metric("Allowed", mw_stats["allowed_requests"])
        col3.metric("Blocked", mw_stats["blocked_requests"])

        st.subheader("Query Audit Log")
        q_audit = query_filter.get_audit_log()
        q_data = []
        for entry in q_audit:
            q_data.append({
                "Table": entry.table_name,
                "Workspace": entry.workspace_id,
                "User": entry.user_id,
                "Filters": ", ".join(entry.filters_applied),
                "Cross-WS": entry.cross_workspace_attempted,
                "Blocked": entry.blocked,
                "Reason": entry.reason,
            })
        st.dataframe(q_data, use_container_width=True)

    # ── Tab 4: Isolation Health ──────────────────────────────────────
    with tabs[3]:
        st.subheader("Data Isolation Health")

        checks = [
            {
                "Check": "Row-Level Security",
                "Status": "Active" if config.enforce_rls else "Inactive",
                "Details": "All queries filtered by workspace_id",
            },
            {
                "Check": "Audit Logging",
                "Status": "Active" if config.audit_logging else "Inactive",
                "Details": f"Retention: {config.audit_retention_days} days",
            },
            {
                "Check": "Cross-Tenant Blocking",
                "Status": "Active" if config.block_cross_tenant_requests else "Inactive",
                "Details": "Cross-workspace requests are blocked",
            },
            {
                "Check": "IP Restrictions",
                "Status": "Active" if config.ip_restriction_enabled else "Inactive",
                "Details": f"Max workspaces per IP: {config.max_workspaces_per_ip}",
            },
            {
                "Check": "Rate Limiting",
                "Status": "Active",
                "Details": f"{config.rate_limit_per_workspace} req/{config.rate_limit_window_seconds}s per workspace",
            },
            {
                "Check": "Policy Cache",
                "Status": "Active",
                "Details": f"TTL: {config.policy_cache_ttl}s",
            },
        ]
        st.dataframe(checks, use_container_width=True)

        active_count = sum(1 for c in checks if c["Status"] == "Active")
        total_count = len(checks)
        health_pct = active_count / total_count if total_count > 0 else 0.0

        st.subheader("Overall Health Score")
        st.progress(health_pct)
        st.metric("Active Controls", f"{active_count}/{total_count}")

        q_stats = query_filter.get_audit_stats()
        st.subheader("Query Filtering Stats")
        qcol1, qcol2, qcol3 = st.columns(3)
        qcol1.metric("Total Queries", q_stats["total_queries"])
        qcol2.metric("Blocked", q_stats["blocked_queries"])
        qcol3.metric("Cross-WS Attempts", q_stats["cross_workspace_attempts"])


try:
    st.set_page_config(
        page_title="Data Isolation & Row-Level Security",
        page_icon="shield",
        layout="wide",
    )
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

render()
