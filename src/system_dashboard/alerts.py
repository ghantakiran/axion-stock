"""System-level alerting for health monitoring."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .config import AlertThresholds, HealthLevel
from .models import HealthSnapshot, SystemAlert, SystemMetrics


class SystemAlertManager:
    """Manages system-level alerts based on health checks and metrics."""

    def __init__(self, thresholds: Optional[AlertThresholds] = None):
        self.thresholds = thresholds or AlertThresholds()
        self._alerts: List[SystemAlert] = []

    def evaluate_metrics(self, metrics: SystemMetrics) -> List[SystemAlert]:
        """Evaluate system metrics and generate alerts."""
        new_alerts = []

        # CPU checks
        if metrics.cpu_usage >= self.thresholds.cpu_crit:
            new_alerts.append(self._create_alert(
                HealthLevel.CRITICAL, "system", f"CPU usage critical: {metrics.cpu_usage:.0%}",
                "cpu_usage", metrics.cpu_usage, self.thresholds.cpu_crit,
            ))
        elif metrics.cpu_usage >= self.thresholds.cpu_warn:
            new_alerts.append(self._create_alert(
                HealthLevel.WARNING, "system", f"CPU usage elevated: {metrics.cpu_usage:.0%}",
                "cpu_usage", metrics.cpu_usage, self.thresholds.cpu_warn,
            ))

        # Memory checks
        if metrics.memory_usage >= self.thresholds.memory_crit:
            new_alerts.append(self._create_alert(
                HealthLevel.CRITICAL, "system", f"Memory usage critical: {metrics.memory_usage:.0%}",
                "memory_usage", metrics.memory_usage, self.thresholds.memory_crit,
            ))
        elif metrics.memory_usage >= self.thresholds.memory_warn:
            new_alerts.append(self._create_alert(
                HealthLevel.WARNING, "system", f"Memory usage elevated: {metrics.memory_usage:.0%}",
                "memory_usage", metrics.memory_usage, self.thresholds.memory_warn,
            ))

        # Disk checks
        if metrics.disk_usage >= self.thresholds.disk_crit:
            new_alerts.append(self._create_alert(
                HealthLevel.CRITICAL, "system", f"Disk usage critical: {metrics.disk_usage:.0%}",
                "disk_usage", metrics.disk_usage, self.thresholds.disk_crit,
            ))
        elif metrics.disk_usage >= self.thresholds.disk_warn:
            new_alerts.append(self._create_alert(
                HealthLevel.WARNING, "system", f"Disk usage elevated: {metrics.disk_usage:.0%}",
                "disk_usage", metrics.disk_usage, self.thresholds.disk_warn,
            ))

        # Response time
        if metrics.avg_response_time_ms >= self.thresholds.response_time_crit_ms:
            new_alerts.append(self._create_alert(
                HealthLevel.CRITICAL, "api",
                f"API response time critical: {metrics.avg_response_time_ms:.0f}ms",
                "response_time", metrics.avg_response_time_ms,
                self.thresholds.response_time_crit_ms,
            ))
        elif metrics.avg_response_time_ms >= self.thresholds.response_time_warn_ms:
            new_alerts.append(self._create_alert(
                HealthLevel.WARNING, "api",
                f"API response time elevated: {metrics.avg_response_time_ms:.0f}ms",
                "response_time", metrics.avg_response_time_ms,
                self.thresholds.response_time_warn_ms,
            ))

        self._alerts.extend(new_alerts)
        return new_alerts

    def evaluate_snapshot(self, snapshot: HealthSnapshot) -> List[SystemAlert]:
        """Evaluate a health snapshot and generate service-level alerts."""
        new_alerts = []

        for svc in snapshot.services:
            if svc.status == "down":
                new_alerts.append(self._create_alert(
                    HealthLevel.DOWN, svc.service_name,
                    f"Service {svc.service_name} is DOWN",
                ))
            elif svc.status == "degraded":
                new_alerts.append(self._create_alert(
                    HealthLevel.WARNING, svc.service_name,
                    f"Service {svc.service_name} is degraded: {svc.details}",
                ))

        # Check stale data sources
        for df in snapshot.data_freshness:
            if df.is_stale and df.staleness_minutes > 0:
                new_alerts.append(self._create_alert(
                    HealthLevel.WARNING, "data_pipeline",
                    f"Data source '{df.source_name}' is stale ({df.staleness_minutes:.0f}min)",
                    "data_staleness", df.staleness_minutes,
                    self.thresholds.data_stale_minutes,
                ))

        self._alerts.extend(new_alerts)
        return new_alerts

    def _create_alert(
        self,
        level: HealthLevel,
        service: str,
        message: str,
        metric_name: str = "",
        metric_value: float = 0.0,
        threshold: float = 0.0,
    ) -> SystemAlert:
        return SystemAlert(
            alert_id=str(uuid.uuid4())[:8],
            level=level.value,
            service=service,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
        )

    def acknowledge_alert(self, alert_id: str, by: str) -> bool:
        for a in self._alerts:
            if a.alert_id == alert_id and not a.acknowledged:
                a.acknowledged = True
                a.acknowledged_by = by
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.alert_id == alert_id and a.is_active:
                a.is_active = False
                a.resolved_at = datetime.now()
                return True
        return False

    def get_active_alerts(self, level: Optional[str] = None) -> List[SystemAlert]:
        alerts = [a for a in self._alerts if a.is_active]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def get_alert_counts(self) -> Dict[str, int]:
        active = self.get_active_alerts()
        counts: Dict[str, int] = {}
        for a in active:
            counts[a.level] = counts.get(a.level, 0) + 1
        return counts

    def clear_resolved(self) -> int:
        before = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.is_active]
        return before - len(self._alerts)
