"""PRD-124: Secrets Management & API Credential Vaulting - Secrets Client."""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import VaultConfig
from .vault import SecretsVault


@dataclass
class CacheEntry:
    """Cached secret value with TTL tracking."""

    value: str
    cached_at: float
    ttl_seconds: int
    key_path: str
    version: int


class SecretsClient:
    """High-level client for accessing secrets with caching and fallback.

    Features:
    - Local caching with configurable TTL
    - Automatic cache invalidation and refresh
    - Environment variable fallback
    - Cache statistics for monitoring
    """

    def __init__(
        self,
        vault: SecretsVault,
        config: Optional[VaultConfig] = None,
        cache_ttl_seconds: int = 300,
        enable_env_fallback: bool = True,
    ):
        self.vault = vault
        self.config = config or VaultConfig()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_env_fallback = enable_env_fallback
        self._cache: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._refreshes: int = 0
        self._env_fallbacks: int = 0

    def get_secret(self, key_path: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value with caching and optional env var fallback.

        Resolution order:
        1. Local cache (if not expired)
        2. Vault lookup
        3. Environment variable fallback (key_path with / replaced by _)
        4. Default value
        """
        # Check cache
        cached = self._cache.get(key_path)
        if cached is not None:
            elapsed = time.time() - cached.cached_at
            if elapsed < cached.ttl_seconds:
                self._hits += 1
                return cached.value

        self._misses += 1

        # Vault lookup
        value = self.vault.get_value(key_path)
        if value is not None:
            entry = self.vault.get(key_path)
            version = entry.version if entry else 0
            self._cache[key_path] = CacheEntry(
                value=value,
                cached_at=time.time(),
                ttl_seconds=self.cache_ttl_seconds,
                key_path=key_path,
                version=version,
            )
            return value

        # Environment variable fallback
        if self.enable_env_fallback:
            env_key = key_path.replace("/", "_").replace("-", "_").upper()
            env_value = os.environ.get(env_key)
            if env_value is not None:
                self._env_fallbacks += 1
                return env_value

        return default

    def invalidate(self, key_path: str) -> bool:
        """Invalidate cached secret for a key path."""
        if key_path in self._cache:
            del self._cache[key_path]
            return True
        return False

    def invalidate_all(self) -> int:
        """Invalidate all cached secrets."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def refresh(self, key_path: str) -> Optional[str]:
        """Force-refresh a secret from the vault, bypassing cache."""
        self.invalidate(key_path)
        self._refreshes += 1
        return self.get_secret(key_path)

    def refresh_all(self) -> int:
        """Refresh all cached secrets from the vault."""
        paths = list(self._cache.keys())
        self._cache.clear()
        refreshed = 0
        for path in paths:
            if self.get_secret(path) is not None:
                refreshed += 1
        self._refreshes += refreshed
        return refreshed

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        now = time.time()
        expired_entries = 0
        active_entries = 0
        for entry in self._cache.values():
            elapsed = now - entry.cached_at
            if elapsed >= entry.ttl_seconds:
                expired_entries += 1
            else:
                active_entries += 1

        return {
            "cache_size": len(self._cache),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "refreshes": self._refreshes,
            "env_fallbacks": self._env_fallbacks,
            "ttl_seconds": self.cache_ttl_seconds,
        }
