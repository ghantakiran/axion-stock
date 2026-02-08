"""PRD-116: Disaster Recovery — Backup Engine.

Scheduled backup execution with compression, encryption, and multi-backend storage.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import (
    BackupConfig,
    BackupStatus,
    BackupType,
    DataSource,
    StorageBackend,
    StorageTier,
)


@dataclass
class BackupArtifact:
    """A backup artifact with metadata."""

    artifact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    backup_id: str = ""
    source: DataSource = DataSource.POSTGRESQL
    path: str = ""
    size_bytes: int = 0
    checksum: str = ""
    compressed: bool = False
    encrypted: bool = False


@dataclass
class BackupJob:
    """A backup job tracking a single backup execution."""

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    sources: list[DataSource] = field(default_factory=list)
    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_tier: StorageTier = StorageTier.HOT
    artifacts: list[BackupArtifact] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    total_size_bytes: int = 0
    error_message: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class BackupEngine:
    """Engine for executing and managing backups."""

    def __init__(self, config: Optional[BackupConfig] = None) -> None:
        self.config = config or BackupConfig()
        self._jobs: dict[str, BackupJob] = {}
        self._schedules: dict[str, dict[str, Any]] = {}

    @property
    def jobs(self) -> dict[str, BackupJob]:
        return dict(self._jobs)

    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        sources: Optional[list[DataSource]] = None,
        storage_tier: StorageTier = StorageTier.HOT,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BackupJob:
        """Create and execute a backup job."""
        effective_sources = sources or list(self.config.default_sources)

        running_count = sum(
            1 for j in self._jobs.values() if j.status == BackupStatus.RUNNING
        )
        if running_count >= self.config.max_concurrent_jobs:
            job = BackupJob(
                backup_type=backup_type,
                sources=effective_sources,
                storage_backend=self.config.storage_backend,
                storage_tier=storage_tier,
                status=BackupStatus.FAILED,
                error_message="Max concurrent jobs reached",
                metadata=metadata or {},
            )
            self._jobs[job.job_id] = job
            return job

        job = BackupJob(
            backup_type=backup_type,
            sources=effective_sources,
            storage_backend=self.config.storage_backend,
            storage_tier=storage_tier,
            status=BackupStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._jobs[job.job_id] = job

        try:
            artifacts = self._execute_backup(job)
            job.artifacts = artifacts
            job.total_size_bytes = sum(a.size_bytes for a in artifacts)
            job.status = BackupStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_seconds = (
                job.completed_at - job.started_at
            ).total_seconds()
        except Exception as exc:
            job.status = BackupStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration_seconds = (
                    job.completed_at - job.started_at
                ).total_seconds()

        return job

    def _execute_backup(self, job: BackupJob) -> list[BackupArtifact]:
        """Execute backup for all sources (simulated)."""
        artifacts = []
        for source in job.sources:
            data = f"backup:{source.value}:{job.backup_type.value}:{time.time()}"
            raw_bytes = data.encode()

            if self.config.compression_enabled:
                content = b"compressed:" + raw_bytes
            else:
                content = raw_bytes

            if self.config.encryption_enabled:
                content = b"encrypted:" + content

            checksum = hashlib.sha256(content).hexdigest()
            path = (
                f"{self.config.storage_path}/{job.job_id}/"
                f"{source.value}.bak"
            )

            artifact = BackupArtifact(
                backup_id=job.job_id,
                source=source,
                path=path,
                size_bytes=len(content),
                checksum=checksum,
                compressed=self.config.compression_enabled,
                encrypted=self.config.encryption_enabled,
            )
            artifacts.append(artifact)
        return artifacts

    def get_job(self, job_id: str) -> Optional[BackupJob]:
        """Get a backup job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[BackupStatus] = None,
        backup_type: Optional[BackupType] = None,
        limit: int = 50,
    ) -> list[BackupJob]:
        """List backup jobs with optional filters."""
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        if backup_type is not None:
            jobs = [j for j in jobs if j.backup_type == backup_type]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def schedule_backup(
        self,
        name: str,
        backup_type: BackupType,
        cron_expression: str,
        sources: Optional[list[DataSource]] = None,
    ) -> dict[str, Any]:
        """Register a scheduled backup (cron-based)."""
        schedule = {
            "name": name,
            "backup_type": backup_type.value,
            "cron": cron_expression,
            "sources": [s.value for s in (sources or self.config.default_sources)],
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._schedules[name] = schedule
        return schedule

    def list_schedules(self) -> list[dict[str, Any]]:
        """List all scheduled backups."""
        return list(self._schedules.values())

    def delete_schedule(self, name: str) -> bool:
        """Delete a scheduled backup."""
        return self._schedules.pop(name, None) is not None

    def enforce_retention(self) -> dict[str, int]:
        """Enforce retention policy — expire old backups."""
        policy = self.config.retention_policy
        now = datetime.now(timezone.utc)
        expired = {"hot": 0, "warm": 0, "cold": 0}

        completed = [
            j for j in self._jobs.values()
            if j.status == BackupStatus.COMPLETED
        ]
        completed.sort(key=lambda j: j.created_at)

        for job in completed:
            if job.completed_at is None:
                continue
            age_days = (now - job.completed_at).days

            if job.storage_tier == StorageTier.HOT and age_days > policy.hot_days:
                job.status = BackupStatus.EXPIRED
                expired["hot"] += 1
            elif job.storage_tier == StorageTier.WARM and age_days > policy.warm_days:
                job.status = BackupStatus.EXPIRED
                expired["warm"] += 1
            elif job.storage_tier == StorageTier.COLD and age_days > policy.cold_days:
                job.status = BackupStatus.EXPIRED
                expired["cold"] += 1

        return expired

    def get_statistics(self) -> dict[str, Any]:
        """Get backup system statistics."""
        all_jobs = list(self._jobs.values())
        completed = [j for j in all_jobs if j.status == BackupStatus.COMPLETED]
        failed = [j for j in all_jobs if j.status == BackupStatus.FAILED]

        total_size = sum(j.total_size_bytes for j in completed)
        avg_duration = (
            sum(j.duration_seconds for j in completed) / len(completed)
            if completed
            else 0.0
        )

        return {
            "total_jobs": len(all_jobs),
            "completed": len(completed),
            "failed": len(failed),
            "total_size_bytes": total_size,
            "avg_duration_seconds": round(avg_duration, 2),
            "success_rate": (
                round(len(completed) / len(all_jobs) * 100, 1)
                if all_jobs
                else 0.0
            ),
            "schedules": len(self._schedules),
        }
