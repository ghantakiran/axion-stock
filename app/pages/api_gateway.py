"""PRD-115: API Gateway & Advanced Rate Limiting Dashboard."""

import streamlit as st
from app.styles import inject_global_styles
from datetime import datetime, timedelta, timezone

from src.api_gateway import (
    APIGateway,
    GatewayConfig,
    RequestContext,
    RateLimitTier,
    VersionStatus,
    DEFAULT_TIERS,
    APIAnalytics,
    VersionManager,
    GatewayRateLimiter,
    RequestValidator,
)


def render():
    st.title("API Gateway & Rate Limiting")

    tabs = st.tabs(["API Overview", "Rate Limits", "Analytics", "Versioning"])

    # ── Tab 1: API Overview ──────────────────────────────────────────
    with tabs[0]:
        st.subheader("Gateway Overview")

        gw = APIGateway()
        health = gw.get_health()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Gateway", health["gateway"].capitalize())
        col2.metric("Rate Limiter", health["rate_limiter"].capitalize())
        col3.metric("Analytics", health["analytics"].capitalize())
        col4.metric("Validation", health["validation"].capitalize())

        st.markdown("---")
        st.subheader("Configuration")
        cfg = GatewayConfig()
        st.json({
            "default_rate_limit": cfg.default_rate_limit,
            "burst_allowance": cfg.burst_allowance,
            "max_payload_bytes": cfg.max_payload_bytes,
            "default_version": cfg.default_version,
        })

        # Process sample requests
        st.markdown("---")
        st.subheader("Sample Request Processing")
        sample_paths = ["/api/v1/stocks", "/api/v1/portfolio", "/api/v1/orders", "/api/v1/analytics"]
        results = []
        for path in sample_paths:
            ctx = RequestContext(path=path, method="GET", user_id="demo_user", tier=RateLimitTier.PRO)
            resp = gw.process_request(ctx)
            results.append({
                "Path": path,
                "Status": resp.status_code,
                "Allowed": resp.allowed,
                "Rate Limit Remaining": resp.headers.get("X-RateLimit-Remaining", "N/A"),
            })
        st.table(results)

    # ── Tab 2: Rate Limits ───────────────────────────────────────────
    with tabs[1]:
        st.subheader("Rate Limit Tiers")

        tier_data = []
        for tier, tc in DEFAULT_TIERS.items():
            tier_data.append({
                "Tier": tier.value.upper(),
                "Requests/Min": tc.requests_per_minute,
                "Requests/Day": tc.requests_per_day,
                "Burst Multiplier": tc.burst_multiplier,
                "Burst Limit": int(tc.requests_per_minute * tc.burst_multiplier),
            })
        st.table(tier_data)

        st.markdown("---")
        st.subheader("Rate Limit Simulation")

        limiter = GatewayRateLimiter()
        selected_tier = st.selectbox("Select Tier", [t.value for t in RateLimitTier], index=0)
        tier_enum = RateLimitTier(selected_tier)
        burst_limit = int(DEFAULT_TIERS[tier_enum].requests_per_minute * DEFAULT_TIERS[tier_enum].burst_multiplier)

        num_requests = st.slider("Number of Requests", 1, burst_limit + 10, burst_limit)
        if st.button("Run Simulation"):
            allowed_count = 0
            rejected_count = 0
            for i in range(num_requests):
                result = limiter.check_rate_limit("sim_user", "/api/sim", tier_enum)
                if result.allowed:
                    allowed_count += 1
                else:
                    rejected_count += 1
            col1, col2 = st.columns(2)
            col1.metric("Allowed", allowed_count)
            col2.metric("Rejected", rejected_count)

        st.markdown("---")
        st.subheader("User Quotas")
        sample_quotas = [
            {"User": "user_001", "Tier": "PRO", "Daily Limit": 10000, "Monthly Limit": 200000, "Daily Used": 4523},
            {"User": "user_002", "Tier": "FREE", "Daily Limit": 1000, "Monthly Limit": 20000, "Daily Used": 987},
            {"User": "user_003", "Tier": "ENTERPRISE", "Daily Limit": 100000, "Monthly Limit": 2000000, "Daily Used": 23456},
        ]
        st.table(sample_quotas)

    # ── Tab 3: Analytics ─────────────────────────────────────────────
    with tabs[2]:
        st.subheader("API Analytics")

        analytics = APIAnalytics()
        # Populate with sample data
        sample_endpoints = [
            ("/api/v1/stocks", "GET", 200, 12.5),
            ("/api/v1/stocks", "GET", 200, 15.3),
            ("/api/v1/stocks", "GET", 200, 11.0),
            ("/api/v1/portfolio", "GET", 200, 45.2),
            ("/api/v1/portfolio", "GET", 500, 120.0),
            ("/api/v1/orders", "POST", 201, 85.4),
            ("/api/v1/orders", "POST", 201, 92.1),
            ("/api/v1/orders", "POST", 400, 10.0),
            ("/api/v1/analytics", "GET", 200, 250.0),
            ("/api/v1/analytics", "GET", 200, 300.0),
        ]
        for path, method, code, lat in sample_endpoints:
            analytics.record_request(path, method, code, lat, user_id="demo")

        summary = analytics.get_summary()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Requests", summary["total_requests"])
        col2.metric("Avg Latency (ms)", f"{summary['avg_latency_ms']:.1f}")
        col3.metric("Error Rate", f"{summary['error_rate']:.1%}")
        col4.metric("Endpoints", summary["total_endpoints"])

        st.markdown("---")
        st.subheader("Top Endpoints")
        top = analytics.get_top_endpoints(n=10)
        top_data = []
        for ep in top:
            top_data.append({
                "Path": ep.path,
                "Method": ep.method,
                "Requests": ep.total_requests,
                "Avg Latency": f"{ep.avg_latency_ms:.1f} ms",
                "Error Rate": f"{ep.error_rate:.1%}",
                "P50": f"{ep.p50:.1f} ms",
                "P95": f"{ep.p95:.1f} ms",
                "P99": f"{ep.p99:.1f} ms",
            })
        st.table(top_data)

        st.markdown("---")
        st.subheader("Error Endpoints (> 5% error rate)")
        error_eps = analytics.get_error_endpoints()
        if error_eps:
            err_data = []
            for ep in error_eps:
                err_data.append({
                    "Path": ep.path,
                    "Method": ep.method,
                    "Error Rate": f"{ep.error_rate:.1%}",
                    "Errors": ep.error_count,
                    "Total": ep.total_requests,
                })
            st.table(err_data)
        else:
            st.info("No endpoints with high error rates.")

    # ── Tab 4: Versioning ────────────────────────────────────────────
    with tabs[3]:
        st.subheader("API Versioning")

        vm = VersionManager(default_version="v1")
        vm.register_version("v1", description="Initial stable release", changelog=["Core endpoints", "Authentication"])
        vm.register_version("v2", description="Enhanced analytics", changelog=["Analytics API", "WebSocket support", "Batch operations"])
        vm.register_version("v3", description="AI-powered features", changelog=["AI recommendations", "Natural language queries"])
        sunset_date = datetime.now(timezone.utc) + timedelta(days=90)
        vm.deprecate_version("v1", sunset_at=sunset_date)

        version_data = []
        for ver_name in ["v1", "v2", "v3"]:
            v = vm.get_version(ver_name)
            if v:
                version_data.append({
                    "Version": v.version,
                    "Status": v.status.value.upper(),
                    "Released": v.released_at.strftime("%Y-%m-%d"),
                    "Sunset": v.sunset_at.strftime("%Y-%m-%d") if v.sunset_at else "N/A",
                    "Description": v.description,
                })
        st.table(version_data)

        st.markdown("---")
        st.subheader("Version Resolution")
        test_version = st.selectbox("Request Version", ["v1", "v2", "v3", "v99"])
        resolved, headers = vm.resolve_version(test_version)
        st.write(f"**Resolved Version:** {resolved}")
        if headers:
            st.json(headers)
        else:
            st.info("No additional headers.")

        st.markdown("---")
        st.subheader("Active Versions")
        active = vm.get_active_versions()
        for v in active:
            with st.expander(f"{v.version} ({v.status.value})"):
                st.write(f"**Description:** {v.description}")
                if v.changelog:
                    st.write("**Changelog:**")
                    for item in v.changelog:
                        st.write(f"- {item}")
                supported = vm.is_supported(v.version)
                st.write(f"**Supported:** {'Yes' if supported else 'No'}")


try:
    st.set_page_config(page_title="API Gateway", page_icon="\U0001f310", layout="wide")
except st.errors.StreamlitAPIException:
    pass

inject_global_styles()

render()
