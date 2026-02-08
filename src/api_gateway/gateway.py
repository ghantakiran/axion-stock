"""Core API Gateway: orchestrates rate limiting, analytics, versioning, validation."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .analytics import APIAnalytics
from .config import GatewayConfig, RateLimitTier
from .rate_limiter import GatewayRateLimiter
from .validator import RequestValidator
from .versioning import VersionManager

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Immutable context representing one inbound API request."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    method: str = "GET"
    user_id: Optional[str] = None
    api_key: Optional[str] = None
    tier: RateLimitTier = RateLimitTier.FREE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    headers: Dict[str, str] = field(default_factory=dict)
    body_size: int = 0
    version: str = "v1"


@dataclass
class GatewayResponse:
    """Result returned by the gateway after processing a request."""

    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    allowed: bool = True
    rejection_reason: Optional[str] = None


class APIGateway:
    """Central gateway that composes validation, rate limiting, analytics, and versioning."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        self._config = config or GatewayConfig()
        self._rate_limiter = GatewayRateLimiter(self._config)
        self._analytics = APIAnalytics()
        self._versioning = VersionManager(self._config.default_version)
        self._validator = RequestValidator(self._config)
        self._hooks_pre: List[Callable] = []
        self._hooks_post: List[Callable] = []

    # ── request processing ───────────────────────────────────────────

    def process_request(self, ctx: RequestContext) -> GatewayResponse:
        """Run a request through the full gateway pipeline.

        Pipeline:
        1. Pre-hooks
        2. Validation (payload size, IP, headers)
        3. Version resolution
        4. Rate-limit check
        5. Record analytics
        6. Post-hooks
        """
        start = time.monotonic()
        response = GatewayResponse()

        # 1. Pre-hooks
        for hook in self._hooks_pre:
            try:
                hook(ctx, response)
            except Exception as exc:  # pragma: no cover
                logger.error("Pre-hook error: %s", exc)

        # 2. Validation
        if self._config.enable_validation:
            validation = self._validator.validate_request(ctx)
            if not validation.valid:
                response.status_code = 400
                response.allowed = False
                response.rejection_reason = "; ".join(validation.errors)
                self._record(ctx, response, start)
                return response

        # 3. Version resolution
        if self._config.enable_versioning:
            resolved_version, version_headers = self._versioning.resolve_version(ctx.version)
            response.headers.update(version_headers)
            if not self._versioning.is_supported(resolved_version):
                # still allow if version simply not registered (graceful)
                pass

        # 4. Rate limiting
        if self._config.enable_rate_limiting:
            identity = ctx.user_id or ctx.api_key or "anonymous"
            result = self._rate_limiter.check_rate_limit(identity, ctx.path, ctx.tier)
            rl_headers = self._rate_limiter.get_rate_limit_headers(result)
            response.headers.update(rl_headers)
            if not result.allowed:
                response.status_code = 429
                response.allowed = False
                response.rejection_reason = "Rate limit exceeded"
                self._record(ctx, response, start)
                return response

        # 5. Post-hooks
        for hook in self._hooks_post:
            try:
                hook(ctx, response)
            except Exception as exc:  # pragma: no cover
                logger.error("Post-hook error: %s", exc)

        # 6. Analytics
        self._record(ctx, response, start)
        return response

    # ── hooks ────────────────────────────────────────────────────────

    def add_pre_hook(self, func: Callable) -> None:
        """Register a pre-processing hook (called before validation)."""
        self._hooks_pre.append(func)

    def add_post_hook(self, func: Callable) -> None:
        """Register a post-processing hook (called after rate limiting)."""
        self._hooks_post.append(func)

    # ── health ───────────────────────────────────────────────────────

    def get_health(self) -> Dict:
        """Report component health status."""
        return {
            "gateway": "healthy",
            "rate_limiter": "enabled" if self._config.enable_rate_limiting else "disabled",
            "analytics": "enabled" if self._config.enable_analytics else "disabled",
            "versioning": "enabled" if self._config.enable_versioning else "disabled",
            "validation": "enabled" if self._config.enable_validation else "disabled",
        }

    # ── properties for external access ───────────────────────────────

    @property
    def rate_limiter(self) -> GatewayRateLimiter:
        return self._rate_limiter

    @property
    def analytics(self) -> APIAnalytics:
        return self._analytics

    @property
    def versioning(self) -> VersionManager:
        return self._versioning

    @property
    def validator(self) -> RequestValidator:
        return self._validator

    # ── internals ────────────────────────────────────────────────────

    def _record(self, ctx: RequestContext, response: GatewayResponse, start: float) -> None:
        if self._config.enable_analytics:
            latency_ms = (time.monotonic() - start) * 1000
            self._analytics.record_request(
                path=ctx.path,
                method=ctx.method,
                status_code=response.status_code,
                latency_ms=latency_ms,
                user_id=ctx.user_id,
            )
