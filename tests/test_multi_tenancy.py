"""Tests for PRD-122: Data Isolation & Row-Level Security."""

import threading
import time
from datetime import datetime, timezone

import pytest

from src.multi_tenancy.config import (
    AccessLevel,
    ResourceType,
    PolicyAction,
    TenancyConfig,
    ROLE_HIERARCHY,
    SHARED_RESOURCE_TABLES,
    DEFAULT_RATE_LIMIT,
    POLICY_CACHE_TTL_SECONDS,
)
from src.multi_tenancy.context import (
    TenantContext,
    TenantContextManager,
    get_global_context_manager,
)
from src.multi_tenancy.filters import (
    QueryFilter,
    QueryAuditEntry,
)
from src.multi_tenancy.middleware import (
    DataIsolationMiddleware,
    RateLimitState,
    MiddlewareAuditEntry,
)
from src.multi_tenancy.policies import (
    Policy,
    PolicyEvaluation,
    PolicyEngine,
    ACCESS_LEVEL_HIERARCHY,
)


# ── Config Tests ─────────────────────────────────────────────────────


class TestAccessLevel:
    def test_values(self):
        assert AccessLevel.NONE.value == "none"
        assert AccessLevel.READ.value == "read"
        assert AccessLevel.WRITE.value == "write"
        assert AccessLevel.ADMIN.value == "admin"

    def test_count(self):
        assert len(AccessLevel) == 4

    def test_string_enum(self):
        assert str(AccessLevel.READ) == "AccessLevel.READ"
        assert AccessLevel("read") == AccessLevel.READ


class TestResourceType:
    def test_values(self):
        assert ResourceType.PORTFOLIO.value == "portfolio"
        assert ResourceType.TRADE.value == "trade"
        assert ResourceType.ORDER.value == "order"
        assert ResourceType.WATCHLIST.value == "watchlist"
        assert ResourceType.MODEL.value == "model"
        assert ResourceType.REPORT.value == "report"

    def test_count(self):
        assert len(ResourceType) == 6


class TestPolicyAction:
    def test_values(self):
        assert PolicyAction.ALLOW.value == "allow"
        assert PolicyAction.DENY.value == "deny"

    def test_count(self):
        assert len(PolicyAction) == 2


class TestTenancyConfig:
    def test_defaults(self):
        cfg = TenancyConfig()
        assert cfg.enabled is True
        assert cfg.enforce_rls is True
        assert cfg.audit_logging is True
        assert cfg.rate_limit_per_workspace == DEFAULT_RATE_LIMIT
        assert cfg.block_cross_tenant_requests is True

    def test_shared_tables_default(self):
        cfg = TenancyConfig()
        assert "market_data" in cfg.shared_tables
        assert "exchange_info" in cfg.shared_tables
        assert len(cfg.shared_tables) == len(SHARED_RESOURCE_TABLES)

    def test_custom_config(self):
        cfg = TenancyConfig(
            enabled=False,
            enforce_rls=False,
            rate_limit_per_workspace=100,
        )
        assert cfg.enabled is False
        assert cfg.enforce_rls is False
        assert cfg.rate_limit_per_workspace == 100

    def test_role_hierarchy(self):
        assert ROLE_HIERARCHY["viewer"] < ROLE_HIERARCHY["editor"]
        assert ROLE_HIERARCHY["editor"] < ROLE_HIERARCHY["admin"]

    def test_allowed_cross_workspace_roles_default(self):
        cfg = TenancyConfig()
        assert "admin" in cfg.allowed_cross_workspace_roles


# ── Context Tests ────────────────────────────────────────────────────


class TestTenantContext:
    def test_basic_creation(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        assert ctx.workspace_id == "ws1"
        assert ctx.user_id == "u1"
        assert len(ctx.context_id) == 16
        assert isinstance(ctx.created_at, datetime)
        assert ctx.created_at.tzinfo is not None

    def test_roles_and_permissions(self):
        ctx = TenantContext(
            workspace_id="ws1",
            user_id="u1",
            roles=["admin", "editor"],
            permissions={"portfolio": "write"},
        )
        assert ctx.has_role("admin")
        assert ctx.has_role("editor")
        assert not ctx.has_role("viewer")
        assert ctx.has_permission("portfolio", "write")
        assert not ctx.has_permission("portfolio", "read")

    def test_highest_role(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["viewer", "admin"])
        assert ctx.highest_role() == "admin"

    def test_highest_role_single(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["editor"])
        assert ctx.highest_role() == "editor"

    def test_highest_role_empty(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=[])
        assert ctx.highest_role() is None

    def test_create_child_context(self):
        parent = TenantContext(
            workspace_id="ws1", user_id="u1", roles=["admin"], ip_address="10.0.0.1"
        )
        child = parent.create_child_context()
        assert child.workspace_id == "ws1"
        assert child.user_id == "u1"
        assert child.roles == ["admin"]
        assert child.parent_context_id == parent.context_id
        assert child.is_background is True
        assert child.context_id != parent.context_id
        assert child.ip_address == "10.0.0.1"

    def test_validate_valid(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        assert ctx.validate() is True

    def test_validate_missing_workspace(self):
        ctx = TenantContext(workspace_id="", user_id="u1")
        assert ctx.validate() is False

    def test_validate_missing_user(self):
        ctx = TenantContext(workspace_id="ws1", user_id="")
        assert ctx.validate() is False

    def test_validate_whitespace_only(self):
        ctx = TenantContext(workspace_id="  ", user_id="u1")
        assert ctx.validate() is False

    def test_default_fields(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        assert ctx.roles == []
        assert ctx.permissions == {}
        assert ctx.ip_address is None
        assert ctx.parent_context_id is None
        assert ctx.is_background is False


class TestTenantContextManager:
    def setup_method(self):
        self.manager = TenantContextManager()

    def test_set_and_get_context(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.manager.set_context(ctx)
        retrieved = self.manager.get_context()
        assert retrieved is not None
        assert retrieved.workspace_id == "ws1"

    def test_get_context_none(self):
        assert self.manager.get_context() is None

    def test_clear_context(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.manager.set_context(ctx)
        self.manager.clear_context()
        assert self.manager.get_context() is None

    def test_require_context_raises(self):
        with pytest.raises(RuntimeError, match="No tenant context set"):
            self.manager.require_context()

    def test_require_context_success(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.manager.set_context(ctx)
        result = self.manager.require_context()
        assert result.workspace_id == "ws1"

    def test_set_invalid_context(self):
        ctx = TenantContext(workspace_id="", user_id="u1")
        with pytest.raises(ValueError, match="Invalid tenant context"):
            self.manager.set_context(ctx)

    def test_context_by_id(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.manager.set_context(ctx)
        found = self.manager.get_context_by_id(ctx.context_id)
        assert found is not None
        assert found.workspace_id == "ws1"

    def test_context_by_id_not_found(self):
        assert self.manager.get_context_by_id("nonexistent") is None

    def test_create_background_context(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["admin"])
        self.manager.set_context(ctx)
        child = self.manager.create_background_context()
        assert child.workspace_id == "ws1"
        assert child.is_background is True
        assert child.parent_context_id == ctx.context_id

    def test_active_context_count(self):
        assert self.manager.active_context_count == 0
        ctx1 = TenantContext(workspace_id="ws1", user_id="u1")
        self.manager.set_context(ctx1)
        assert self.manager.active_context_count == 1

    def test_thread_isolation(self):
        """Verify contexts are thread-local."""
        ctx_main = TenantContext(workspace_id="ws_main", user_id="u1")
        self.manager.set_context(ctx_main)

        results = {}

        def thread_fn():
            # Should not see main thread's context
            results["thread_ctx"] = self.manager.get_context()
            ctx_thread = TenantContext(workspace_id="ws_thread", user_id="u2")
            self.manager.set_context(ctx_thread)
            results["thread_set_ctx"] = self.manager.get_context()

        t = threading.Thread(target=thread_fn)
        t.start()
        t.join()

        # Main thread context unchanged
        assert self.manager.get_context().workspace_id == "ws_main"
        # Thread had no context initially
        assert results["thread_ctx"] is None
        # Thread set its own context
        assert results["thread_set_ctx"].workspace_id == "ws_thread"

    def test_global_context_manager(self):
        mgr = get_global_context_manager()
        assert isinstance(mgr, TenantContextManager)


# ── Filter Tests ─────────────────────────────────────────────────────


class TestQueryFilter:
    def setup_method(self):
        self.config = TenancyConfig()
        self.ctx_manager = TenantContextManager()
        self.filter = QueryFilter(config=self.config, context_manager=self.ctx_manager)

    def test_filter_adds_workspace_id(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        result = self.filter.filter_query("portfolios")
        assert result["workspace_id"] == "ws1"

    def test_filter_with_existing_params(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        result = self.filter.filter_query("trades", {"symbol": "AAPL"})
        assert result["workspace_id"] == "ws1"
        assert result["symbol"] == "AAPL"

    def test_shared_resource_bypass(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        result = self.filter.filter_query("market_data")
        assert "workspace_id" not in result

    def test_is_shared_resource(self):
        assert self.filter.is_shared_resource("market_data") is True
        assert self.filter.is_shared_resource("exchange_info") is True
        assert self.filter.is_shared_resource("portfolios") is False

    def test_add_shared_table(self):
        self.filter.add_shared_table("custom_global")
        assert self.filter.is_shared_resource("custom_global") is True

    def test_remove_shared_table(self):
        self.filter.remove_shared_table("market_data")
        assert self.filter.is_shared_resource("market_data") is False

    def test_cross_workspace_blocked(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        with pytest.raises(PermissionError, match="Cross-workspace access denied"):
            self.filter.filter_query("portfolios", {"workspace_id": "ws_other"})

    def test_cross_workspace_allowed_for_admin(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["admin"])
        self.ctx_manager.set_context(ctx)
        result = self.filter.filter_query("portfolios", {"workspace_id": "ws_other"})
        # Admin can access, but workspace_id gets overridden to context's
        assert result["workspace_id"] == "ws1"

    def test_no_context_with_rls_enforced(self):
        with pytest.raises(PermissionError, match="No tenant context available"):
            self.filter.filter_query("portfolios")

    def test_no_context_rls_not_enforced(self):
        config = TenancyConfig(enforce_rls=False)
        f = QueryFilter(config=config, context_manager=self.ctx_manager)
        result = f.filter_query("portfolios")
        assert "workspace_id" not in result

    def test_detect_cross_workspace(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        assert self.filter.detect_cross_workspace("ws_other", ctx) is True
        assert self.filter.detect_cross_workspace("ws1", ctx) is False

    def test_detect_cross_workspace_no_context(self):
        assert self.filter.detect_cross_workspace("ws1") is False

    def test_audit_log(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        self.filter.filter_query("portfolios")
        log = self.filter.get_audit_log()
        assert len(log) == 1
        assert log[0].workspace_id == "ws1"
        assert log[0].table_name == "portfolios"

    def test_clear_audit_log(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        self.filter.filter_query("portfolios")
        self.filter.clear_audit_log()
        assert len(self.filter.get_audit_log()) == 0

    def test_audit_stats(self):
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        self.filter.filter_query("portfolios")
        self.filter.filter_query("trades")
        self.filter.filter_query("market_data")
        stats = self.filter.get_audit_stats()
        assert stats["total_queries"] == 3
        assert stats["blocked_queries"] == 0
        assert stats["queries_by_table"]["portfolios"] == 1

    def test_audit_disabled(self):
        config = TenancyConfig(audit_logging=False)
        f = QueryFilter(config=config, context_manager=self.ctx_manager)
        ctx = TenantContext(workspace_id="ws1", user_id="u1")
        self.ctx_manager.set_context(ctx)
        f.filter_query("portfolios")
        assert len(f.get_audit_log()) == 0

    def test_filter_with_explicit_context(self):
        ctx = TenantContext(workspace_id="ws_explicit", user_id="u_explicit")
        result = self.filter.filter_query("trades", context=ctx)
        assert result["workspace_id"] == "ws_explicit"


# ── Middleware Tests ─────────────────────────────────────────────────


class TestDataIsolationMiddleware:
    def setup_method(self):
        self.config = TenancyConfig()
        self.ctx_manager = TenantContextManager()
        self.middleware = DataIsolationMiddleware(
            config=self.config, context_manager=self.ctx_manager
        )

    def test_process_valid_request(self):
        headers = {
            "X-Workspace-ID": "ws1",
            "X-User-ID": "u1",
            "X-User-Roles": "admin,editor",
        }
        allowed, ctx, msg = self.middleware.process_request(headers)
        assert allowed is True
        assert ctx is not None
        assert ctx.workspace_id == "ws1"
        assert ctx.user_id == "u1"
        assert "admin" in ctx.roles
        assert "editor" in ctx.roles

    def test_missing_workspace_id(self):
        headers = {"X-User-ID": "u1"}
        allowed, ctx, msg = self.middleware.process_request(headers)
        assert allowed is False
        assert ctx is None
        assert "Missing X-Workspace-ID" in msg

    def test_missing_user_id(self):
        headers = {"X-Workspace-ID": "ws1"}
        allowed, ctx, msg = self.middleware.process_request(headers)
        assert allowed is False
        assert ctx is None
        assert "Missing X-User-ID" in msg

    def test_disabled_middleware(self):
        config = TenancyConfig(enabled=False)
        mw = DataIsolationMiddleware(config=config, context_manager=self.ctx_manager)
        allowed, ctx, msg = mw.process_request({})
        assert allowed is True
        assert ctx is None
        assert "disabled" in msg.lower()

    def test_cleanup_request(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers)
        assert self.ctx_manager.get_context() is not None
        self.middleware.cleanup_request()
        assert self.ctx_manager.get_context() is None

    def test_cross_tenant_detection(self):
        headers1 = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers1)
        # Try to access different workspace without clearing
        headers2 = {"X-Workspace-ID": "ws2", "X-User-ID": "u2"}
        allowed, ctx, msg = self.middleware.process_request(headers2)
        assert allowed is False
        assert "Cross-tenant" in msg

    def test_ip_workspace_limit(self):
        config = TenancyConfig(max_workspaces_per_ip=2)
        mw = DataIsolationMiddleware(config=config, context_manager=self.ctx_manager)

        for i in range(2):
            self.ctx_manager.clear_context()
            headers = {"X-Workspace-ID": f"ws{i}", "X-User-ID": "u1"}
            allowed, _, _ = mw.process_request(headers, ip_address="1.2.3.4")
            assert allowed is True

        self.ctx_manager.clear_context()
        headers = {"X-Workspace-ID": "ws_extra", "X-User-ID": "u1"}
        allowed, _, msg = mw.process_request(headers, ip_address="1.2.3.4")
        assert allowed is False
        assert "too many workspaces" in msg

    def test_ip_whitelist(self):
        config = TenancyConfig(ip_restriction_enabled=True)
        mw = DataIsolationMiddleware(config=config, context_manager=self.ctx_manager)
        mw.set_workspace_ip_whitelist("ws1", {"10.0.0.1"})

        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        allowed, _, _ = mw.process_request(headers, ip_address="10.0.0.1")
        assert allowed is True

        self.ctx_manager.clear_context()
        allowed, _, msg = mw.process_request(headers, ip_address="10.0.0.2")
        assert allowed is False
        assert "not in whitelist" in msg

    def test_ip_whitelist_no_restriction(self):
        config = TenancyConfig(ip_restriction_enabled=True)
        mw = DataIsolationMiddleware(config=config, context_manager=self.ctx_manager)
        # No whitelist for ws2 = all IPs allowed
        headers = {"X-Workspace-ID": "ws2", "X-User-ID": "u1"}
        allowed, _, _ = mw.process_request(headers, ip_address="10.0.0.99")
        assert allowed is True

    def test_rate_limiting(self):
        config = TenancyConfig(rate_limit_per_workspace=3, rate_limit_window_seconds=60)
        mw = DataIsolationMiddleware(config=config, context_manager=self.ctx_manager)

        for i in range(3):
            self.ctx_manager.clear_context()
            headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
            allowed, _, _ = mw.process_request(headers)
            assert allowed is True

        self.ctx_manager.clear_context()
        allowed, _, msg = mw.process_request({"X-Workspace-ID": "ws1", "X-User-ID": "u1"})
        assert allowed is False
        assert "Rate limit exceeded" in msg

    def test_get_rate_limit_state(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers)
        state = self.middleware.get_rate_limit_state("ws1")
        assert state is not None
        assert state.total_requests >= 1

    def test_get_rate_limit_state_unknown(self):
        assert self.middleware.get_rate_limit_state("unknown") is None

    def test_audit_log(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers)
        log = self.middleware.get_audit_log()
        assert len(log) >= 1
        assert log[0].workspace_id == "ws1"

    def test_clear_audit_log(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers)
        self.middleware.clear_audit_log()
        assert len(self.middleware.get_audit_log()) == 0

    def test_get_ip_workspace_count(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers, ip_address="5.5.5.5")
        assert self.middleware.get_ip_workspace_count("5.5.5.5") == 1

    def test_get_stats(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1"}
        self.middleware.process_request(headers)
        stats = self.middleware.get_stats()
        assert stats["total_requests"] >= 1
        assert "allowed_requests" in stats
        assert "blocked_requests" in stats

    def test_empty_roles(self):
        headers = {"X-Workspace-ID": "ws1", "X-User-ID": "u1", "X-User-Roles": ""}
        allowed, ctx, _ = self.middleware.process_request(headers)
        assert allowed is True
        assert ctx.roles == []


# ── Policy Engine Tests ──────────────────────────────────────────────


class TestPolicyEngine:
    def setup_method(self):
        self.engine = PolicyEngine(cache_ttl=300)
        self.ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["editor"])

    def test_add_and_list_policies(self):
        policy = Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        )
        self.engine.add_policy(policy)
        policies = self.engine.list_policies()
        assert len(policies) == 1
        assert policies[0].policy_id == policy.policy_id

    def test_remove_policy(self):
        policy = Policy(policy_id="test123", workspace_id="ws1",
                        resource_type=ResourceType.TRADE, role="viewer",
                        access_level=AccessLevel.READ)
        self.engine.add_policy(policy)
        assert self.engine.remove_policy("test123") is True
        assert len(self.engine.list_policies()) == 0

    def test_remove_nonexistent_policy(self):
        assert self.engine.remove_policy("nope") is False

    def test_list_filter_by_workspace(self):
        self.engine.add_policy(Policy(workspace_id="ws1", resource_type=ResourceType.PORTFOLIO,
                                      role="viewer", access_level=AccessLevel.READ))
        self.engine.add_policy(Policy(workspace_id="ws2", resource_type=ResourceType.PORTFOLIO,
                                      role="viewer", access_level=AccessLevel.READ))
        result = self.engine.list_policies(workspace_id="ws1")
        assert len(result) == 1

    def test_list_filter_by_resource_type(self):
        self.engine.add_policy(Policy(workspace_id="ws1", resource_type=ResourceType.PORTFOLIO,
                                      role="viewer", access_level=AccessLevel.READ))
        self.engine.add_policy(Policy(workspace_id="ws1", resource_type=ResourceType.TRADE,
                                      role="viewer", access_level=AccessLevel.READ))
        result = self.engine.list_policies(resource_type=ResourceType.TRADE)
        assert len(result) == 1

    def test_evaluate_allow(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
            description="editor+ can write portfolios",
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        assert result.allowed is True

    def test_evaluate_deny(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.MODEL,
            role="viewer",
            access_level=AccessLevel.NONE,
            action=PolicyAction.DENY,
            priority=10,
            description="Deny model access",
        ))
        ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["viewer"])
        result = self.engine.evaluate(ctx, ResourceType.MODEL, AccessLevel.READ)
        assert result.allowed is False
        assert "Denied" in result.reason

    def test_evaluate_no_matching_policy(self):
        result = self.engine.evaluate(self.ctx, ResourceType.REPORT, AccessLevel.READ)
        assert result.allowed is False
        assert "No matching policy" in result.reason

    def test_evaluate_insufficient_access(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.ADMIN)
        assert result.allowed is False
        assert "Insufficient" in result.reason

    def test_role_hierarchy_matching(self):
        # Policy for viewer, should match editor too
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.TRADE, AccessLevel.READ)
        assert result.allowed is True

    def test_role_hierarchy_no_match_below(self):
        # Policy for admin, should NOT match viewer
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="admin",
            access_level=AccessLevel.ADMIN,
            action=PolicyAction.ALLOW,
        ))
        viewer_ctx = TenantContext(workspace_id="ws1", user_id="u1", roles=["viewer"])
        result = self.engine.evaluate(viewer_ctx, ResourceType.TRADE, AccessLevel.READ)
        assert result.allowed is False

    def test_deny_priority_over_allow(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
            priority=5,
        ))
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.NONE,
            action=PolicyAction.DENY,
            priority=5,
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        assert result.allowed is False

    def test_policy_conditions(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
            conditions={"market_hours": True},
        ))
        result = self.engine.evaluate(
            self.ctx, ResourceType.TRADE, AccessLevel.WRITE,
            conditions={"market_hours": True}
        )
        assert result.allowed is True

    def test_policy_conditions_not_met(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
            conditions={"market_hours": True},
        ))
        result = self.engine.evaluate(
            self.ctx, ResourceType.TRADE, AccessLevel.WRITE,
            conditions={"market_hours": False}
        )
        assert result.allowed is False

    def test_caching(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        r1 = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        r2 = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        assert r1.allowed is True
        assert r2.allowed is True
        assert r2.cached is True

    def test_cache_cleared_on_policy_add(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        stats_before = self.engine.get_stats()
        assert stats_before["cache_size"] > 0

        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.READ,
        ))
        assert self.engine.get_stats()["cache_size"] == 0

    def test_clear_cache(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        self.engine.clear_cache()
        assert self.engine.get_stats()["cache_size"] == 0

    def test_evaluate_batch(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
        ))
        results = self.engine.evaluate_batch(self.ctx, [
            (ResourceType.PORTFOLIO, AccessLevel.READ),
            (ResourceType.TRADE, AccessLevel.READ),
        ])
        assert len(results) == 2
        assert results[0].allowed is True
        assert results[1].allowed is True

    def test_get_effective_access(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.WRITE,
            action=PolicyAction.ALLOW,
        ))
        level = self.engine.get_effective_access(self.ctx, ResourceType.PORTFOLIO)
        assert level == AccessLevel.WRITE

    def test_get_effective_access_none(self):
        level = self.engine.get_effective_access(self.ctx, ResourceType.REPORT)
        assert level == AccessLevel.NONE

    def test_get_stats(self):
        stats = self.engine.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["cache_hit_rate"] == 0.0

    def test_disabled_policy_not_matched(self):
        self.engine.add_policy(Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
            enabled=False,
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        assert result.allowed is False

    def test_global_policy_matches_any_workspace(self):
        self.engine.add_policy(Policy(
            workspace_id="",  # global
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
            action=PolicyAction.ALLOW,
        ))
        result = self.engine.evaluate(self.ctx, ResourceType.PORTFOLIO, AccessLevel.READ)
        assert result.allowed is True


# ── Dataclass Tests ──────────────────────────────────────────────────


class TestMultiTenancyDataclasses:
    def test_query_audit_entry(self):
        entry = QueryAuditEntry(
            workspace_id="ws1",
            user_id="u1",
            table_name="portfolios",
        )
        assert entry.workspace_id == "ws1"
        assert len(entry.audit_id) == 16
        assert entry.blocked is False
        assert entry.cross_workspace_attempted is False
        assert entry.timestamp.tzinfo is not None

    def test_rate_limit_state(self):
        state = RateLimitState(workspace_id="ws1")
        state.record_request()
        state.record_request()
        assert state.total_requests == 2
        count = state.count_in_window(60)
        assert count == 2

    def test_rate_limit_window_pruning(self):
        state = RateLimitState(workspace_id="ws1")
        # Add an old timestamp
        state.request_timestamps.append(time.time() - 120)
        state.record_request()
        count = state.count_in_window(60)
        # Only the recent request should remain
        assert count == 1

    def test_middleware_audit_entry(self):
        entry = MiddlewareAuditEntry(
            workspace_id="ws1",
            user_id="u1",
            action="context_established",
        )
        assert entry.workspace_id == "ws1"
        assert entry.allowed is True
        assert len(entry.entry_id) == 16
        assert entry.timestamp.tzinfo is not None

    def test_policy_dataclass(self):
        p = Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="admin",
            access_level=AccessLevel.ADMIN,
            action=PolicyAction.ALLOW,
        )
        assert p.workspace_id == "ws1"
        assert p.resource_type == ResourceType.TRADE
        assert p.enabled is True
        assert len(p.policy_id) == 16
        assert p.created_at.tzinfo is not None

    def test_policy_matches_basic(self):
        p = Policy(
            workspace_id="ws1",
            resource_type=ResourceType.PORTFOLIO,
            role="viewer",
            access_level=AccessLevel.READ,
        )
        assert p.matches("ws1", ResourceType.PORTFOLIO, "viewer") is True
        assert p.matches("ws2", ResourceType.PORTFOLIO, "viewer") is False
        assert p.matches("ws1", ResourceType.TRADE, "viewer") is False

    def test_policy_evaluate_conditions_empty(self):
        p = Policy(workspace_id="ws1", resource_type=ResourceType.PORTFOLIO,
                    role="viewer", access_level=AccessLevel.READ)
        assert p.evaluate_conditions({}) is True

    def test_policy_evaluate_conditions_list(self):
        p = Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.READ,
            conditions={"region": ["US", "EU"]},
        )
        assert p.evaluate_conditions({"region": "US"}) is True
        assert p.evaluate_conditions({"region": "APAC"}) is False

    def test_policy_evaluate_conditions_missing_key(self):
        p = Policy(
            workspace_id="ws1",
            resource_type=ResourceType.TRADE,
            role="viewer",
            access_level=AccessLevel.READ,
            conditions={"market_hours": True},
        )
        assert p.evaluate_conditions({}) is False

    def test_policy_evaluation_dataclass(self):
        ev = PolicyEvaluation(
            allowed=True,
            policy_id="pol1",
            reason="Allowed",
            access_level=AccessLevel.WRITE,
        )
        assert ev.allowed is True
        assert ev.policy_id == "pol1"
        assert ev.cached is False

    def test_access_level_hierarchy(self):
        assert ACCESS_LEVEL_HIERARCHY["none"] == 0
        assert ACCESS_LEVEL_HIERARCHY["read"] == 1
        assert ACCESS_LEVEL_HIERARCHY["write"] == 2
        assert ACCESS_LEVEL_HIERARCHY["admin"] == 3
        assert ACCESS_LEVEL_HIERARCHY["read"] < ACCESS_LEVEL_HIERARCHY["write"]
