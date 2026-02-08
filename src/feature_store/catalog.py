"""Feature Catalog for discovery, registration, and management."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import EntityType, FeatureStatus, FeatureType


@dataclass
class FeatureDefinition:
    """Metadata definition for a single feature."""

    feature_id: str = ""
    name: str = ""
    description: str = ""
    feature_type: FeatureType = FeatureType.NUMERIC
    entity_type: EntityType = EntityType.STOCK
    owner: str = ""
    freshness_sla_minutes: int = 30
    version: int = 1
    status: FeatureStatus = FeatureStatus.ACTIVE
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    compute_mode: str = "batch"
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.feature_id:
            self.feature_id = uuid.uuid4().hex[:16]


class FeatureCatalog:
    """Central registry for feature definitions with search and management."""

    def __init__(self) -> None:
        self._features: Dict[str, FeatureDefinition] = {}
        self._versions: Dict[str, List[FeatureDefinition]] = {}

    def register(self, feature: FeatureDefinition) -> FeatureDefinition:
        """Register a new feature definition in the catalog."""
        if feature.name in self._get_names() and feature.feature_id not in self._features:
            existing = self.get_by_name(feature.name)
            if existing and existing.status == FeatureStatus.ACTIVE:
                feature.version = existing.version + 1
                self._add_version(existing.feature_id, existing)
        self._features[feature.feature_id] = feature
        return feature

    def get(self, feature_id: str) -> Optional[FeatureDefinition]:
        """Get a feature definition by ID."""
        return self._features.get(feature_id)

    def get_by_name(self, name: str) -> Optional[FeatureDefinition]:
        """Get a feature definition by name."""
        for f in self._features.values():
            if f.name == name:
                return f
        return None

    def search(
        self,
        query: str = "",
        feature_type: Optional[FeatureType] = None,
        entity_type: Optional[EntityType] = None,
        status: Optional[FeatureStatus] = None,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[FeatureDefinition]:
        """Search features with optional filters."""
        results = list(self._features.values())

        if query:
            q = query.lower()
            results = [
                f for f in results
                if q in f.name.lower() or q in f.description.lower()
            ]

        if feature_type is not None:
            results = [f for f in results if f.feature_type == feature_type]

        if entity_type is not None:
            results = [f for f in results if f.entity_type == entity_type]

        if status is not None:
            results = [f for f in results if f.status == status]

        if owner is not None:
            results = [f for f in results if f.owner == owner]

        if tags:
            results = [
                f for f in results
                if any(t in f.tags for t in tags)
            ]

        return results

    def deprecate(self, feature_id: str, reason: str = "") -> bool:
        """Mark a feature as deprecated."""
        feature = self._features.get(feature_id)
        if not feature:
            return False
        feature.status = FeatureStatus.DEPRECATED
        feature.updated_at = datetime.now(timezone.utc)
        if reason:
            feature.metadata["deprecation_reason"] = reason
        return True

    def archive(self, feature_id: str) -> bool:
        """Mark a feature as archived."""
        feature = self._features.get(feature_id)
        if not feature:
            return False
        feature.status = FeatureStatus.ARCHIVED
        feature.updated_at = datetime.now(timezone.utc)
        return True

    def list_features(
        self,
        status: Optional[FeatureStatus] = None,
        entity_type: Optional[EntityType] = None,
    ) -> List[FeatureDefinition]:
        """List all features with optional filters."""
        results = list(self._features.values())
        if status is not None:
            results = [f for f in results if f.status == status]
        if entity_type is not None:
            results = [f for f in results if f.entity_type == entity_type]
        return results

    def get_dependencies(self, feature_id: str) -> List[FeatureDefinition]:
        """Get all features that this feature depends on."""
        feature = self._features.get(feature_id)
        if not feature:
            return []
        deps = []
        for dep_id in feature.dependencies:
            dep = self._features.get(dep_id)
            if dep:
                deps.append(dep)
        return deps

    def get_dependents(self, feature_id: str) -> List[FeatureDefinition]:
        """Get all features that depend on this feature."""
        return [
            f for f in self._features.values()
            if feature_id in f.dependencies
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get catalog-wide statistics."""
        features = list(self._features.values())
        status_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        entity_counts: Dict[str, int] = {}
        owner_counts: Dict[str, int] = {}

        for f in features:
            status_counts[f.status.value] = status_counts.get(f.status.value, 0) + 1
            type_counts[f.feature_type.value] = type_counts.get(f.feature_type.value, 0) + 1
            entity_counts[f.entity_type.value] = entity_counts.get(f.entity_type.value, 0) + 1
            if f.owner:
                owner_counts[f.owner] = owner_counts.get(f.owner, 0) + 1

        return {
            "total_features": len(features),
            "by_status": status_counts,
            "by_type": type_counts,
            "by_entity": entity_counts,
            "by_owner": owner_counts,
            "total_deprecated": status_counts.get("deprecated", 0),
            "total_active": status_counts.get("active", 0),
        }

    def remove(self, feature_id: str) -> bool:
        """Remove a feature from the catalog."""
        if feature_id in self._features:
            del self._features[feature_id]
            return True
        return False

    def _get_names(self) -> List[str]:
        return [f.name for f in self._features.values()]

    def _add_version(self, feature_id: str, feature: FeatureDefinition) -> None:
        if feature_id not in self._versions:
            self._versions[feature_id] = []
        self._versions[feature_id].append(feature)

    def get_versions(self, feature_id: str) -> List[FeatureDefinition]:
        """Get all historical versions of a feature."""
        versions = list(self._versions.get(feature_id, []))
        current = self._features.get(feature_id)
        if current:
            versions.append(current)
        return versions
