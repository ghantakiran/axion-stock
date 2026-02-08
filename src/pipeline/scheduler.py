"""PRD-112: Data Pipeline Orchestration — Pipeline Scheduler."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .config import ScheduleType

logger = logging.getLogger(__name__)


@dataclass
class Schedule:
    """A schedule definition for a pipeline."""

    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = ""
    schedule_type: ScheduleType = ScheduleType.ONCE
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    market_hours_only: bool = False
    enabled: bool = True
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None


class PipelineScheduler:
    """Manage and evaluate pipeline schedules."""

    def __init__(self) -> None:
        self._schedules: Dict[str, Schedule] = {}
        self._lock = threading.Lock()

    # ── Schedule management ──────────────────────────────────────────

    def add_schedule(self, schedule: Schedule) -> None:
        """Register a new schedule."""
        with self._lock:
            self._schedules[schedule.schedule_id] = schedule
        logger.info(
            "Added schedule '%s' for pipeline '%s'",
            schedule.schedule_id,
            schedule.pipeline_id,
        )

    def remove_schedule(self, schedule_id: str) -> None:
        """Remove a schedule by ID."""
        with self._lock:
            if schedule_id not in self._schedules:
                raise KeyError(f"Schedule '{schedule_id}' not found")
            del self._schedules[schedule_id]
        logger.info("Removed schedule '%s'", schedule_id)

    def enable_schedule(self, schedule_id: str) -> None:
        """Enable a schedule."""
        with self._lock:
            sched = self._schedules.get(schedule_id)
            if sched is None:
                raise KeyError(f"Schedule '{schedule_id}' not found")
            sched.enabled = True

    def disable_schedule(self, schedule_id: str) -> None:
        """Disable a schedule."""
        with self._lock:
            sched = self._schedules.get(schedule_id)
            if sched is None:
                raise KeyError(f"Schedule '{schedule_id}' not found")
            sched.enabled = False

    # ── Evaluation ───────────────────────────────────────────────────

    def get_due_schedules(self, now: Optional[datetime] = None) -> List[Schedule]:
        """Return schedules whose next_run is at or before *now*."""
        now = now or datetime.utcnow()
        due: List[Schedule] = []
        for sched in self._schedules.values():
            if not sched.enabled:
                continue
            if sched.next_run is not None and sched.next_run <= now:
                if sched.market_hours_only and not self.is_market_hours(now):
                    continue
                due.append(sched)
        return due

    def update_next_run(self, schedule_id: str) -> None:
        """Compute and set the next run time after execution."""
        with self._lock:
            sched = self._schedules.get(schedule_id)
            if sched is None:
                raise KeyError(f"Schedule '{schedule_id}' not found")

            now = datetime.utcnow()
            sched.last_run = now

            if sched.schedule_type == ScheduleType.ONCE:
                # One-shot schedule — disable after run
                sched.next_run = None
                sched.enabled = False

            elif sched.schedule_type == ScheduleType.RECURRING:
                if sched.interval_seconds is not None:
                    sched.next_run = now + timedelta(seconds=sched.interval_seconds)
                else:
                    sched.next_run = None

            elif sched.schedule_type == ScheduleType.CRON:
                # Simplified cron: just advance by 60 seconds for now
                # A full cron parser would be used in production
                sched.next_run = now + timedelta(seconds=60)

            elif sched.schedule_type == ScheduleType.MARKET_HOURS:
                # Schedule next run for 1 minute from now during market hours
                if sched.interval_seconds is not None:
                    sched.next_run = now + timedelta(seconds=sched.interval_seconds)
                else:
                    sched.next_run = now + timedelta(seconds=60)

    # ── Market hours ─────────────────────────────────────────────────

    @staticmethod
    def is_market_hours(dt: Optional[datetime] = None) -> bool:
        """Check whether *dt* falls within US equity market hours.

        Market hours: Monday–Friday, 09:30–16:00 Eastern Time.
        For simplicity, assumes UTC-5 (EST) without DST handling.
        """
        dt = dt or datetime.utcnow()
        # Convert UTC to Eastern (simplified: UTC - 5)
        eastern = dt - timedelta(hours=5)
        weekday = eastern.weekday()  # 0=Mon … 6=Sun
        if weekday >= 5:
            return False
        market_open = eastern.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = eastern.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= eastern <= market_close

    # ── Accessors ────────────────────────────────────────────────────

    def get_schedules(self) -> List[Schedule]:
        """Return all registered schedules."""
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Return a schedule by ID, or None."""
        return self._schedules.get(schedule_id)
