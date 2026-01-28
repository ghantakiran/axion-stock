"""Redis cache client for Axion platform.

Provides both async and sync access to Redis with DataFrame serialization,
JSON storage, and TTL-based expiration.
"""

import json
import logging
import pickle
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache with async and sync support."""

    def __init__(self):
        self._async_client = None
        self._sync_client = None

    # --- Connection Management ---

    async def get_async_client(self):
        """Get or create async Redis client."""
        if self._async_client is None:
            try:
                import redis.asyncio as aioredis
                from src.settings import get_settings
                settings = get_settings()
                self._async_client = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=False,
                )
                await self._async_client.ping()
            except Exception as e:
                logger.warning("Redis async connection failed: %s", e)
                self._async_client = None
                raise
        return self._async_client

    def get_sync_client(self):
        """Get or create sync Redis client."""
        if self._sync_client is None:
            try:
                import redis
                from src.settings import get_settings
                settings = get_settings()
                self._sync_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=False,
                )
                self._sync_client.ping()
            except Exception as e:
                logger.warning("Redis sync connection failed: %s", e)
                self._sync_client = None
                raise
        return self._sync_client

    # --- Async DataFrame Operations ---

    async def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Get a pickled DataFrame from Redis."""
        try:
            client = await self.get_async_client()
            data = await client.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.debug("Redis get_dataframe miss for %s: %s", key, e)
            return None

    async def set_dataframe(self, key: str, df: pd.DataFrame, ttl: int) -> None:
        """Store a DataFrame in Redis with TTL."""
        try:
            client = await self.get_async_client()
            await client.setex(key, ttl, pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception as e:
            logger.warning("Redis set_dataframe failed for %s: %s", key, e)

    # --- Async JSON Operations ---

    async def get_json(self, key: str) -> Optional[Any]:
        """Get a JSON-serialized value from Redis."""
        try:
            client = await self.get_async_client()
            data = await client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except Exception as e:
            logger.debug("Redis get_json miss for %s: %s", key, e)
            return None

    async def set_json(self, key: str, data: Any, ttl: int) -> None:
        """Store a JSON-serializable value in Redis with TTL."""
        try:
            client = await self.get_async_client()
            await client.setex(key, ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.warning("Redis set_json failed for %s: %s", key, e)

    # --- Quote Shortcuts ---

    async def get_quote(self, ticker: str) -> Optional[dict]:
        """Get a cached stock quote."""
        return await self.get_json(f"axion:quote:{ticker}")

    async def set_quote(self, ticker: str, data: dict) -> None:
        """Cache a stock quote with short TTL."""
        from src.settings import get_settings
        settings = get_settings()
        await self.set_json(f"axion:quote:{ticker}", data, settings.redis_quote_ttl)

    # --- Sync Operations (backward compatibility) ---

    def get_dataframe_sync(self, key: str) -> Optional[pd.DataFrame]:
        """Synchronous DataFrame get."""
        try:
            client = self.get_sync_client()
            data = client.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except Exception as e:
            logger.debug("Redis sync get_dataframe miss for %s: %s", key, e)
            return None

    def set_dataframe_sync(self, key: str, df: pd.DataFrame, ttl: int) -> None:
        """Synchronous DataFrame set."""
        try:
            client = self.get_sync_client()
            client.setex(key, ttl, pickle.dumps(df, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception as e:
            logger.warning("Redis sync set_dataframe failed for %s: %s", key, e)

    def get_json_sync(self, key: str) -> Optional[Any]:
        """Synchronous JSON get."""
        try:
            client = self.get_sync_client()
            data = client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except Exception as e:
            logger.debug("Redis sync get_json miss for %s: %s", key, e)
            return None

    def set_json_sync(self, key: str, data: Any, ttl: int) -> None:
        """Synchronous JSON set."""
        try:
            client = self.get_sync_client()
            client.setex(key, ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.warning("Redis sync set_json failed for %s: %s", key, e)

    # --- Cache Invalidation ---

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count deleted."""
        try:
            client = await self.get_async_client()
            count = 0
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                count += 1
            return count
        except Exception as e:
            logger.warning("Redis invalidate_pattern failed for %s: %s", pattern, e)
            return 0

    async def close(self) -> None:
        """Close all connections."""
        if self._async_client:
            await self._async_client.close()
            self._async_client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None


# Module-level singleton
cache = RedisCache()
