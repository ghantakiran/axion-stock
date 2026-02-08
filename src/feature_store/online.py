"""Online Feature Store for low-latency serving and caching."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """A cached feature value for online serving."""

    feature_id: str = ""
    entity_id: str = ""
    value: Any = None
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 300
    hits: int = 0
    entry_id: str = ""

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = uuid.uuid4().hex[:16]

    @property
    def is_expired(self) -> bool:
        """Check whether this cache entry has expired based on TTL."""
        elapsed = (datetime.now(timezone.utc) - self.cached_at).total_seconds()
        return elapsed > self.ttl_seconds


class OnlineFeatureStore:
    """Low-latency feature store backed by in-memory cache."""

    def __init__(self, default_ttl_seconds: int = 300, max_entries: int = 100000) -> None:
        self._cache: Dict[Tuple[str, str], CacheEntry] = {}
        self._default_ttl = default_ttl_seconds
        self._max_entries = max_entries
        self._total_hits: int = 0
        self._total_misses: int = 0

    def put(
        self,
        feature_id: str,
        entity_id: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> CacheEntry:
        """Put a feature value into the online store."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        entry = CacheEntry(
            feature_id=feature_id,
            entity_id=entity_id,
            value=value,
            ttl_seconds=ttl,
            cached_at=datetime.now(timezone.utc),
        )
        key = (feature_id, entity_id)
        self._cache[key] = entry

        # Evict if over capacity (remove oldest entries)
        if len(self._cache) > self._max_entries:
            self._evict_oldest()

        return entry

    def put_batch(
        self,
        entries: List[Dict[str, Any]],
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """Put multiple feature values. Each dict must have feature_id, entity_id, value."""
        count = 0
        for entry_data in entries:
            self.put(
                feature_id=entry_data["feature_id"],
                entity_id=entry_data["entity_id"],
                value=entry_data["value"],
                ttl_seconds=ttl_seconds,
            )
            count += 1
        return count

    def get(
        self,
        feature_id: str,
        entity_id: str,
        default: Any = None,
    ) -> Any:
        """Get a feature value from the cache. Returns default if missing or expired."""
        key = (feature_id, entity_id)
        entry = self._cache.get(key)

        if entry is None:
            self._total_misses += 1
            return default

        if entry.is_expired:
            del self._cache[key]
            self._total_misses += 1
            return default

        entry.hits += 1
        self._total_hits += 1
        return entry.value

    def get_entry(
        self,
        feature_id: str,
        entity_id: str,
    ) -> Optional[CacheEntry]:
        """Get the full cache entry (including metadata) for a feature-entity pair."""
        key = (feature_id, entity_id)
        entry = self._cache.get(key)
        if entry is None or entry.is_expired:
            return None
        return entry

    def get_feature_vector(
        self,
        feature_ids: List[str],
        entity_id: str,
    ) -> Dict[str, Any]:
        """Assemble a feature vector for model inference.

        Returns a dict of feature_id -> value for the given entity.
        Missing or expired features will have None values.
        """
        vector: Dict[str, Any] = {}
        for feature_id in feature_ids:
            vector[feature_id] = self.get(feature_id, entity_id)
        return vector

    def invalidate(
        self,
        feature_id: str,
        entity_id: Optional[str] = None,
    ) -> int:
        """Invalidate cached entries. If entity_id is None, invalidate all entries for the feature."""
        if entity_id is not None:
            key = (feature_id, entity_id)
            if key in self._cache:
                del self._cache[key]
                return 1
            return 0

        keys_to_delete = [k for k in self._cache if k[0] == feature_id]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)

    def invalidate_entity(self, entity_id: str) -> int:
        """Invalidate all cached entries for an entity."""
        keys_to_delete = [k for k in self._cache if k[1] == entity_id]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_entries = len(self._cache)
        expired = sum(1 for e in self._cache.values() if e.is_expired)
        active = total_entries - expired
        total_requests = self._total_hits + self._total_misses
        hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0

        return {
            "total_entries": total_entries,
            "active_entries": active,
            "expired_entries": expired,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": hit_rate,
            "max_entries": self._max_entries,
            "utilization": total_entries / self._max_entries if self._max_entries > 0 else 0.0,
        }

    def is_fresh(
        self,
        feature_id: str,
        entity_id: str,
        max_age_seconds: Optional[int] = None,
    ) -> bool:
        """Check if a cached value is still fresh (not expired and within max age)."""
        key = (feature_id, entity_id)
        entry = self._cache.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            return False
        if max_age_seconds is not None:
            elapsed = (datetime.now(timezone.utc) - entry.cached_at).total_seconds()
            return elapsed <= max_age_seconds
        return True

    def clear(self) -> int:
        """Clear all entries from the cache. Returns count cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    def _evict_oldest(self) -> None:
        """Evict the oldest entries to get below max_entries."""
        entries_sorted = sorted(
            self._cache.items(),
            key=lambda item: item[1].cached_at,
        )
        to_remove = len(self._cache) - self._max_entries
        for i in range(to_remove):
            del self._cache[entries_sorted[i][0]]
