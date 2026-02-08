"""PRD-112: Data Pipeline Orchestration — Monitoring & SLA."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import PipelineStatus, SLAConfig
from .definition import PipelineRun

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Aggregated metrics for a single pipeline."""

    pipeline_id: str = ""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    avg_duration_ms: float = 0.0
    last_run_at: Optional[datetime] = None
    last_status: Optional[PipelineStatus] = None

    @property
    def success_rate(self) -> float:
        """Fraction of runs that succeeded (0.0–1.0)."""
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs


@dataclass
class FreshnessCheck:
    """Tracks data freshness for a named source."""

    source_name: str = ""
    last_updated: Optional[datetime] = None
    max_staleness_seconds: int = 3600

    @property
    def is_fresh(self) -> bool:
        """Return True if data is within the staleness window."""
        if self.last_updated is None:
            return False
        elapsed = (datetime.utcnow() - self.last_updated).total_seconds()
        return elapsed <= self.max_staleness_seconds


@dataclass
class SLAResult:
    """Outcome of an SLA check."""

    passed: bool = True
    violations: List[str] = field(default_factory=list)


class PipelineMonitor:
    """Track pipeline metrics, SLAs, and data freshness."""

    def __init__(self) -> None:
        self._metrics: Dict[str, PipelineMetrics] = {}
        self._freshness_checks: Dict[str, FreshnessCheck] = {}
        self._sla_configs: Dict[str, SLAConfig] = {}
        self._durations: Dict[str, List[float]] = {}  # pipeline_id -> list of ms

    # ── Run recording ────────────────────────────────────────────────

    def record_run(self, pipeline_id: str, run: PipelineRun) -> None:
        """Update metrics after a pipeline run completes."""
        if pipeline_id not in self._metrics:
            self._metrics[pipeline_id] = PipelineMetrics(pipeline_id=pipeline_id)

        m = self._metrics[pipeline_id]
        m.total_runs += 1
        m.last_run_at = run.completed_at or datetime.utcnow()
        m.last_status = run.status

        if run.status == PipelineStatus.SUCCESS:
            m.successful_runs += 1
        elif run.status == PipelineStatus.FAILED:
            m.failed_runs += 1

        # Track duration
        if run.started_at and run.completed_at:
            duration_ms = (run.completed_at - run.started_at).total_seconds() * 1000
            if pipeline_id not in self._durations:
                self._durations[pipeline_id] = []
            self._durations[pipeline_id].append(duration_ms)
            m.avg_duration_ms = sum(self._durations[pipeline_id]) / len(
                self._durations[pipeline_id]
            )

        logger.info(
            "Recorded run for '%s': status=%s, total=%d",
            pipeline_id,
            run.status.value,
            m.total_runs,
        )

    # ── Metrics access ───────────────────────────────────────────────

    def get_metrics(self, pipeline_id: str) -> Optional[PipelineMetrics]:
        """Return metrics for a specific pipeline."""
        return self._metrics.get(pipeline_id)

    def get_all_metrics(self) -> Dict[str, PipelineMetrics]:
        """Return metrics for all tracked pipelines."""
        return dict(self._metrics)

    # ── SLA management ───────────────────────────────────────────────

    def set_sla(self, pipeline_id: str, sla: SLAConfig) -> None:
        """Set or update the SLA configuration for a pipeline."""
        self._sla_configs[pipeline_id] = sla

    def check_sla(self, pipeline_id: str) -> SLAResult:
        """Check whether a pipeline meets its SLA requirements."""
        sla = self._sla_configs.get(pipeline_id)
        if sla is None:
            return SLAResult(passed=True, violations=[])

        violations: List[str] = []
        m = self._metrics.get(pipeline_id)

        if m is not None:
            # Check failure rate
            failure_rate = 1.0 - m.success_rate
            if failure_rate > sla.max_failure_rate:
                violations.append(
                    f"Failure rate {failure_rate:.1%} exceeds max {sla.max_failure_rate:.1%}"
                )

            # Check average duration
            if m.avg_duration_ms > sla.max_duration_seconds * 1000:
                violations.append(
                    f"Avg duration {m.avg_duration_ms:.0f}ms exceeds max {sla.max_duration_seconds * 1000:.0f}ms"
                )

        return SLAResult(passed=len(violations) == 0, violations=violations)

    # ── Freshness monitoring ─────────────────────────────────────────

    def add_freshness_check(self, name: str, max_staleness_seconds: int) -> None:
        """Register a freshness check for a data source."""
        self._freshness_checks[name] = FreshnessCheck(
            source_name=name,
            max_staleness_seconds=max_staleness_seconds,
        )

    def update_freshness(self, name: str, timestamp: Optional[datetime] = None) -> None:
        """Mark a data source as freshly updated."""
        if name not in self._freshness_checks:
            raise KeyError(f"Freshness check '{name}' not registered")
        self._freshness_checks[name].last_updated = timestamp or datetime.utcnow()

    def get_stale_sources(self) -> List[str]:
        """Return names of data sources that are stale."""
        return [
            name
            for name, check in self._freshness_checks.items()
            if not check.is_fresh
        ]

    # ── Health score ─────────────────────────────────────────────────

    def get_health_score(self, pipeline_id: str) -> float:
        """Compute a health score (0.0–1.0) for a pipeline.

        Based on success rate (70% weight) and SLA compliance (30% weight).
        """
        m = self._metrics.get(pipeline_id)
        if m is None:
            return 0.0

        success_component = m.success_rate * 0.7

        sla_result = self.check_sla(pipeline_id)
        sla_component = (1.0 if sla_result.passed else 0.0) * 0.3

        return min(1.0, success_component + sla_component)
