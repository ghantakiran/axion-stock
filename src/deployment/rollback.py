"""PRD-120: Deployment Strategies & Rollback Automation — Rollback Engine."""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import DeploymentConfig

logger = logging.getLogger(__name__)


@dataclass
class RollbackAction:
    """Record of a rollback operation."""

    rollback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    from_version: str = ""
    to_version: str = ""
    reason: str = ""
    triggered_by: str = "auto"
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    success: bool = False
    steps_completed: List[str] = field(default_factory=list)


class RollbackEngine:
    """Handles automated and manual rollback of deployments."""

    def __init__(self, config: Optional[DeploymentConfig] = None):
        self._config = config or DeploymentConfig()
        self._actions: Dict[str, RollbackAction] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> DeploymentConfig:
        return self._config

    def trigger_rollback(
        self,
        deployment_id: str,
        from_version: str,
        to_version: str,
        reason: str,
        triggered_by: str = "auto",
    ) -> RollbackAction:
        """Create a rollback action record."""
        with self._lock:
            action = RollbackAction(
                deployment_id=deployment_id,
                from_version=from_version,
                to_version=to_version,
                reason=reason,
                triggered_by=triggered_by,
            )
            self._actions[action.rollback_id] = action
            logger.warning(
                "Rollback triggered for deployment %s: %s -> %s (reason: %s)",
                deployment_id,
                from_version,
                to_version,
                reason,
            )
            return action

    def execute_rollback(self, rollback_id: str) -> RollbackAction:
        """Execute a rollback by simulating standard rollback steps."""
        with self._lock:
            action = self._actions.get(rollback_id)
            if action is None:
                raise KeyError(f"Rollback {rollback_id} not found")

            steps = [
                "drain_traffic",
                "swap_version",
                "validate_health",
                "complete_rollback",
            ]

            for step in steps:
                action.steps_completed.append(step)
                logger.info(
                    "Rollback %s step completed: %s", rollback_id, step
                )

            action.success = True
            action.completed_at = datetime.utcnow()
            logger.info(
                "Rollback %s completed successfully: %s -> %s",
                rollback_id,
                action.from_version,
                action.to_version,
            )
            return action

    def get_rollback(self, rollback_id: str) -> Optional[RollbackAction]:
        """Retrieve a rollback action by ID."""
        return self._actions.get(rollback_id)

    def list_rollbacks(
        self, deployment_id: Optional[str] = None
    ) -> List[RollbackAction]:
        """List rollback actions, optionally filtered by deployment."""
        actions = list(self._actions.values())
        if deployment_id is not None:
            actions = [
                a for a in actions if a.deployment_id == deployment_id
            ]
        actions.sort(key=lambda a: a.triggered_at, reverse=True)
        return actions

    def should_auto_rollback(
        self, error_rate: float, latency_ms: float
    ) -> Tuple[bool, str]:
        """Determine whether auto-rollback should be triggered.

        Returns:
            Tuple of (should_rollback: bool, reason: str).
        """
        if not self._config.auto_rollback:
            return False, ""

        reasons = []
        if error_rate > self._config.error_rate_threshold:
            reasons.append(
                f"Error rate {error_rate:.2%} exceeds threshold "
                f"{self._config.error_rate_threshold:.2%}"
            )
        if latency_ms > self._config.latency_threshold_ms:
            reasons.append(
                f"Latency {latency_ms:.0f}ms exceeds threshold "
                f"{self._config.latency_threshold_ms:.0f}ms"
            )

        if reasons:
            combined = "; ".join(reasons)
            logger.warning("Auto-rollback recommended: %s", combined)
            return True, combined

        return False, ""

    def get_rollback_stats(self) -> dict:
        """Return rollback statistics."""
        actions = list(self._actions.values())
        total = len(actions)
        successful = sum(1 for a in actions if a.success)
        completed = [
            a
            for a in actions
            if a.completed_at is not None and a.triggered_at is not None
        ]
        if completed:
            durations = [
                (a.completed_at - a.triggered_at).total_seconds()
                for a in completed
            ]
            avg_duration = sum(durations) / len(durations)
        else:
            avg_duration = 0.0

        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "avg_duration_seconds": round(avg_duration, 2),
        }

    def reset(self) -> None:
        """Clear all rollback actions (for testing)."""
        with self._lock:
            self._actions.clear()
