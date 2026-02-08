"""PRD-120: Deployment Strategies & Rollback Automation — Orchestrator."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import DeploymentConfig, DeploymentStatus, DeploymentStrategy

logger = logging.getLogger(__name__)


@dataclass
class Deployment:
    """Represents a single deployment."""

    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = ""
    previous_version: Optional[str] = None
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    status: DeploymentStatus = DeploymentStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deployed_by: str = "system"
    rollback_reason: Optional[str] = None
    validation_results: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class DeploymentOrchestrator:
    """Manages deployment lifecycle from creation to completion or rollback."""

    def __init__(self, config: Optional[DeploymentConfig] = None):
        self._config = config or DeploymentConfig()
        self._deployments: Dict[str, Deployment] = {}
        self._active_deployment: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def config(self) -> DeploymentConfig:
        return self._config

    def create_deployment(
        self,
        version: str,
        strategy: Optional[DeploymentStrategy] = None,
        previous_version: Optional[str] = None,
        deployed_by: str = "system",
    ) -> Deployment:
        """Create a new deployment record."""
        with self._lock:
            deployment = Deployment(
                version=version,
                strategy=strategy or self._config.default_strategy,
                previous_version=previous_version,
                deployed_by=deployed_by,
            )
            self._deployments[deployment.deployment_id] = deployment
            logger.info(
                "Created deployment %s for version %s (strategy=%s)",
                deployment.deployment_id,
                version,
                deployment.strategy.value,
            )
            return deployment

    def start_deployment(self, deployment_id: str) -> Deployment:
        """Transition a deployment to DEPLOYING status."""
        with self._lock:
            deployment = self._get_or_raise(deployment_id)
            if deployment.status != DeploymentStatus.PENDING:
                raise ValueError(
                    f"Cannot start deployment in status {deployment.status.value}"
                )
            deployment.status = DeploymentStatus.DEPLOYING
            deployment.started_at = datetime.utcnow()
            logger.info("Started deployment %s", deployment_id)
            return deployment

    def complete_deployment(self, deployment_id: str) -> Deployment:
        """Mark a deployment as ACTIVE and set it as the active deployment."""
        with self._lock:
            deployment = self._get_or_raise(deployment_id)
            if deployment.status not in (
                DeploymentStatus.DEPLOYING,
                DeploymentStatus.VALIDATING,
            ):
                raise ValueError(
                    f"Cannot complete deployment in status {deployment.status.value}"
                )
            deployment.status = DeploymentStatus.ACTIVE
            deployment.completed_at = datetime.utcnow()
            self._active_deployment = deployment_id
            logger.info(
                "Deployment %s is now ACTIVE (version %s)",
                deployment_id,
                deployment.version,
            )
            return deployment

    def fail_deployment(self, deployment_id: str, reason: str) -> Deployment:
        """Mark a deployment as FAILED."""
        with self._lock:
            deployment = self._get_or_raise(deployment_id)
            deployment.status = DeploymentStatus.FAILED
            deployment.rollback_reason = reason
            deployment.completed_at = datetime.utcnow()
            if self._active_deployment == deployment_id:
                self._active_deployment = None
            logger.warning(
                "Deployment %s FAILED: %s", deployment_id, reason
            )
            return deployment

    def get_deployment(self, deployment_id: str) -> Optional[Deployment]:
        """Retrieve a deployment by ID."""
        return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        status: Optional[DeploymentStatus] = None,
        limit: int = 20,
    ) -> List[Deployment]:
        """List deployments, optionally filtered by status."""
        deployments = list(self._deployments.values())
        if status is not None:
            deployments = [d for d in deployments if d.status == status]
        # Sort newest first by started_at (PENDING ones at end)
        deployments.sort(
            key=lambda d: d.started_at or datetime.min, reverse=True
        )
        return deployments[:limit]

    def get_active_deployment(self) -> Optional[Deployment]:
        """Return the currently active deployment, if any."""
        if self._active_deployment:
            return self._deployments.get(self._active_deployment)
        return None

    def get_deployment_history(self, limit: int = 10) -> List[Deployment]:
        """Return the most recent deployments in reverse chronological order."""
        all_deps = list(self._deployments.values())
        all_deps.sort(
            key=lambda d: d.started_at or datetime.min, reverse=True
        )
        return all_deps[:limit]

    def get_summary(self) -> dict:
        """Return aggregate deployment statistics."""
        all_deps = list(self._deployments.values())
        total = len(all_deps)
        active = sum(
            1 for d in all_deps if d.status == DeploymentStatus.ACTIVE
        )
        rolled_back = sum(
            1 for d in all_deps if d.status == DeploymentStatus.ROLLED_BACK
        )
        failed = sum(
            1 for d in all_deps if d.status == DeploymentStatus.FAILED
        )
        completed = active + rolled_back + failed
        success_rate = active / completed if completed > 0 else 0.0
        return {
            "total": total,
            "active": active,
            "rolled_back": rolled_back,
            "failed": failed,
            "success_rate": round(success_rate, 4),
        }

    def reset(self) -> None:
        """Clear all deployments (for testing)."""
        with self._lock:
            self._deployments.clear()
            self._active_deployment = None

    # ── Internal helpers ─────────────────────────────────────────────

    def _get_or_raise(self, deployment_id: str) -> Deployment:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise KeyError(f"Deployment {deployment_id} not found")
        return deployment
