"""Sliding-window rate limiter with per-endpoint and per-user quotas."""

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .config import DEFAULT_TIERS, GatewayConfig, RateLimitTier

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool = True
    limit: int = 0
    remaining: int = 0
    reset_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_after_seconds: Optional[int] = None


@dataclass
class SlidingWindowEntry:
    """Single entry inside a sliding window."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    count: int = 1


@dataclass
class EndpointRateLimit:
    """Custom rate limit for a specific endpoint path pattern."""

    path_pattern: str = ""
    requests_per_minute: int = 60
    burst_multiplier: float = 1.5


@dataclass
class _UserQuota:
    """Internal tracker for user daily/monthly quotas."""

    daily_limit: int = 0
    monthly_limit: int = 0
    daily_used: int = 0
    monthly_used: int = 0
    last_reset_daily: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_reset_monthly: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class GatewayRateLimiter:
    """Sliding-window rate limiter with endpoint + quota support."""

    def __init__(self, config: Optional[GatewayConfig] = None) -> None:
        self._config = config or GatewayConfig()
        self._windows: Dict[str, List[SlidingWindowEntry]] = {}
        self._endpoint_limits: Dict[str, EndpointRateLimit] = {}
        self._user_quotas: Dict[str, _UserQuota] = {}
        self._lock = threading.Lock()

    # ── public API ───────────────────────────────────────────────────

    def check_rate_limit(
        self,
        user_id_or_ip: str,
        path: str,
        tier: RateLimitTier = RateLimitTier.FREE,
    ) -> RateLimitResult:
        """Check whether a request is allowed under the sliding window."""
        with self._lock:
            now = datetime.now(timezone.utc)
            tier_cfg = DEFAULT_TIERS.get(tier, DEFAULT_TIERS[RateLimitTier.FREE])

            # Determine effective RPM (endpoint override or tier default)
            effective_rpm = tier_cfg.requests_per_minute
            effective_burst = tier_cfg.burst_multiplier
            for pattern, ep_limit in self._endpoint_limits.items():
                if re.fullmatch(pattern, path):
                    effective_rpm = ep_limit.requests_per_minute
                    effective_burst = ep_limit.burst_multiplier
                    break

            burst_limit = int(effective_rpm * effective_burst)
            window_seconds = 60

            # Per-user sliding window
            key = f"{user_id_or_ip}:{path}"
            self._cleanup_old_entries(key, window_seconds)
            entries = self._windows.get(key, [])
            current_count = sum(e.count for e in entries)

            reset_at = now + timedelta(seconds=window_seconds)

            if current_count >= burst_limit:
                retry_after = window_seconds
                if entries:
                    oldest = min(e.timestamp for e in entries)
                    retry_after = max(1, int((oldest + timedelta(seconds=window_seconds) - now).total_seconds()))
                logger.info(
                    "Rate limit exceeded for %s on %s (%d/%d)",
                    user_id_or_ip, path, current_count, burst_limit,
                )
                return RateLimitResult(
                    allowed=False,
                    limit=burst_limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after_seconds=retry_after,
                )

            # Check user daily quota if configured
            if user_id_or_ip in self._user_quotas:
                quota = self._user_quotas[user_id_or_ip]
                self._maybe_reset_quota(quota, now)
                if quota.daily_limit > 0 and quota.daily_used >= quota.daily_limit:
                    logger.info("Daily quota exceeded for %s", user_id_or_ip)
                    return RateLimitResult(
                        allowed=False,
                        limit=quota.daily_limit,
                        remaining=0,
                        reset_at=now.replace(hour=0, minute=0, second=0) + timedelta(days=1),
                        retry_after_seconds=int(
                            ((now.replace(hour=0, minute=0, second=0) + timedelta(days=1)) - now).total_seconds()
                        ),
                    )
                if quota.monthly_limit > 0 and quota.monthly_used >= quota.monthly_limit:
                    logger.info("Monthly quota exceeded for %s", user_id_or_ip)
                    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
                    return RateLimitResult(
                        allowed=False,
                        limit=quota.monthly_limit,
                        remaining=0,
                        reset_at=next_month,
                        retry_after_seconds=int((next_month - now).total_seconds()),
                    )
                quota.daily_used += 1
                quota.monthly_used += 1

            # Record the request
            entries.append(SlidingWindowEntry(timestamp=now))
            self._windows[key] = entries

            remaining = max(0, burst_limit - current_count - 1)
            return RateLimitResult(
                allowed=True,
                limit=burst_limit,
                remaining=remaining,
                reset_at=reset_at,
            )

    def add_endpoint_limit(
        self, path_pattern: str, rpm: int, burst_multiplier: float = 1.5
    ) -> None:
        """Register a custom rate limit for an endpoint path regex."""
        with self._lock:
            self._endpoint_limits[path_pattern] = EndpointRateLimit(
                path_pattern=path_pattern,
                requests_per_minute=rpm,
                burst_multiplier=burst_multiplier,
            )
            logger.info("Endpoint limit set: %s -> %d rpm", path_pattern, rpm)

    def set_user_quota(
        self, user_id: str, daily_limit: int, monthly_limit: int
    ) -> None:
        """Configure daily/monthly quota for a user."""
        with self._lock:
            now = datetime.now(timezone.utc)
            self._user_quotas[user_id] = _UserQuota(
                daily_limit=daily_limit,
                monthly_limit=monthly_limit,
                last_reset_daily=now,
                last_reset_monthly=now,
            )
            logger.info(
                "User quota set: %s -> %d daily / %d monthly",
                user_id, daily_limit, monthly_limit,
            )

    def get_user_usage(self, user_id: str) -> Dict:
        """Return current daily/monthly usage for a user."""
        with self._lock:
            quota = self._user_quotas.get(user_id)
            if not quota:
                return {"daily_used": 0, "monthly_used": 0, "daily_limit": 0, "monthly_limit": 0}
            self._maybe_reset_quota(quota, datetime.now(timezone.utc))
            return {
                "daily_used": quota.daily_used,
                "monthly_used": quota.monthly_used,
                "daily_limit": quota.daily_limit,
                "monthly_limit": quota.monthly_limit,
            }

    def get_rate_limit_headers(self, result: RateLimitResult) -> Dict[str, str]:
        """Build standard X-RateLimit-* response headers."""
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": result.reset_at.isoformat(),
        }
        if result.retry_after_seconds is not None:
            headers["Retry-After"] = str(result.retry_after_seconds)
        return headers

    def reset_user(self, user_id: str) -> None:
        """Clear all windows and quotas for a given user."""
        with self._lock:
            keys_to_remove = [k for k in self._windows if k.startswith(f"{user_id}:")]
            for k in keys_to_remove:
                del self._windows[k]
            if user_id in self._user_quotas:
                q = self._user_quotas[user_id]
                q.daily_used = 0
                q.monthly_used = 0
            logger.info("Reset rate-limit state for user %s", user_id)

    # ── internals ────────────────────────────────────────────────────

    def _cleanup_old_entries(self, key: str, window_seconds: int) -> None:
        """Remove entries outside the sliding window."""
        if key not in self._windows:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        self._windows[key] = [e for e in self._windows[key] if e.timestamp > cutoff]

    @staticmethod
    def _maybe_reset_quota(quota: _UserQuota, now: datetime) -> None:
        """Reset daily/monthly counters if the period rolled over."""
        if now.date() > quota.last_reset_daily.date():
            quota.daily_used = 0
            quota.last_reset_daily = now
        if now.month != quota.last_reset_monthly.month or now.year != quota.last_reset_monthly.year:
            quota.monthly_used = 0
            quota.last_reset_monthly = now
