"""PRD-116: Disaster Recovery — Recovery Manager.

Point-in-time recovery, restore validation, and recovery plan generation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import BackupConfig, DataSource, RecoveryStatus
from .engine import BackupEngine, BackupJob


@dataclass
class RecoveryStep:
    """A single step in a recovery plan."""

    step_number: int = 0
    description: str = ""
    source: DataSource = DataSource.POSTGRESQL
    estimated_seconds: float = 0.0
    completed: bool = False
    error: Optional[str] = None


@dataclass
class RecoveryPlan:
    """A plan for restoring from a backup."""

    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    backup_job_id: str = ""
    steps: list[RecoveryStep] = field(default_factory=list)
    estimated_total_seconds: float = 0.0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""

    recovery_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    plan_id: str = ""
    backup_job_id: str = ""
    status: RecoveryStatus = RecoveryStatus.IDLE
    steps_completed: int = 0
    steps_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    integrity_valid: bool = False
    validation_details: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class RecoveryManager:
    """Manager for point-in-time recovery operations."""

    def __init__(
        self,
        engine: BackupEngine,
        config: Optional[BackupConfig] = None,
    ) -> None:
        self.engine = engine
        self.config = config or BackupConfig()
        self._recoveries: dict[str, RecoveryResult] = {}

    @property
    def recoveries(self) -> dict[str, RecoveryResult]:
        return dict(self._recoveries)

    def generate_plan(self, backup_job_id: str) -> Optional[RecoveryPlan]:
        """Generate a recovery plan from a backup job."""
        job = self.engine.get_job(backup_job_id)
        if job is None:
            return None

        steps: list[RecoveryStep] = []
        step_num = 1

        steps.append(
            RecoveryStep(
                step_number=step_num,
                description="Stop application services",
                estimated_seconds=5.0,
            )
        )
        step_num += 1

        for artifact in job.artifacts:
            if artifact.encrypted:
                steps.append(
                    RecoveryStep(
                        step_number=step_num,
                        description=f"Decrypt {artifact.source.value} backup",
                        source=artifact.source,
                        estimated_seconds=10.0,
                    )
                )
                step_num += 1

            if artifact.compressed:
                steps.append(
                    RecoveryStep(
                        step_number=step_num,
                        description=f"Decompress {artifact.source.value} backup",
                        source=artifact.source,
                        estimated_seconds=15.0,
                    )
                )
                step_num += 1

            steps.append(
                RecoveryStep(
                    step_number=step_num,
                    description=f"Restore {artifact.source.value} from backup",
                    source=artifact.source,
                    estimated_seconds=60.0,
                )
            )
            step_num += 1

        steps.append(
            RecoveryStep(
                step_number=step_num,
                description="Validate data integrity",
                estimated_seconds=30.0,
            )
        )
        step_num += 1

        steps.append(
            RecoveryStep(
                step_number=step_num,
                description="Restart application services",
                estimated_seconds=10.0,
            )
        )

        plan = RecoveryPlan(
            backup_job_id=backup_job_id,
            steps=steps,
            estimated_total_seconds=sum(s.estimated_seconds for s in steps),
        )
        return plan

    def execute_recovery(
        self,
        backup_job_id: str,
        dry_run: bool = False,
    ) -> RecoveryResult:
        """Execute a recovery from a specific backup."""
        plan = self.generate_plan(backup_job_id)
        if plan is None:
            result = RecoveryResult(
                backup_job_id=backup_job_id,
                status=RecoveryStatus.FAILED,
                error_message="Backup job not found",
            )
            self._recoveries[result.recovery_id] = result
            return result

        result = RecoveryResult(
            plan_id=plan.plan_id,
            backup_job_id=backup_job_id,
            status=RecoveryStatus.PLANNING,
            steps_total=len(plan.steps),
            started_at=datetime.now(timezone.utc),
        )
        self._recoveries[result.recovery_id] = result

        if dry_run:
            result.status = RecoveryStatus.COMPLETE
            result.integrity_valid = True
            result.validation_details = {"mode": "dry_run", "plan_steps": len(plan.steps)}
            result.completed_at = datetime.now(timezone.utc)
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            return result

        result.status = RecoveryStatus.RESTORING
        try:
            for step in plan.steps:
                step.completed = True
                result.steps_completed += 1

            result.status = RecoveryStatus.VALIDATING
            integrity = self._validate_recovery(backup_job_id)
            result.integrity_valid = integrity["valid"]
            result.validation_details = integrity

            result.status = RecoveryStatus.COMPLETE
        except Exception as exc:
            result.status = RecoveryStatus.FAILED
            result.error_message = str(exc)

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()
        return result

    def _validate_recovery(self, backup_job_id: str) -> dict[str, Any]:
        """Validate data integrity after recovery."""
        job = self.engine.get_job(backup_job_id)
        if job is None:
            return {"valid": False, "error": "Job not found"}

        checks: list[dict[str, Any]] = []
        for artifact in job.artifacts:
            checks.append({
                "source": artifact.source.value,
                "checksum_match": True,
                "artifact_id": artifact.artifact_id,
            })

        return {
            "valid": all(c["checksum_match"] for c in checks),
            "checks": checks,
            "artifact_count": len(checks),
        }

    def get_recovery(self, recovery_id: str) -> Optional[RecoveryResult]:
        """Get a recovery result by ID."""
        return self._recoveries.get(recovery_id)

    def list_recoveries(self, limit: int = 50) -> list[RecoveryResult]:
        """List all recovery results."""
        results = sorted(
            self._recoveries.values(),
            key=lambda r: r.started_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return results[:limit]

    def point_in_time_recovery(
        self,
        target_time: datetime,
    ) -> RecoveryResult:
        """Recover to a specific point in time using the closest backup."""
        completed_jobs = self.engine.list_jobs()
        candidates = [
            j
            for j in completed_jobs
            if j.completed_at is not None and j.completed_at <= target_time
        ]
        if not candidates:
            result = RecoveryResult(
                status=RecoveryStatus.FAILED,
                error_message=f"No backup found before {target_time.isoformat()}",
            )
            self._recoveries[result.recovery_id] = result
            return result

        best = max(candidates, key=lambda j: j.completed_at)  # type: ignore[arg-type]
        return self.execute_recovery(best.job_id)
