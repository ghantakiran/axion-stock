"""Offline Feature Store for batch computation and historical retrieval."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FeatureValue:
    """A single feature value record."""

    feature_id: str = ""
    entity_id: str = ""
    value: Any = None
    as_of_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    version: int = 1
    value_id: str = ""

    def __post_init__(self):
        if not self.value_id:
            self.value_id = uuid.uuid4().hex[:16]


class OfflineFeatureStore:
    """Batch-oriented feature store for training data and historical lookups."""

    def __init__(self, max_history_per_key: int = 10000) -> None:
        # Key: (feature_id, entity_id) -> List[FeatureValue] sorted by as_of_date
        self._store: Dict[Tuple[str, str], List[FeatureValue]] = defaultdict(list)
        self._max_history = max_history_per_key

    def store(self, value: FeatureValue) -> FeatureValue:
        """Store a feature value."""
        key = (value.feature_id, value.entity_id)
        self._store[key].append(value)
        # Keep sorted by as_of_date
        self._store[key].sort(key=lambda v: v.as_of_date)
        # Trim to max history
        if len(self._store[key]) > self._max_history:
            self._store[key] = self._store[key][-self._max_history:]
        return value

    def store_batch(self, values: List[FeatureValue]) -> int:
        """Store multiple feature values at once. Returns count stored."""
        for v in values:
            self.store(v)
        return len(values)

    def get_latest(
        self,
        feature_id: str,
        entity_id: str,
    ) -> Optional[FeatureValue]:
        """Get the latest value for a feature-entity pair."""
        key = (feature_id, entity_id)
        values = self._store.get(key, [])
        if not values:
            return None
        return values[-1]

    def get_point_in_time(
        self,
        feature_id: str,
        entity_id: str,
        as_of: datetime,
    ) -> Optional[FeatureValue]:
        """Get the feature value as of a specific point in time (PIT correctness)."""
        key = (feature_id, entity_id)
        values = self._store.get(key, [])
        if not values:
            return None

        # Find the latest value that was computed at or before as_of
        result = None
        for v in values:
            if v.as_of_date <= as_of:
                result = v
            else:
                break
        return result

    def get_history(
        self,
        feature_id: str,
        entity_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FeatureValue]:
        """Get historical values for a feature-entity pair within a date range."""
        key = (feature_id, entity_id)
        values = self._store.get(key, [])

        if start_date:
            values = [v for v in values if v.as_of_date >= start_date]
        if end_date:
            values = [v for v in values if v.as_of_date <= end_date]

        return values[:limit]

    def get_training_dataset(
        self,
        feature_ids: List[str],
        entity_ids: List[str],
        as_of: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Build a training dataset by joining multiple features for multiple entities.

        Returns a list of dicts, one per entity, with feature values as of the given date.
        """
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        dataset = []
        for entity_id in entity_ids:
            row: Dict[str, Any] = {"entity_id": entity_id}
            for feature_id in feature_ids:
                val = self.get_point_in_time(feature_id, entity_id, as_of)
                row[feature_id] = val.value if val else None
            dataset.append(row)
        return dataset

    def get_statistics(self) -> Dict[str, Any]:
        """Get store-level statistics."""
        total_values = sum(len(v) for v in self._store.values())
        total_keys = len(self._store)

        feature_ids = set()
        entity_ids = set()
        for (fid, eid) in self._store.keys():
            feature_ids.add(fid)
            entity_ids.add(eid)

        oldest = None
        newest = None
        for values in self._store.values():
            if values:
                if oldest is None or values[0].as_of_date < oldest:
                    oldest = values[0].as_of_date
                if newest is None or values[-1].as_of_date > newest:
                    newest = values[-1].as_of_date

        return {
            "total_values": total_values,
            "total_keys": total_keys,
            "unique_features": len(feature_ids),
            "unique_entities": len(entity_ids),
            "oldest_value": oldest,
            "newest_value": newest,
        }

    def delete_feature(self, feature_id: str) -> int:
        """Delete all values for a given feature. Returns count deleted."""
        keys_to_delete = [k for k in self._store if k[0] == feature_id]
        total = sum(len(self._store[k]) for k in keys_to_delete)
        for k in keys_to_delete:
            del self._store[k]
        return total

    def delete_entity(self, entity_id: str) -> int:
        """Delete all values for a given entity. Returns count deleted."""
        keys_to_delete = [k for k in self._store if k[1] == entity_id]
        total = sum(len(self._store[k]) for k in keys_to_delete)
        for k in keys_to_delete:
            del self._store[k]
        return total

    def get_feature_entities(self, feature_id: str) -> List[str]:
        """Get all entity IDs that have values for a feature."""
        return [eid for (fid, eid) in self._store.keys() if fid == feature_id]
