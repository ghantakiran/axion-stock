"""FastAPI Dependencies for Authentication and Rate Limiting.

Provides injectable dependencies for API key validation, scope enforcement,
and rate limiting. Auth is opt-in via AXION_REQUIRE_API_KEY=true env var.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, Response

from src.api.auth import APIKeyManager, RateLimiter
from src.api.config import APITier

logger = logging.getLogger(__name__)

# ── Singleton instances (shared per process) ──────────────────────────

_key_manager: Optional[APIKeyManager] = None
_rate_limiter: Optional[RateLimiter] = None


def get_key_manager() -> APIKeyManager:
    """Return (or create) the global APIKeyManager singleton."""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager()
    return _key_manager


def get_rate_limiter() -> RateLimiter:
    """Return (or create) the global RateLimiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def _auth_required() -> bool:
    """Check whether API key authentication is enabled."""
    return os.environ.get("AXION_REQUIRE_API_KEY", "").lower() in ("true", "1", "yes")


# ── User context returned by auth dependency ──────────────────────────


@dataclass
class AuthContext:
    """Authenticated user context injected into request handlers."""

    user_id: str
    tier: APITier
    scopes: list[str]
    authenticated: bool


_DEV_CONTEXT = AuthContext(
    user_id="dev",
    tier=APITier.ENTERPRISE,
    scopes=["admin"],
    authenticated=False,
)


# ── Auth Dependencies ─────────────────────────────────────────────────


async def require_auth(
    x_api_key: Optional[str] = Header(default=None),
) -> AuthContext:
    """Require a valid API key on protected endpoints.

    When AXION_REQUIRE_API_KEY is unset/false, returns a dev context
    with full permissions so local development works without keys.

    Usage::

        @router.post("/orders")
        async def create_order(auth: AuthContext = Depends(require_auth)):
            ...
    """
    if not _auth_required():
        return _DEV_CONTEXT

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key — provide X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    manager = get_key_manager()
    metadata = manager.validate_key(x_api_key)
    if metadata is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return AuthContext(
        user_id=metadata["user_id"],
        tier=metadata["tier"],
        scopes=metadata["scopes"],
        authenticated=True,
    )


def require_scope(scope: str):
    """Factory that returns a dependency requiring a specific scope.

    Usage::

        @router.post("/bot/kill")
        async def kill(auth: AuthContext = Depends(require_scope("write"))):
            ...
    """

    async def _check_scope(
        auth: AuthContext = Depends(require_auth),
    ) -> AuthContext:
        if not _auth_required():
            return auth

        manager = get_key_manager()
        # Build a metadata-like dict for has_scope
        meta = {"scopes": auth.scopes}
        if not manager.has_scope(meta, scope):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope — requires '{scope}'",
            )
        return auth

    return _check_scope


# ── Rate Limit Dependency ─────────────────────────────────────────────


async def check_rate_limit(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_auth),
) -> AuthContext:
    """Check rate limits and add X-RateLimit-* headers.

    Extracts user identity from auth context, checks limits based on
    their tier, and injects standard rate limit headers.

    Usage::

        @router.get("/market/quotes")
        async def quotes(auth: AuthContext = Depends(check_rate_limit)):
            ...
    """
    limiter = get_rate_limiter()
    allowed, info = limiter.check_rate_limit(auth.user_id, auth.tier)

    if not allowed:
        reset = info.get("reset", 0)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({info.get('reason', 'unknown')})",
            headers={
                "Retry-After": str(reset),
                "X-RateLimit-Limit": str(info.get("limit", 0)),
                "X-RateLimit-Remaining": "0",
            },
        )

    # Add rate limit headers to successful responses
    response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
    response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
    if "daily_remaining" in info:
        dr = info["daily_remaining"]
        response.headers["X-RateLimit-Daily-Remaining"] = str(dr) if dr != -1 else "unlimited"

    return auth
