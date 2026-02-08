"""PRD-113: ML Model Registry & Deployment Pipeline - Registry."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import ModelFramework, ModelRegistryConfig, ModelStage

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """A single version of a registered model."""

    model_name: str
    version: str
    stage: ModelStage = ModelStage.DRAFT
    framework: ModelFramework = ModelFramework.CUSTOM
    artifact_path: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    promoted_at: Optional[datetime] = None
    created_by: str = "system"


class ModelRegistry:
    """Central registry for managing ML model versions.

    Thread-safe store that supports registration, lookup, filtering,
    and deletion of model versions across their lifecycle stages.
    """

    def __init__(self, config: Optional[ModelRegistryConfig] = None) -> None:
        self._config = config or ModelRegistryConfig()
        self._models: Dict[str, List[ModelVersion]] = {}
        self._lock = threading.Lock()

    # ── Registration ─────────────────────────────────────────────────

    def register(
        self,
        model_name: str,
        version: str,
        framework: ModelFramework = ModelFramework.CUSTOM,
        metrics: Optional[Dict[str, float]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        artifact_path: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> ModelVersion:
        """Register a new model version in the registry."""
        with self._lock:
            versions = self._models.setdefault(model_name, [])

            # Enforce max versions per model
            if len(versions) >= self._config.max_versions_per_model:
                logger.warning(
                    "Model '%s' has reached the max version limit (%d). "
                    "Removing oldest DRAFT version.",
                    model_name,
                    self._config.max_versions_per_model,
                )
                # Remove oldest draft if possible
                for i, v in enumerate(versions):
                    if v.stage == ModelStage.DRAFT:
                        versions.pop(i)
                        break

            # Check for duplicate version
            for v in versions:
                if v.version == version:
                    logger.error(
                        "Version '%s' already exists for model '%s'.",
                        version,
                        model_name,
                    )
                    raise ValueError(
                        f"Version '{version}' already registered for '{model_name}'"
                    )

            mv = ModelVersion(
                model_name=model_name,
                version=version,
                framework=framework,
                metrics=metrics or {},
                hyperparameters=hyperparameters or {},
                artifact_path=artifact_path,
                tags=tags or {},
                description=description,
            )
            versions.append(mv)
            logger.info(
                "Registered model '%s' version '%s' (framework=%s).",
                model_name,
                version,
                framework.value,
            )
            return mv

    # ── Lookups ──────────────────────────────────────────────────────

    def get_version(
        self, name: str, version: str
    ) -> Optional[ModelVersion]:
        """Return a specific model version, or None."""
        with self._lock:
            for v in self._models.get(name, []):
                if v.version == version:
                    return v
            return None

    def get_latest(self, name: str) -> Optional[ModelVersion]:
        """Return the most recently registered version for a model."""
        with self._lock:
            versions = self._models.get(name, [])
            if not versions:
                return None
            return versions[-1]

    def get_production(self, name: str) -> Optional[ModelVersion]:
        """Return the latest PRODUCTION version for a model."""
        with self._lock:
            versions = self._models.get(name, [])
            production_versions = [
                v for v in versions if v.stage == ModelStage.PRODUCTION
            ]
            if not production_versions:
                return None
            # Return the one most recently promoted
            return max(production_versions, key=lambda v: v.promoted_at or v.created_at)

    # ── Listing ──────────────────────────────────────────────────────

    def list_models(self) -> List[str]:
        """Return all unique model names."""
        with self._lock:
            return list(self._models.keys())

    def list_versions(
        self, name: str, stage: Optional[ModelStage] = None
    ) -> List[ModelVersion]:
        """Return versions for a model, optionally filtered by stage."""
        with self._lock:
            versions = self._models.get(name, [])
            if stage is not None:
                return [v for v in versions if v.stage == stage]
            return list(versions)

    # ── Deletion ─────────────────────────────────────────────────────

    def delete_version(self, name: str, version: str) -> bool:
        """Delete a specific model version. Returns True if found and deleted."""
        with self._lock:
            versions = self._models.get(name, [])
            for i, v in enumerate(versions):
                if v.version == version:
                    versions.pop(i)
                    logger.info(
                        "Deleted model '%s' version '%s'.", name, version
                    )
                    if not versions:
                        del self._models[name]
                    return True
            return False

    # ── Search ───────────────────────────────────────────────────────

    def search(
        self,
        name_pattern: Optional[str] = None,
        stage: Optional[ModelStage] = None,
        framework: Optional[ModelFramework] = None,
        min_metric: Optional[float] = None,
        metric_name: Optional[str] = None,
    ) -> List[ModelVersion]:
        """Search across all models with optional filters."""
        results: List[ModelVersion] = []
        with self._lock:
            for model_name, versions in self._models.items():
                # Filter by name pattern (regex)
                if name_pattern and not re.search(name_pattern, model_name):
                    continue
                for v in versions:
                    if stage is not None and v.stage != stage:
                        continue
                    if framework is not None and v.framework != framework:
                        continue
                    if (
                        min_metric is not None
                        and metric_name is not None
                        and v.metrics.get(metric_name, float("-inf")) < min_metric
                    ):
                        continue
                    results.append(v)
        return results
