"""API Authentication & Rate Limiting.

Handles API key validation, OAuth2 tokens, and request rate limiting.
"""

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from src.api.config import APITier, RATE_LIMITS, APIConfig, DEFAULT_API_CONFIG

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API key creation, validation, and lifecycle.

    Keys are prefixed with 'ax_' followed by 48 random hex characters.
    Stored keys are SHA-256 hashed for security.
    """

    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or DEFAULT_API_CONFIG
        # key_hash -> key metadata
        self._keys: dict[str, dict] = {}
        # key_id -> key_hash (for lookups)
        self._id_to_hash: dict[str, str] = {}

    def create_key(
        self,
        user_id: str,
        name: str,
        scopes: Optional[list[str]] = None,
        tier: APITier = APITier.FREE,
        expires_in_days: Optional[int] = None,
    ) -> dict:
        """Create a new API key.

        Args:
            user_id: Owner user ID.
            name: Key name/description.
            scopes: Permission scopes.
            tier: Subscription tier for rate limits.
            expires_in_days: Optional expiry.

        Returns:
            Dict with key_id, raw key (shown once), and metadata.
        """
        raw_key = f"{self.config.api_key_prefix}{secrets.token_hex(24)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = secrets.token_hex(8)

        now = datetime.utcnow()
        expires_at = None
        if expires_in_days:
            expires_at = now + timedelta(days=expires_in_days)

        metadata = {
            "key_id": key_id,
            "user_id": user_id,
            "name": name,
            "scopes": scopes or ["read"],
            "tier": tier,
            "is_active": True,
            "created_at": now,
            "expires_at": expires_at,
            "last_used": None,
        }

        self._keys[key_hash] = metadata
        self._id_to_hash[key_id] = key_hash

        return {
            "key_id": key_id,
            "key": raw_key,
            "key_preview": f"{self.config.api_key_prefix}...{raw_key[-4:]}",
            **metadata,
        }

    def validate_key(self, raw_key: str) -> Optional[dict]:
        """Validate an API key and return its metadata.

        Args:
            raw_key: The raw API key string.

        Returns:
            Key metadata if valid, None otherwise.
        """
        if not raw_key.startswith(self.config.api_key_prefix):
            return None

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        metadata = self._keys.get(key_hash)

        if not metadata:
            return None

        if not metadata["is_active"]:
            return None

        if metadata["expires_at"] and metadata["expires_at"] < datetime.utcnow():
            return None

        # Update last used
        metadata["last_used"] = datetime.utcnow()
        return metadata

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: Key ID to revoke.

        Returns:
            True if revoked, False if not found.
        """
        key_hash = self._id_to_hash.get(key_id)
        if not key_hash or key_hash not in self._keys:
            return False

        self._keys[key_hash]["is_active"] = False
        logger.info(f"API key revoked: {key_id}")
        return True

    def list_keys(self, user_id: str) -> list[dict]:
        """List all API keys for a user.

        Args:
            user_id: User ID.

        Returns:
            List of key metadata (without hashes).
        """
        return [
            {k: v for k, v in meta.items() if k != "key_hash"}
            for meta in self._keys.values()
            if meta["user_id"] == user_id
        ]

    def has_scope(self, key_metadata: dict, required_scope: str) -> bool:
        """Check if a key has the required scope.

        Args:
            key_metadata: Key metadata from validate_key.
            required_scope: Scope to check.

        Returns:
            True if scope is present.
        """
        scopes = key_metadata.get("scopes", [])
        # 'admin' scope grants everything
        if "admin" in scopes:
            return True
        # 'write' implies 'read'
        if required_scope == "read" and "write" in scopes:
            return True
        return required_scope in scopes


class RateLimiter:
    """Token bucket rate limiter.

    Tracks request counts per user/key with per-minute and daily limits.
    """

    def __init__(self):
        # user_id -> list of request timestamps
        self._minute_windows: dict[str, list[float]] = defaultdict(list)
        self._daily_counts: dict[str, dict] = {}

    def check_rate_limit(
        self,
        user_id: str,
        tier: APITier = APITier.FREE,
    ) -> tuple[bool, dict]:
        """Check if a request is within rate limits.

        Args:
            user_id: User or API key ID.
            tier: Subscription tier.

        Returns:
            Tuple of (allowed, limit_info).
        """
        limits = RATE_LIMITS[tier]
        now = time.time()

        # Clean old entries from minute window
        minute_ago = now - 60
        self._minute_windows[user_id] = [
            t for t in self._minute_windows[user_id] if t > minute_ago
        ]

        minute_count = len(self._minute_windows[user_id])
        per_minute = limits["per_minute"]

        # Check per-minute limit
        if minute_count >= per_minute:
            return False, {
                "limit": per_minute,
                "remaining": 0,
                "reset": int(self._minute_windows[user_id][0] + 60),
                "reason": "per_minute",
            }

        # Check daily limit
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if user_id not in self._daily_counts:
            self._daily_counts[user_id] = {"date": today, "count": 0}

        daily = self._daily_counts[user_id]
        if daily["date"] != today:
            daily["date"] = today
            daily["count"] = 0

        daily_limit = limits["daily_limit"]
        if daily_limit > 0 and daily["count"] >= daily_limit:
            return False, {
                "limit": daily_limit,
                "remaining": 0,
                "reset": 0,
                "reason": "daily",
            }

        # Allow request
        self._minute_windows[user_id].append(now)
        daily["count"] += 1

        return True, {
            "limit": per_minute,
            "remaining": per_minute - minute_count - 1,
            "daily_remaining": max(0, daily_limit - daily["count"]) if daily_limit > 0 else -1,
        }

    def get_usage(self, user_id: str, tier: APITier = APITier.FREE) -> dict:
        """Get current rate limit usage.

        Args:
            user_id: User or API key ID.
            tier: Subscription tier.

        Returns:
            Usage statistics.
        """
        limits = RATE_LIMITS[tier]
        now = time.time()

        # Minute window
        minute_ago = now - 60
        minute_requests = [
            t for t in self._minute_windows.get(user_id, []) if t > minute_ago
        ]

        # Daily count
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily = self._daily_counts.get(user_id, {"date": today, "count": 0})
        daily_count = daily["count"] if daily["date"] == today else 0

        daily_limit = limits["daily_limit"]

        return {
            "tier": tier.value,
            "minute_limit": limits["per_minute"],
            "minute_used": len(minute_requests),
            "minute_remaining": max(0, limits["per_minute"] - len(minute_requests)),
            "daily_limit": daily_limit if daily_limit > 0 else "unlimited",
            "daily_used": daily_count,
            "daily_remaining": (
                max(0, daily_limit - daily_count) if daily_limit > 0 else "unlimited"
            ),
        }


class WebhookSigner:
    """HMAC webhook payload signer.

    Signs webhook payloads so receivers can verify authenticity.
    """

    @staticmethod
    def sign(payload: str, secret: str, algorithm: str = "sha256") -> str:
        """Sign a payload with HMAC.

        Args:
            payload: JSON payload string.
            secret: Webhook secret.
            algorithm: Hash algorithm.

        Returns:
            Hex-encoded HMAC signature.
        """
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            getattr(hashlib, algorithm),
        ).hexdigest()

    @staticmethod
    def verify(
        payload: str,
        signature: str,
        secret: str,
        algorithm: str = "sha256",
    ) -> bool:
        """Verify a webhook signature.

        Args:
            payload: JSON payload string.
            signature: Provided signature.
            secret: Webhook secret.
            algorithm: Hash algorithm.

        Returns:
            True if signature is valid.
        """
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            getattr(hashlib, algorithm),
        ).hexdigest()

        return hmac.compare_digest(signature, expected)
