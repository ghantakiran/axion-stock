"""Resource monitoring for PRD-130: Capacity Planning & Auto-Scaling."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from .config import CapacityConfig, CapacityStatus, ResourceThreshold, ResourceType


@dataclass
class ResourceMetric:
    """Single resource utilization measurement."""

    resource_type: ResourceType
    current_value: float
    capacity: float
    utilization_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    service: str = "default"
    metric_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    def __post_init__(self):
        if self.capacity > 0 and self.utilization_pct == 0.0:
            self.utilization_pct = (self.current_value / self.capacity) * 100.0


@dataclass
class ResourceSnapshot:
    """Point-in-time snapshot of all resource metrics."""

    snapshot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: List[ResourceMetric] = field(default_factory=list)
    overall_health: CapacityStatus = CapacityStatus.HEALTHY


class ResourceMonitor:
    """Monitors resource utilization and maintains history."""

    def __init__(self, config: Optional[CapacityConfig] = None):
        self.config = config or CapacityConfig()
        self._metrics: List[ResourceMetric] = []
        self._snapshots: List[ResourceSnapshot] = []

    def record_metric(self, metric: ResourceMetric) -> None:
        """Record a new resource metric."""
        self._metrics.append(metric)

    def get_current_utilization(
        self, resource_type: ResourceType, service: str = "default"
    ) -> Optional[ResourceMetric]:
        """Get the most recent metric for a resource type and service."""
        for metric in reversed(self._metrics):
            if metric.resource_type == resource_type and metric.service == service:
                return metric
        return None

    def get_utilization_history(
        self,
        resource_type: ResourceType,
        service: str = "default",
        hours: int = 24,
    ) -> List[ResourceMetric]:
        """Get historical metrics for a resource type and service."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            m
            for m in self._metrics
            if m.resource_type == resource_type
            and m.service == service
            and m.timestamp >= cutoff
        ]

    def take_snapshot(self) -> ResourceSnapshot:
        """Take a snapshot of current resource utilization."""
        # Collect latest metric per (resource_type, service)
        latest: Dict[Tuple[ResourceType, str], ResourceMetric] = {}
        for m in self._metrics:
            key = (m.resource_type, m.service)
            if key not in latest or m.timestamp >= latest[key].timestamp:
                latest[key] = m

        metrics = list(latest.values())
        health = self._compute_health(metrics)
        snapshot = ResourceSnapshot(
            metrics=metrics,
            overall_health=health,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def get_health_status(self) -> CapacityStatus:
        """Get overall health based on current metrics."""
        latest: Dict[Tuple[ResourceType, str], ResourceMetric] = {}
        for m in self._metrics:
            key = (m.resource_type, m.service)
            if key not in latest or m.timestamp >= latest[key].timestamp:
                latest[key] = m
        return self._compute_health(list(latest.values()))

    def top_utilized_resources(self, limit: int = 5) -> List[ResourceMetric]:
        """Get the top N most utilized resources."""
        latest: Dict[Tuple[ResourceType, str], ResourceMetric] = {}
        for m in self._metrics:
            key = (m.resource_type, m.service)
            if key not in latest or m.timestamp >= latest[key].timestamp:
                latest[key] = m
        sorted_metrics = sorted(
            latest.values(), key=lambda m: m.utilization_pct, reverse=True
        )
        return sorted_metrics[:limit]

    def resource_summary(self) -> Dict:
        """Get a summary of resource utilization."""
        latest: Dict[Tuple[ResourceType, str], ResourceMetric] = {}
        for m in self._metrics:
            key = (m.resource_type, m.service)
            if key not in latest or m.timestamp >= latest[key].timestamp:
                latest[key] = m

        by_type: Dict[str, List[float]] = defaultdict(list)
        for (rt, _), metric in latest.items():
            by_type[rt.value].append(metric.utilization_pct)

        summary: Dict = {
            "total_metrics": len(latest),
            "health": self.get_health_status().value,
            "by_resource_type": {},
        }
        for rt_val, pcts in by_type.items():
            summary["by_resource_type"][rt_val] = {
                "count": len(pcts),
                "avg_utilization_pct": sum(pcts) / len(pcts) if pcts else 0,
                "max_utilization_pct": max(pcts) if pcts else 0,
            }
        return summary

    def _compute_health(self, metrics: List[ResourceMetric]) -> CapacityStatus:
        """Compute overall health from a list of metrics."""
        if not metrics:
            return CapacityStatus.HEALTHY

        has_critical = False
        has_warning = False
        all_low = True

        for m in metrics:
            threshold = self.config.thresholds.get(
                m.resource_type, ResourceThreshold()
            )
            if m.utilization_pct >= threshold.critical_pct:
                has_critical = True
                all_low = False
            elif m.utilization_pct >= threshold.warning_pct:
                has_warning = True
                all_low = False
            elif m.utilization_pct > threshold.scale_down_pct:
                all_low = False

        if has_critical:
            return CapacityStatus.CRITICAL
        if has_warning:
            return CapacityStatus.WARNING
        if all_low and len(metrics) > 0:
            return CapacityStatus.OVER_PROVISIONED
        return CapacityStatus.HEALTHY
