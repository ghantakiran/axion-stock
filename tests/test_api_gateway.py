"""Tests for PRD-115: API Gateway & Advanced Rate Limiting."""

from datetime import datetime, timedelta, timezone

import pytest

from src.api_gateway.config import (
    RateLimitTier,
    VersionStatus,
    GatewayConfig,
    TierConfig,
    DEFAULT_TIERS,
)
from src.api_gateway.gateway import (
    RequestContext,
    GatewayResponse,
    APIGateway,
)
from src.api_gateway.rate_limiter import (
    RateLimitResult,
    SlidingWindowEntry,
    EndpointRateLimit,
    GatewayRateLimiter,
)
from src.api_gateway.analytics import (
    EndpointStats,
    APIAnalytics,
)
from src.api_gateway.versioning import (
    APIVersion,
    VersionManager,
)
from src.api_gateway.validator import (
    ValidationResult,
    RequestValidator,
)


# ── Config Tests ─────────────────────────────────────────────────────


class TestGatewayConfig:
    """Tests for enums, dataclass defaults, and tier mapping."""

    def test_rate_limit_tier_values(self):
        assert RateLimitTier.FREE.value == "free"
        assert RateLimitTier.PRO.value == "pro"
        assert RateLimitTier.ENTERPRISE.value == "enterprise"
        assert RateLimitTier.INTERNAL.value == "internal"
        assert len(RateLimitTier) == 4

    def test_version_status_values(self):
        assert VersionStatus.ACTIVE.value == "active"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.SUNSET.value == "sunset"
        assert VersionStatus.RETIRED.value == "retired"
        assert len(VersionStatus) == 4

    def test_gateway_config_defaults(self):
        cfg = GatewayConfig()
        assert cfg.enable_rate_limiting is True
        assert cfg.enable_analytics is True
        assert cfg.enable_versioning is True
        assert cfg.enable_validation is True
        assert cfg.default_rate_limit == 60
        assert cfg.burst_allowance == 1.5
        assert cfg.max_payload_bytes == 10_000_000
        assert cfg.default_version == "v1"

    def test_tier_config_defaults(self):
        tc = TierConfig()
        assert tc.tier == RateLimitTier.FREE
        assert tc.requests_per_minute == 10
        assert tc.requests_per_day == 1000
        assert tc.burst_multiplier == 1.5

    def test_default_tiers_mapping(self):
        assert len(DEFAULT_TIERS) == 4
        assert DEFAULT_TIERS[RateLimitTier.FREE].requests_per_minute == 10
        assert DEFAULT_TIERS[RateLimitTier.FREE].requests_per_day == 1000
        assert DEFAULT_TIERS[RateLimitTier.PRO].requests_per_minute == 60
        assert DEFAULT_TIERS[RateLimitTier.PRO].requests_per_day == 10000
        assert DEFAULT_TIERS[RateLimitTier.ENTERPRISE].requests_per_minute == 600
        assert DEFAULT_TIERS[RateLimitTier.ENTERPRISE].requests_per_day == 100000
        assert DEFAULT_TIERS[RateLimitTier.INTERNAL].requests_per_minute == 6000
        assert DEFAULT_TIERS[RateLimitTier.INTERNAL].requests_per_day == 1000000

    def test_tier_config_custom(self):
        tc = TierConfig(tier=RateLimitTier.PRO, requests_per_minute=120, requests_per_day=50000, burst_multiplier=2.0)
        assert tc.requests_per_minute == 120
        assert tc.burst_multiplier == 2.0


# ── API Gateway Tests ────────────────────────────────────────────────


class TestAPIGateway:
    """Tests for the central gateway orchestration."""

    def setup_method(self):
        self.gw = APIGateway()

    def test_process_request_allowed(self):
        ctx = RequestContext(path="/api/stocks", method="GET", user_id="user1")
        resp = self.gw.process_request(ctx)
        assert resp.allowed is True
        assert resp.status_code == 200
        assert resp.rejection_reason is None

    def test_process_request_rate_limit_exceeded(self):
        # FREE tier burst limit = 10 * 1.5 = 15
        for i in range(15):
            ctx = RequestContext(path="/api/data", method="GET", user_id="flood_user")
            self.gw.process_request(ctx)
        ctx = RequestContext(path="/api/data", method="GET", user_id="flood_user")
        resp = self.gw.process_request(ctx)
        assert resp.allowed is False
        assert resp.status_code == 429
        assert "Rate limit" in resp.rejection_reason

    def test_process_request_validation_failure(self):
        cfg = GatewayConfig(max_payload_bytes=100)
        gw = APIGateway(config=cfg)
        ctx = RequestContext(path="/upload", method="POST", body_size=200)
        resp = gw.process_request(ctx)
        assert resp.allowed is False
        assert resp.status_code == 400
        assert "Payload size" in resp.rejection_reason

    def test_pre_hook_called(self):
        called = []

        def hook(ctx, resp):
            called.append(ctx.path)

        self.gw.add_pre_hook(hook)
        ctx = RequestContext(path="/hook-test", method="GET")
        self.gw.process_request(ctx)
        assert called == ["/hook-test"]

    def test_post_hook_called(self):
        called = []

        def hook(ctx, resp):
            called.append(resp.status_code)

        self.gw.add_post_hook(hook)
        ctx = RequestContext(path="/post", method="GET")
        self.gw.process_request(ctx)
        assert called == [200]

    def test_health_check(self):
        health = self.gw.get_health()
        assert health["gateway"] == "healthy"
        assert health["rate_limiter"] == "enabled"
        assert health["analytics"] == "enabled"
        assert health["versioning"] == "enabled"
        assert health["validation"] == "enabled"

    def test_health_check_disabled(self):
        cfg = GatewayConfig(enable_rate_limiting=False, enable_analytics=False)
        gw = APIGateway(config=cfg)
        health = gw.get_health()
        assert health["rate_limiter"] == "disabled"
        assert health["analytics"] == "disabled"

    def test_rate_limit_headers_in_response(self):
        ctx = RequestContext(path="/api/test", method="GET", user_id="u1")
        resp = self.gw.process_request(ctx)
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers


# ── Rate Limiter Tests ───────────────────────────────────────────────


class TestGatewayRateLimiter:
    """Tests for the sliding-window rate limiter."""

    def setup_method(self):
        self.limiter = GatewayRateLimiter()

    def test_check_allowed(self):
        result = self.limiter.check_rate_limit("user1", "/api/test", RateLimitTier.PRO)
        assert result.allowed is True
        assert result.remaining > 0

    def test_check_exceeded_free_tier(self):
        # FREE tier: 10 rpm * 1.5 burst = 15 max
        for _ in range(15):
            self.limiter.check_rate_limit("userX", "/api/a", RateLimitTier.FREE)
        result = self.limiter.check_rate_limit("userX", "/api/a", RateLimitTier.FREE)
        assert result.allowed is False
        assert result.retry_after_seconds is not None

    def test_per_endpoint_limit(self):
        self.limiter.add_endpoint_limit("/api/heavy", 2, 1.0)
        self.limiter.check_rate_limit("u1", "/api/heavy", RateLimitTier.INTERNAL)
        self.limiter.check_rate_limit("u1", "/api/heavy", RateLimitTier.INTERNAL)
        result = self.limiter.check_rate_limit("u1", "/api/heavy", RateLimitTier.INTERNAL)
        assert result.allowed is False

    def test_user_quota_daily(self):
        self.limiter.set_user_quota("quotaUser", daily_limit=3, monthly_limit=100)
        for _ in range(3):
            r = self.limiter.check_rate_limit("quotaUser", "/api/q", RateLimitTier.INTERNAL)
            assert r.allowed is True
        r = self.limiter.check_rate_limit("quotaUser", "/api/q", RateLimitTier.INTERNAL)
        assert r.allowed is False

    def test_get_user_usage(self):
        self.limiter.set_user_quota("u2", daily_limit=50, monthly_limit=500)
        self.limiter.check_rate_limit("u2", "/api/x", RateLimitTier.PRO)
        self.limiter.check_rate_limit("u2", "/api/x", RateLimitTier.PRO)
        usage = self.limiter.get_user_usage("u2")
        assert usage["daily_used"] == 2
        assert usage["monthly_used"] == 2
        assert usage["daily_limit"] == 50

    def test_rate_limit_headers(self):
        result = RateLimitResult(allowed=True, limit=60, remaining=59, retry_after_seconds=None)
        headers = self.limiter.get_rate_limit_headers(result)
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "59"
        assert "Retry-After" not in headers

    def test_rate_limit_headers_with_retry(self):
        result = RateLimitResult(allowed=False, limit=60, remaining=0, retry_after_seconds=30)
        headers = self.limiter.get_rate_limit_headers(result)
        assert headers["Retry-After"] == "30"

    def test_sliding_window_cleanup(self):
        # Insert entries with old timestamps
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        key = "cleanup_user:/api/test"
        self.limiter._windows[key] = [
            SlidingWindowEntry(timestamp=old_time, count=1),
            SlidingWindowEntry(timestamp=old_time, count=1),
        ]
        self.limiter._cleanup_old_entries(key, 60)
        assert len(self.limiter._windows[key]) == 0

    def test_reset_user(self):
        self.limiter.set_user_quota("reset_u", daily_limit=100, monthly_limit=1000)
        self.limiter.check_rate_limit("reset_u", "/api/a", RateLimitTier.PRO)
        self.limiter.check_rate_limit("reset_u", "/api/b", RateLimitTier.PRO)
        self.limiter.reset_user("reset_u")
        usage = self.limiter.get_user_usage("reset_u")
        assert usage["daily_used"] == 0
        assert usage["monthly_used"] == 0
        # Windows should be cleared
        assert not any(k.startswith("reset_u:") for k in self.limiter._windows)

    def test_unknown_user_usage(self):
        usage = self.limiter.get_user_usage("nobody")
        assert usage["daily_used"] == 0
        assert usage["daily_limit"] == 0


# ── Analytics Tests ──────────────────────────────────────────────────


class TestAPIAnalytics:
    """Tests for endpoint analytics and percentiles."""

    def setup_method(self):
        self.analytics = APIAnalytics()

    def test_record_request(self):
        self.analytics.record_request("/api/a", "GET", 200, 10.0, user_id="u1")
        stats = self.analytics.get_endpoint_stats("/api/a", "GET")
        assert stats is not None
        assert stats.total_requests == 1

    def test_endpoint_stats_accumulation(self):
        for _ in range(5):
            self.analytics.record_request("/api/b", "POST", 200, 20.0)
        self.analytics.record_request("/api/b", "POST", 500, 100.0)
        stats = self.analytics.get_endpoint_stats("/api/b", "POST")
        assert stats.total_requests == 6
        assert stats.error_count == 1
        assert stats.avg_latency_ms == pytest.approx((5 * 20.0 + 100.0) / 6, rel=0.01)

    def test_percentiles(self):
        for lat in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            self.analytics.record_request("/api/perc", "GET", 200, float(lat))
        stats = self.analytics.get_endpoint_stats("/api/perc", "GET")
        assert stats.p50 > 0
        assert stats.p95 >= stats.p50
        assert stats.p99 >= stats.p95

    def test_percentiles_empty(self):
        stats = EndpointStats(path="/empty", method="GET")
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0
        assert stats.p99 == 0.0

    def test_top_endpoints(self):
        for _ in range(10):
            self.analytics.record_request("/api/hot", "GET", 200, 5.0)
        for _ in range(3):
            self.analytics.record_request("/api/cold", "GET", 200, 5.0)
        top = self.analytics.get_top_endpoints(n=2)
        assert len(top) == 2
        assert top[0].path == "/api/hot"

    def test_top_users(self):
        for _ in range(8):
            self.analytics.record_request("/api/x", "GET", 200, 1.0, user_id="power_user")
        for _ in range(2):
            self.analytics.record_request("/api/x", "GET", 200, 1.0, user_id="casual")
        top = self.analytics.get_top_users(n=5)
        assert top[0]["user_id"] == "power_user"
        assert top[0]["requests"] == 8

    def test_error_endpoints(self):
        for _ in range(10):
            self.analytics.record_request("/api/fail", "GET", 500, 5.0)
        for _ in range(5):
            self.analytics.record_request("/api/ok", "GET", 200, 5.0)
        errors = self.analytics.get_error_endpoints()
        paths = [e.path for e in errors]
        assert "/api/fail" in paths
        assert "/api/ok" not in paths

    def test_summary(self):
        self.analytics.record_request("/a", "GET", 200, 10.0, user_id="u1")
        self.analytics.record_request("/b", "POST", 201, 20.0, user_id="u2")
        self.analytics.record_request("/b", "POST", 500, 50.0, user_id="u2")
        summary = self.analytics.get_summary()
        assert summary["total_requests"] == 3
        assert summary["total_endpoints"] == 2
        assert summary["total_errors"] == 1
        assert summary["total_users"] == 2
        assert summary["avg_latency_ms"] == pytest.approx(80.0 / 3, rel=0.01)

    def test_summary_empty(self):
        summary = self.analytics.get_summary()
        assert summary["total_requests"] == 0
        assert summary["avg_latency_ms"] == 0.0
        assert summary["error_rate"] == 0.0

    def test_reset(self):
        self.analytics.record_request("/api/x", "GET", 200, 1.0, user_id="u1")
        self.analytics.reset()
        assert self.analytics.get_all_stats() == {}
        assert self.analytics.get_top_users() == []

    def test_get_all_stats(self):
        self.analytics.record_request("/a", "GET", 200, 1.0)
        self.analytics.record_request("/b", "POST", 200, 2.0)
        all_stats = self.analytics.get_all_stats()
        assert len(all_stats) == 2

    def test_error_rate_property(self):
        stats = EndpointStats(path="/x", method="GET", total_requests=10, error_count=3)
        assert stats.error_rate == pytest.approx(0.3)

    def test_avg_latency_property_zero(self):
        stats = EndpointStats(path="/x", method="GET")
        assert stats.avg_latency_ms == 0.0


# ── Version Manager Tests ────────────────────────────────────────────


class TestVersionManager:
    """Tests for API versioning and lifecycle."""

    def setup_method(self):
        self.vm = VersionManager(default_version="v1")

    def test_register_version(self):
        v = self.vm.register_version("v1", description="Initial release", changelog=["First version"])
        assert v.version == "v1"
        assert v.status == VersionStatus.ACTIVE
        assert v.description == "Initial release"
        assert len(v.changelog) == 1

    def test_deprecate_version(self):
        self.vm.register_version("v1")
        sunset = datetime(2025, 12, 31, tzinfo=timezone.utc)
        self.vm.deprecate_version("v1", sunset_at=sunset)
        v = self.vm.get_version("v1")
        assert v.status == VersionStatus.DEPRECATED
        assert v.sunset_at == sunset

    def test_sunset_version(self):
        self.vm.register_version("v1")
        self.vm.sunset_version("v1")
        v = self.vm.get_version("v1")
        assert v.status == VersionStatus.SUNSET
        assert v.sunset_at is not None

    def test_retire_version(self):
        self.vm.register_version("v1")
        self.vm.retire_version("v1")
        v = self.vm.get_version("v1")
        assert v.status == VersionStatus.RETIRED

    def test_resolve_version_active(self):
        self.vm.register_version("v2", description="Second version")
        resolved, headers = self.vm.resolve_version("v2")
        assert resolved == "v2"
        assert len(headers) == 0

    def test_resolve_version_deprecated(self):
        self.vm.register_version("v1")
        sunset = datetime(2025, 6, 1, tzinfo=timezone.utc)
        self.vm.deprecate_version("v1", sunset_at=sunset)
        resolved, headers = self.vm.resolve_version("v1")
        assert resolved == "v1"
        assert "Deprecation" in headers
        assert "Sunset" in headers

    def test_resolve_version_unknown_fallback(self):
        resolved, headers = self.vm.resolve_version("v99")
        assert resolved == "v1"  # fallback to default

    def test_resolve_version_retired_warning(self):
        self.vm.register_version("v1")
        self.vm.retire_version("v1")
        resolved, headers = self.vm.resolve_version("v1")
        assert resolved == "v1"
        assert "X-API-Warn" in headers

    def test_sunset_headers_rfc8594(self):
        self.vm.register_version("v1")
        sunset = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.vm.deprecate_version("v1", sunset_at=sunset)
        headers = self.vm.get_sunset_headers("v1")
        assert "Sunset" in headers
        assert "Deprecation" in headers
        assert headers["Deprecation"] == "true"

    def test_active_versions(self):
        self.vm.register_version("v1")
        self.vm.register_version("v2")
        self.vm.register_version("v3")
        self.vm.retire_version("v1")
        active = self.vm.get_active_versions()
        versions = [a.version for a in active]
        assert "v1" not in versions
        assert "v2" in versions
        assert "v3" in versions

    def test_is_supported(self):
        self.vm.register_version("v1")
        assert self.vm.is_supported("v1") is True
        self.vm.retire_version("v1")
        assert self.vm.is_supported("v1") is False
        assert self.vm.is_supported("v_nonexistent") is False

    def test_deprecate_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown API version"):
            self.vm.deprecate_version("v_unknown")

    def test_resolve_version_none_uses_default(self):
        self.vm.register_version("v1")
        resolved, _ = self.vm.resolve_version(None)
        assert resolved == "v1"


# ── Request Validator Tests ──────────────────────────────────────────


class TestRequestValidator:
    """Tests for request validation rules."""

    def setup_method(self):
        self.validator = RequestValidator()

    def test_valid_request(self):
        ctx = RequestContext(path="/api/test", method="GET", body_size=100)
        result = self.validator.validate_request(ctx)
        assert result.valid is True
        assert result.errors == []

    def test_payload_too_large(self):
        cfg = GatewayConfig(max_payload_bytes=500)
        validator = RequestValidator(config=cfg)
        ctx = RequestContext(path="/upload", method="POST", body_size=1000)
        result = validator.validate_request(ctx)
        assert result.valid is False
        assert any("Payload size" in e for e in result.errors)

    def test_blocked_ip(self):
        self.validator.add_ip_blocklist("10.0.0.99")
        ctx = RequestContext(
            path="/api/data", method="GET",
            headers={"X-Forwarded-For": "10.0.0.99"},
        )
        result = self.validator.validate_request(ctx)
        assert result.valid is False
        assert any("blocked" in e for e in result.errors)

    def test_ip_allowlist_enforcement(self):
        self.validator.add_ip_allowlist("192.168.1.1")
        ctx = RequestContext(
            path="/api/data", method="GET",
            headers={"X-Forwarded-For": "10.0.0.5"},
        )
        result = self.validator.validate_request(ctx)
        assert result.valid is False
        assert any("not in allowlist" in e for e in result.errors)

    def test_ip_allowlist_passes(self):
        self.validator.add_ip_allowlist("192.168.1.1")
        ctx = RequestContext(
            path="/api/data", method="GET",
            headers={"X-Forwarded-For": "192.168.1.1"},
        )
        result = self.validator.validate_request(ctx)
        assert result.valid is True

    def test_required_headers_missing(self):
        self.validator.add_required_headers("/api/secure", ["Authorization", "X-Request-ID"])
        ctx = RequestContext(
            path="/api/secure/resource", method="GET",
            headers={"X-Request-ID": "abc"},
        )
        result = self.validator.validate_request(ctx)
        assert result.valid is False
        assert any("Authorization" in e for e in result.errors)

    def test_required_headers_present(self):
        self.validator.add_required_headers("/api/secure", ["Authorization"])
        ctx = RequestContext(
            path="/api/secure/resource", method="GET",
            headers={"Authorization": "Bearer token"},
        )
        result = self.validator.validate_request(ctx)
        assert result.valid is True

    def test_check_payload_size(self):
        assert self.validator.check_payload_size(100) is True
        assert self.validator.check_payload_size(10_000_001) is False

    def test_get_ip_lists(self):
        self.validator.add_ip_allowlist("1.2.3.4")
        self.validator.add_ip_blocklist("5.6.7.8")
        lists = self.validator.get_ip_lists()
        assert "1.2.3.4" in lists["allowlist"]
        assert "5.6.7.8" in lists["blocklist"]

    def test_remove_ip(self):
        self.validator.add_ip_blocklist("9.9.9.9")
        self.validator.remove_ip_blocklist("9.9.9.9")
        lists = self.validator.get_ip_lists()
        assert "9.9.9.9" not in lists["blocklist"]

    def test_remove_ip_allowlist(self):
        self.validator.add_ip_allowlist("1.1.1.1")
        self.validator.remove_ip_allowlist("1.1.1.1")
        lists = self.validator.get_ip_lists()
        assert "1.1.1.1" not in lists["allowlist"]
