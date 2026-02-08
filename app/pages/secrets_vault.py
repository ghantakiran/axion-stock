"""PRD-124: Secrets Management & API Credential Vaulting Dashboard."""

import streamlit as st
from datetime import datetime, timedelta, timezone

from src.secrets_vault import (
    SecretsVault,
    CredentialRotation,
    AccessControl,
    SecretsClient,
    VaultConfig,
    SecretType,
    RotationStrategy,
    AccessAction,
)


try:
    st.set_page_config(page_title="Secrets Vault", page_icon="🔐", layout="wide")
except st.errors.StreamlitAPIException:
    pass



def render():
    st.title("Secrets Management & API Credential Vaulting")

    # Initialize demo components
    config = VaultConfig()
    vault = SecretsVault(config=config, encryption_key="dashboard-demo-key")
    rotation = CredentialRotation(vault)
    access_ctrl = AccessControl()
    client = SecretsClient(vault=vault)

    # Seed demo data
    _seed_demo_data(vault, rotation, access_ctrl, client)

    tabs = st.tabs(["Secrets Browser", "Rotation Status", "Access Audit", "Policies"])

    # ── Tab 1: Secrets Browser ────────────────────────────────────────
    with tabs[0]:
        st.subheader("Secrets Browser")

        secrets = vault.list_secrets()
        stats = vault.get_statistics()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Secrets", stats["total_secrets"])
        col2.metric("Total Versions", stats["total_versions"])
        col3.metric("Expired", stats["expired_secrets"])
        col4.metric("Deleted", stats["deleted_secrets"])

        # Type breakdown
        if stats["by_type"]:
            st.markdown("**Secrets by Type**")
            type_cols = st.columns(len(stats["by_type"]))
            for i, (stype, count) in enumerate(stats["by_type"].items()):
                type_cols[i].metric(stype.replace("_", " ").title(), count)

        # Search
        search_query = st.text_input("Search secrets", placeholder="Enter path, owner, or metadata...")
        if search_query:
            results = vault.search(search_query)
            st.info(f"Found {len(results)} matching secrets")
            display_secrets = results
        else:
            display_secrets = secrets

        # Secrets table
        if display_secrets:
            for secret in display_secrets:
                with st.expander(f"{secret.key_path} (v{secret.version})"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Type:** {secret.secret_type.value}")
                    c2.write(f"**Owner:** {secret.owner_service or 'N/A'}")
                    c3.write(f"**ID:** `{secret.secret_id}`")

                    c4, c5 = st.columns(2)
                    c4.write(f"**Created:** {secret.created_at.strftime('%Y-%m-%d %H:%M')}")
                    expires = secret.expires_at.strftime('%Y-%m-%d %H:%M') if secret.expires_at else "Never"
                    c5.write(f"**Expires:** {expires}")

                    versions = vault.get_versions(secret.key_path)
                    st.write(f"**Versions:** {len(versions)}")
        else:
            st.info("No secrets stored in the vault.")

    # ── Tab 2: Rotation Status ────────────────────────────────────────
    with tabs[1]:
        st.subheader("Credential Rotation Status")

        rot_stats = rotation.get_statistics()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Policies", rot_stats["total_policies"])
        col2.metric("Enabled", rot_stats["enabled_policies"])
        col3.metric("Due Now", rot_stats["due_rotations"])
        col4.metric("Total Rotations", rot_stats["total_rotations"])

        col5, col6, col7 = st.columns(3)
        col5.metric("Successful", rot_stats["successful_rotations"])
        col6.metric("Failed", rot_stats["failed_rotations"])
        col7.metric("Avg Duration (s)", rot_stats["avg_duration_seconds"])

        # Strategy breakdown
        if rot_stats["by_strategy"]:
            st.markdown("**Policies by Strategy**")
            strat_cols = st.columns(len(rot_stats["by_strategy"]))
            for i, (strategy, count) in enumerate(rot_stats["by_strategy"].items()):
                strat_cols[i].metric(strategy.replace("_", " ").title(), count)

        # Rotation history
        st.markdown("---")
        st.subheader("Recent Rotation History")
        history = rotation.get_rotation_history(limit=20)
        if history:
            for result in reversed(history):
                status = "Success" if result.success else "Failed"
                color = "green" if result.success else "red"
                st.markdown(
                    f":{color}[{status}] | `{result.key_path}` | "
                    f"v{result.old_version} -> v{result.new_version} | "
                    f"{result.duration_seconds:.4f}s"
                )
                if result.error:
                    st.error(f"Error: {result.error}")
        else:
            st.info("No rotation history available.")

        # Due rotations
        due = rotation.get_due_rotations()
        if due:
            st.markdown("---")
            st.subheader("Rotations Due")
            for policy in due:
                st.warning(f"`{policy.key_path}` - Strategy: {policy.strategy.value}")

    # ── Tab 3: Access Audit ───────────────────────────────────────────
    with tabs[2]:
        st.subheader("Access Audit Log")

        ac_stats = access_ctrl.get_statistics()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Entries", ac_stats["total_audit_entries"])
        col2.metric("Allowed", ac_stats["allowed_requests"])
        col3.metric("Denied", ac_stats["denied_requests"])
        col4.metric("Active Policies", ac_stats["active_policies"])

        # Action breakdown
        if ac_stats["by_action"]:
            st.markdown("**Requests by Action**")
            act_cols = st.columns(min(len(ac_stats["by_action"]), 5))
            for i, (act, count) in enumerate(ac_stats["by_action"].items()):
                act_cols[i % len(act_cols)].metric(act.title(), count)

        # Audit log entries
        st.markdown("---")
        audit_log = access_ctrl.get_audit_log(limit=50)
        if audit_log:
            for entry in reversed(audit_log):
                icon = "white_check_mark" if entry.allowed else "x"
                st.markdown(
                    f":{icon}: **{entry.action.value.upper()}** | "
                    f"Requester: `{entry.requester_id}` | "
                    f"Secret: `{entry.secret_id or 'N/A'}` | "
                    f"{entry.reason} | "
                    f"{entry.timestamp.strftime('%H:%M:%S')}"
                )
        else:
            st.info("No audit entries recorded.")

    # ── Tab 4: Policies ───────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Access Policies")

        policies = access_ctrl.list_policies()

        col1, col2 = st.columns(2)
        col1.metric("Total Policies", len(policies))
        col2.metric("Unique Subjects", ac_stats["unique_subjects"])

        if policies:
            for policy in policies:
                actions_str = ", ".join(a.value for a in policy.allowed_actions)
                expires = policy.expires_at.strftime('%Y-%m-%d %H:%M') if policy.expires_at else "Never"
                with st.expander(f"{policy.subject_id} -> {policy.path_pattern}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"**Policy ID:** `{policy.policy_id}`")
                    c2.write(f"**Actions:** {actions_str}")
                    c3, c4 = st.columns(2)
                    c3.write(f"**Created:** {policy.created_at.strftime('%Y-%m-%d %H:%M')}")
                    c4.write(f"**Expires:** {expires}")
                    if policy.description:
                        st.write(f"**Description:** {policy.description}")
        else:
            st.info("No access policies configured.")

        # Cache stats
        st.markdown("---")
        st.subheader("Client Cache Statistics")
        cache_stats = client.get_cache_stats()

        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("Cache Size", cache_stats["cache_size"])
        cc2.metric("Hits", cache_stats["hits"])
        cc3.metric("Misses", cache_stats["misses"])
        cc4.metric("Hit Rate", f"{cache_stats['hit_rate']:.1%}")


def _seed_demo_data(vault, rotation, access_ctrl, client):
    """Seed demo data for dashboard display."""
    now = datetime.now(timezone.utc)

    # Secrets
    vault.put("broker/alpaca/api_key", "PKTEST1234567890", SecretType.API_KEY, owner_service="trading-engine")
    vault.put("broker/alpaca/api_secret", "secret-abc-def-ghi", SecretType.API_KEY, owner_service="trading-engine")
    vault.put("broker/ib/api_key", "IB-KEY-999888777", SecretType.API_KEY, owner_service="trading-engine")
    vault.put("db/postgres/password", "pg-super-secret-pw", SecretType.DATABASE_PASSWORD, owner_service="data-service")
    vault.put("db/redis/password", "redis-auth-token", SecretType.DATABASE_PASSWORD, owner_service="cache-service")
    vault.put("oauth/polygon/token", "poly-oauth-tok-xyz", SecretType.OAUTH_TOKEN, owner_service="data-fetcher")
    vault.put("cert/tls/server", "-----BEGIN CERT-----...", SecretType.CERTIFICATE, owner_service="api-gateway")
    vault.put("generic/webhook/secret", "whsec_123456", SecretType.GENERIC, owner_service="alerting")

    # Multiple versions for some
    vault.put("broker/alpaca/api_key", "PKTEST-ROTATED-V2", SecretType.API_KEY, owner_service="trading-engine")
    vault.put("db/postgres/password", "pg-rotated-pw-v2", SecretType.DATABASE_PASSWORD, owner_service="data-service")

    # Rotation policies
    p1 = rotation.add_policy("broker/alpaca/api_key", RotationStrategy.CREATE_THEN_DELETE, interval_hours=168)
    p2 = rotation.add_policy("broker/ib/api_key", RotationStrategy.SWAP, interval_hours=720)
    p3 = rotation.add_policy("db/postgres/password", RotationStrategy.CREATE_THEN_DELETE, interval_hours=24)
    p4 = rotation.add_policy("oauth/polygon/token", RotationStrategy.MANUAL, interval_hours=8760)

    # Execute a rotation
    rotation.execute_rotation(p1.policy_id, new_value="PKTEST-ROTATED-V3")
    rotation.execute_rotation(p3.policy_id, new_value="pg-rotated-pw-v3")

    # Access policies
    access_ctrl.grant(
        "trading-engine", "broker/*", [AccessAction.READ, AccessAction.LIST],
        description="Trading engine reads broker credentials",
    )
    access_ctrl.grant(
        "data-service", "db/*", [AccessAction.READ],
        description="Data service reads DB passwords",
    )
    access_ctrl.grant(
        "admin", "**", [AccessAction.READ, AccessAction.WRITE, AccessAction.ROTATE, AccessAction.DELETE, AccessAction.LIST],
        description="Admin full access",
    )
    access_ctrl.grant(
        "risk-service", "broker/*/api_key", [AccessAction.READ],
        expires_at=now + timedelta(hours=48),
        description="Temporary read access for risk calculations",
    )

    # Generate audit entries
    access_ctrl.check_access("trading-engine", "broker/alpaca/api_key", AccessAction.READ, secret_id="sec-1")
    access_ctrl.check_access("trading-engine", "broker/ib/api_key", AccessAction.READ, secret_id="sec-2")
    access_ctrl.check_access("data-service", "db/postgres/password", AccessAction.READ, secret_id="sec-3")
    access_ctrl.check_access("risk-service", "broker/alpaca/api_key", AccessAction.READ, secret_id="sec-1")
    access_ctrl.check_access("unknown-svc", "broker/alpaca/api_key", AccessAction.DELETE, secret_id="sec-1")
    access_ctrl.check_access("admin", "cert/tls/server", AccessAction.READ, secret_id="sec-4")

    # Client cache warm-up
    client.get_secret("broker/alpaca/api_key")
    client.get_secret("db/postgres/password")
    client.get_secret("broker/alpaca/api_key")  # cache hit


render()
