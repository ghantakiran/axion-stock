"""Token bucket rate limiter with FastAPI middleware.

Provides rate limiting to protect services from being overwhelmed
by too many requests.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

from .config import RateLimiterConfig

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when the rate limit has been exceeded."""

    def __init__(self, retry_after: float = 0.0):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after:.1f}s."
        )


class RateLimiter:
    """Token bucket rate limiter.

    Allows up to `burst` tokens to be consumed instantly, then
    refills at `rate` tokens per second.
    """

    def __init__(self, config: Optional[RateLimiterConfig] = None):
        self._config = config or RateLimiterConfig()
        self._tokens: float = float(self._config.burst)
        self._max_tokens: float = float(self._config.burst)
        self._rate: float = self._config.rate
        self._last_refill: float = time.monotonic()
        self._lock = threading.Lock()
        self._total_allowed: int = 0
        self._total_rejected: int = 0

    @property
    def available_tokens(self) -> float:
        """Return current number of available tokens."""
        with self._lock:
            self._refill()
            return self._tokens

    @property
    def total_allowed(self) -> int:
        return self._total_allowed

    @property
    def total_rejected(self) -> int:
        return self._total_rejected

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self._rate
        self._tokens = min(self._max_tokens, self._tokens + new_tokens)
        self._last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if limited.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if the request is allowed, False if rate limited.
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._total_allowed += 1
                return True
            else:
                self._total_rejected += 1
                return False

    def retry_after(self) -> float:
        """Return seconds until at least 1 token is available."""
        with self._lock:
            self._refill()
            if self._tokens >= 1:
                return 0.0
            needed = 1.0 - self._tokens
            return needed / self._rate

    def reset(self) -> None:
        """Reset to full token capacity."""
        with self._lock:
            self._tokens = self._max_tokens
            self._last_refill = time.monotonic()
            self._total_allowed = 0
            self._total_rejected = 0

    def get_metrics(self) -> Dict[str, Any]:
        """Return current rate limiter metrics."""
        with self._lock:
            self._refill()
            return {
                "available_tokens": self._tokens,
                "max_tokens": self._max_tokens,
                "rate_per_second": self._rate,
                "total_allowed": self._total_allowed,
                "total_rejected": self._total_rejected,
            }


class RateLimiterRegistry:
    """Manage per-key rate limiters (e.g., per client IP)."""

    def __init__(self, default_config: Optional[RateLimiterConfig] = None):
        self._default_config = default_config or RateLimiterConfig()
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str) -> RateLimiter:
        """Get or create a rate limiter for the given key."""
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(self._default_config)
            return self._limiters[key]

    def remove(self, key: str) -> bool:
        """Remove a limiter by key."""
        with self._lock:
            return self._limiters.pop(key, None) is not None

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Return metrics for all limiters."""
        with self._lock:
            return {k: v.get_metrics() for k, v in self._limiters.items()}

    def __len__(self) -> int:
        with self._lock:
            return len(self._limiters)


# ── FastAPI Middleware ────────────────────────────────────────────────

def create_rate_limit_middleware(
    config: Optional[RateLimiterConfig] = None,
):
    """Create a FastAPI/Starlette-compatible rate limiting middleware.

    Usage:
        from fastapi import FastAPI
        from src.resilience.rate_limiter import create_rate_limit_middleware, RateLimiterConfig

        app = FastAPI()
        app.add_middleware(
            create_rate_limit_middleware(RateLimiterConfig(rate=50, burst=10))
        )
    """
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse
    except ImportError:
        logger.warning("starlette not installed; RateLimitMiddleware unavailable")
        return None

    registry = RateLimiterRegistry(config)

    class RateLimitMiddleware(BaseHTTPMiddleware):
        """ASGI middleware that rate limits requests by client IP."""

        async def dispatch(self, request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            limiter = registry.get_or_create(client_ip)

            if not limiter.consume():
                retry_after = limiter.retry_after()
                logger.warning(
                    "Rate limited client %s, retry after %.1fs",
                    client_ip,
                    retry_after,
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )

            response = await call_next(request)
            return response

    return RateLimitMiddleware
