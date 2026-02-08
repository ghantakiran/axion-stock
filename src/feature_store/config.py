"""Configuration for Feature Store & ML Feature Management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class FeatureType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    EMBEDDING = "embedding"


class FeatureStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    ARCHIVED = "archived"


class EntityType(str, Enum):
    STOCK = "stock"
    USER = "user"
    PORTFOLIO = "portfolio"
    ORDER = "order"


class ComputeMode(str, Enum):
    BATCH = "batch"
    REALTIME = "realtime"
    ON_DEMAND = "on_demand"


@dataclass
class FeatureStoreConfig:
    """Master configuration for the feature store."""

    cache_ttl_seconds: int = 300
    freshness_check_interval: int = 60
    max_feature_versions: int = 10
    offline_batch_size: int = 10000
    online_cache_max_entries: int = 100000
    lineage_max_depth: int = 20
    default_freshness_sla_minutes: int = 30
    enable_metrics: bool = True
    enable_lineage_tracking: bool = True
    supported_entity_types: List[EntityType] = field(
        default_factory=lambda: list(EntityType)
    )
    supported_feature_types: List[FeatureType] = field(
        default_factory=lambda: list(FeatureType)
    )
