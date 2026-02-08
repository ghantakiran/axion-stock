"""PRD-113: ML Model Registry & Deployment Pipeline - Configuration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger(__name__)


class ModelStage(str, Enum):
    """Lifecycle stage for a registered model version."""

    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ModelFramework(str, Enum):
    """ML framework used to train the model."""

    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    SKLEARN = "sklearn"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    CUSTOM = "custom"


class ExperimentStatus(str, Enum):
    """Status of an experiment run or A/B test."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ModelRegistryConfig:
    """Configuration for the model registry."""

    storage_path: str = "models/"
    max_versions_per_model: int = 50
    auto_archive_on_new_production: bool = True
    require_staging_before_production: bool = True
    min_metrics_for_promotion: List[str] = field(
        default_factory=lambda: ["accuracy"]
    )
