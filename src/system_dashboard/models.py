"""Data models for system dashboard."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ServiceHealth:
    """Health status of a single service."""

    service_name: str
    status: str  # healthy, degraded, down, unknown
    response_time_ms: float = 0.0
    error_rate: float = 0.0
    uptime_pct: float = 100.0
    last_check: datetime = field(default_factory=datetime.now)
    details: str = ""
    version: str = ""


@dataclass
class SystemMetrics:
    """System resource metrics snapshot."""

    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    active_connections: int = 0
    requests_per_minute: float = 0.0
    avg_response_time_ms: float = 0.0
    error_count: int = 0
    cache_hit_rate: float = 0.0
    cache_memory_mb: float = 0.0
    db_connections_active: int = 0
    db_connections_idle: int = 0
    recorded_at: datetime = field(default_factory=datetime.now)


@dataclass
class DataFreshness:
    """Data freshness tracking per source."""

    source_name: str
    last_update: Optional[datetime] = None
    records_count: int = 0
    is_stale: bool = False
    staleness_minutes: float = 0.0
    status: str = "unknown"


@dataclass
class DependencyStatus:
    """External dependency health."""

    name: str
    endpoint: str = ""
    status: str = "unknown"
    response_time_ms: float = 0.0
    last_success: Optional[datetime] = None
    failure_count: int = 0


@dataclass
class SystemAlert:
    """System-level alert."""

    alert_id: str
    level: str  # healthy, warning, critical, down
    service: str
    message: str
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    is_active: bool = True
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None


@dataclass
class HealthSnapshot:
    """Complete system health snapshot."""

    services: List[ServiceHealth] = field(default_factory=list)
    metrics: Optional[SystemMetrics] = None
    data_freshness: List[DataFreshness] = field(default_factory=list)
    dependencies: List[DependencyStatus] = field(default_factory=list)
    active_alerts: List[SystemAlert] = field(default_factory=list)
    overall_status: str = "healthy"
    captured_at: datetime = field(default_factory=datetime.now)

    @property
    def n_healthy(self) -> int:
        return len([s for s in self.services if s.status == "healthy"])

    @property
    def n_degraded(self) -> int:
        return len([s for s in self.services if s.status == "degraded"])

    @property
    def n_down(self) -> int:
        return len([s for s in self.services if s.status == "down"])

    @property
    def stale_sources(self) -> List[str]:
        return [d.source_name for d in self.data_freshness if d.is_stale]


@dataclass
class SystemSummary:
    """High-level system summary for dashboard."""

    overall_status: str = "healthy"
    total_services: int = 0
    healthy_services: int = 0
    degraded_services: int = 0
    down_services: int = 0
    active_alerts: int = 0
    critical_alerts: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    requests_per_minute: float = 0.0
    avg_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    stale_data_sources: int = 0
    uptime_hours: float = 0.0
    generated_at: datetime = field(default_factory=datetime.now)
