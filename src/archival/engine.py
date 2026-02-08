"""Archival engine for executing data archival jobs."""

import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .config import ArchivalConfig, ArchivalFormat

logger = logging.getLogger(__name__)


@dataclass
class ArchivalJob:
    """Represents a single archival job."""

    job_id: str = field(default_factory=lambda: str(uuid4()))
    table_name: str = ""
    date_range_start: datetime = field(default_factory=datetime.utcnow)
    date_range_end: datetime = field(default_factory=datetime.utcnow)
    format: ArchivalFormat = ArchivalFormat.PARQUET
    status: str = "pending"
    records_archived: int = 0
    bytes_written: int = 0
    storage_path: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ArchivalEngine:
    """Engine for creating and executing data archival jobs."""

    def __init__(self, config: Optional[ArchivalConfig] = None):
        self._config = config or ArchivalConfig()
        self._jobs: Dict[str, ArchivalJob] = {}
        self._catalog: Dict[str, ArchivalJob] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        table_name: str,
        start: datetime,
        end: datetime,
        format: Optional[ArchivalFormat] = None,
    ) -> ArchivalJob:
        """Create a new archival job for a table and date range."""
        with self._lock:
            job = ArchivalJob(
                table_name=table_name,
                date_range_start=start,
                date_range_end=end,
                format=format or self._config.default_format,
            )
            self._jobs[job.job_id] = job
            logger.info("Created archival job %s for table %s", job.job_id, table_name)
            return job

    def execute_job(self, job_id: str) -> ArchivalJob:
        """Execute an archival job (simulated)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            job.status = "running"
            job.started_at = datetime.utcnow()

            try:
                # Simulate archival work
                days_span = max(1, (job.date_range_end - job.date_range_start).days)
                job.records_archived = random.randint(1000, self._config.max_batch_size) * days_span // 30
                job.bytes_written = job.records_archived * random.randint(200, 800)
                job.storage_path = (
                    f"{self._config.storage_path}{job.table_name}/"
                    f"{job.date_range_start.strftime('%Y%m%d')}_"
                    f"{job.date_range_end.strftime('%Y%m%d')}.{job.format.value}"
                )

                job.status = "completed"
                job.completed_at = datetime.utcnow()

                # Update catalog
                catalog_key = f"{job.table_name}:{job.date_range_start.isoformat()}:{job.date_range_end.isoformat()}"
                self._catalog[catalog_key] = job

                logger.info(
                    "Completed archival job %s: %d records, %d bytes",
                    job.job_id, job.records_archived, job.bytes_written,
                )
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.utcnow()
                logger.error("Archival job %s failed: %s", job.job_id, e)

            return job

    def get_job(self, job_id: str) -> Optional[ArchivalJob]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        table_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ArchivalJob]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())
        if table_name:
            jobs = [j for j in jobs if j.table_name == table_name]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def restore_from_archive(self, job_id: str) -> dict:
        """Restore data from a completed archival job."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != "completed":
            raise ValueError(f"Job {job_id} is not in completed state (status={job.status})")

        logger.info("Restoring %d records from archive job %s", job.records_archived, job_id)
        return {
            "status": "restored",
            "records": job.records_archived,
            "source_path": job.storage_path,
            "table_name": job.table_name,
            "restored_at": datetime.utcnow().isoformat(),
        }

    def get_catalog(self) -> Dict[str, ArchivalJob]:
        """Return the full catalog of archived data ranges."""
        return dict(self._catalog)

    def get_storage_stats(self) -> dict:
        """Return aggregate storage statistics."""
        completed = [j for j in self._jobs.values() if j.status == "completed"]
        return {
            "total_jobs": len(self._jobs),
            "completed_jobs": len(completed),
            "total_bytes": sum(j.bytes_written for j in completed),
            "total_records": sum(j.records_archived for j in completed),
        }

    def reset(self) -> None:
        """Reset all engine state."""
        with self._lock:
            self._jobs.clear()
            self._catalog.clear()
