"""PRD-116: Disaster Recovery — Backup Monitor.

Backup health tracking, SLA compliance, recovery drill scheduling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .config import BackupConfig, BackupStatus
from .engine import BackupEngine


@dataclass
class RecoveryDrill:
    """A scheduled or completed recovery drill."""

    drill_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    backup_job_id: str = ""
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = False
    rto_met: bool = False
    rpo_met: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAReport:
    """SLA compliance report."""

    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    rto_target_minutes: int = 60
    rpo_target_minutes: int = 15
    rto_compliance_pct: float = 0.0
    rpo_compliance_pct: float = 0.0
    backup_success_rate: float = 0.0
    total_backups: int = 0
    failed_backups: int = 0
    avg_backup_duration: float = 0.0
    storage_used_bytes: int = 0
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class BackupMonitor:
    """Monitor for backup health and SLA compliance."""

    def __init__(
        self,
        engine: BackupEngine,
        config: Optional[BackupConfig] = None,
    ) -> None:
        self.engine = engine
        self.config = config or BackupConfig()
        self._drills: dict[str, RecoveryDrill] = {}
        self._alerts: list[dict[str, Any]] = []

    def check_backup_freshness(self) -> dict[str, Any]:
        """Check if the latest backup is within RPO target."""
        jobs = self.engine.list_jobs(status=BackupStatus.COMPLETED, limit=1)
        now = datetime.now(timezone.utc)
        rpo_minutes = self.config.rpo_target_minutes

        if not jobs:
            self._add_alert("critical", "No completed backups found")
            return {
                "fresh": False,
                "last_backup": None,
                "age_minutes": None,
                "rpo_target_minutes": rpo_minutes,
            }

        latest = jobs[0]
        age = now - (latest.completed_at or latest.created_at)
        age_minutes = age.total_seconds() / 60.0
        fresh = age_minutes <= rpo_minutes

        if not fresh:
            self._add_alert(
                "warning",
                f"Backup age ({age_minutes:.1f}m) exceeds RPO ({rpo_minutes}m)",
            )

        return {
            "fresh": fresh,
            "last_backup": latest.job_id,
            "age_minutes": round(age_minutes, 1),
            "rpo_target_minutes": rpo_minutes,
        }

    def check_storage_capacity(
        self, max_bytes: int = 10 * 1024**3,
    ) -> dict[str, Any]:
        """Check storage capacity usage."""
        stats = self.engine.get_statistics()
        used = stats["total_size_bytes"]
        utilization = (used / max_bytes * 100) if max_bytes > 0 else 0.0

        if utilization > 90:
            self._add_alert("critical", f"Storage at {utilization:.1f}%")
        elif utilization > 75:
            self._add_alert("warning", f"Storage at {utilization:.1f}%")

        return {
            "used_bytes": used,
            "max_bytes": max_bytes,
            "utilization_pct": round(utilization, 1),
            "healthy": utilization < 90,
        }

    def schedule_drill(
        self,
        backup_job_id: str,
        scheduled_at: Optional[datetime] = None,
    ) -> RecoveryDrill:
        """Schedule a recovery drill."""
        drill = RecoveryDrill(
            backup_job_id=backup_job_id,
            scheduled_at=scheduled_at or datetime.now(timezone.utc),
        )
        self._drills[drill.drill_id] = drill
        return drill

    def execute_drill(self, drill_id: str) -> Optional[RecoveryDrill]:
        """Execute a scheduled recovery drill (simulated)."""
        drill = self._drills.get(drill_id)
        if drill is None:
            return None

        drill.executed_at = datetime.now(timezone.utc)
        # Simulate recovery
        drill.duration_seconds = 45.0
        drill.rto_met = drill.duration_seconds <= (
            self.config.rto_target_minutes * 60
        )

        # Check RPO by verifying backup exists
        job = self.engine.get_job(drill.backup_job_id)
        if job and job.completed_at:
            age_minutes = (
                drill.executed_at - job.completed_at
            ).total_seconds() / 60.0
            drill.rpo_met = age_minutes <= self.config.rpo_target_minutes
        else:
            drill.rpo_met = False

        drill.success = drill.rto_met and drill.rpo_met
        drill.details = {
            "rto_actual_seconds": drill.duration_seconds,
            "rto_target_seconds": self.config.rto_target_minutes * 60,
            "rpo_met": drill.rpo_met,
        }
        return drill

    def list_drills(self, limit: int = 50) -> list[RecoveryDrill]:
        """List recovery drills."""
        drills = sorted(
            self._drills.values(),
            key=lambda d: d.scheduled_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return drills[:limit]

    def generate_sla_report(
        self,
        period_days: int = 30,
    ) -> SLAReport:
        """Generate an SLA compliance report for a given period."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)
        all_jobs = self.engine.list_jobs(limit=1000)

        period_jobs = [
            j for j in all_jobs
            if j.created_at >= period_start
        ]
        completed = [j for j in period_jobs if j.status == BackupStatus.COMPLETED]
        failed = [j for j in period_jobs if j.status == BackupStatus.FAILED]

        success_rate = (
            len(completed) / len(period_jobs) * 100 if period_jobs else 0.0
        )
        avg_duration = (
            sum(j.duration_seconds for j in completed) / len(completed)
            if completed
            else 0.0
        )
        total_size = sum(j.total_size_bytes for j in completed)

        # RTO compliance from drills
        period_drills = [
            d for d in self._drills.values()
            if d.executed_at and d.executed_at >= period_start
        ]
        rto_pass = sum(1 for d in period_drills if d.rto_met)
        rpo_pass = sum(1 for d in period_drills if d.rpo_met)
        drill_count = len(period_drills) or 1  # avoid division by zero

        return SLAReport(
            period_start=period_start,
            period_end=now,
            rto_target_minutes=self.config.rto_target_minutes,
            rpo_target_minutes=self.config.rpo_target_minutes,
            rto_compliance_pct=round(rto_pass / drill_count * 100, 1),
            rpo_compliance_pct=round(rpo_pass / drill_count * 100, 1),
            backup_success_rate=round(success_rate, 1),
            total_backups=len(period_jobs),
            failed_backups=len(failed),
            avg_backup_duration=round(avg_duration, 2),
            storage_used_bytes=total_size,
        )

    def get_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get monitoring alerts."""
        return self._alerts[-limit:]

    def clear_alerts(self) -> int:
        """Clear all alerts, return count cleared."""
        count = len(self._alerts)
        self._alerts.clear()
        return count

    def _add_alert(self, severity: str, message: str) -> None:
        """Record a monitoring alert."""
        self._alerts.append({
            "severity": severity,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get all monitoring data for the dashboard."""
        return {
            "freshness": self.check_backup_freshness(),
            "statistics": self.engine.get_statistics(),
            "recent_drills": [
                {
                    "drill_id": d.drill_id,
                    "success": d.success,
                    "rto_met": d.rto_met,
                    "rpo_met": d.rpo_met,
                    "duration": d.duration_seconds,
                }
                for d in self.list_drills(limit=5)
            ],
            "alerts": self.get_alerts(limit=10),
        }
