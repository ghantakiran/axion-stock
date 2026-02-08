"""Health check framework for system services."""

import random
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from .config import AlertThresholds, ServiceName, ServiceStatus, SystemConfig
from .models import (
    DataFreshness,
    DependencyStatus,
    HealthSnapshot,
    ServiceHealth,
    SystemMetrics,
    SystemSummary,
)


class HealthChecker:
    """Runs health checks across all system services."""

    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self._custom_checks: Dict[str, Callable] = {}
        self._history: List[HealthSnapshot] = []

    def register_check(self, service_name: str, check_fn: Callable) -> None:
        """Register a custom health check function."""
        self._custom_checks[service_name] = check_fn

    def check_service(
        self,
        service_name: str,
        response_time_ms: float = 0.0,
        error_rate: float = 0.0,
        is_available: bool = True,
        version: str = "",
    ) -> ServiceHealth:
        """Check health of a single service."""
        thresholds = self.config.alert_thresholds

        if not is_available:
            status = ServiceStatus.DOWN.value
        elif (response_time_ms > thresholds.response_time_crit_ms
              or error_rate > thresholds.error_rate_crit):
            status = ServiceStatus.DEGRADED.value
        elif (response_time_ms > thresholds.response_time_warn_ms
              or error_rate > thresholds.error_rate_warn):
            status = ServiceStatus.DEGRADED.value
        else:
            status = ServiceStatus.HEALTHY.value

        uptime = 100.0 if is_available else 0.0
        details = f"Response: {response_time_ms:.0f}ms, Errors: {error_rate:.2%}"

        return ServiceHealth(
            service_name=service_name,
            status=status,
            response_time_ms=response_time_ms,
            error_rate=error_rate,
            uptime_pct=uptime,
            details=details,
            version=version,
        )

    def check_all_services(
        self, service_data: Optional[Dict[str, Dict]] = None
    ) -> List[ServiceHealth]:
        """Check all monitored services."""
        results = []

        data = service_data or {}
        for svc in self.config.monitored_services:
            svc_info = data.get(svc.value, {})
            health = self.check_service(
                service_name=svc.value,
                response_time_ms=svc_info.get("response_time_ms", 0),
                error_rate=svc_info.get("error_rate", 0),
                is_available=svc_info.get("is_available", True),
                version=svc_info.get("version", ""),
            )

            # Run custom check if registered
            if svc.value in self._custom_checks:
                try:
                    custom_result = self._custom_checks[svc.value]()
                    if not custom_result:
                        health.status = ServiceStatus.DEGRADED.value
                        health.details += " [custom check failed]"
                except Exception as e:
                    health.status = ServiceStatus.DEGRADED.value
                    health.details += f" [custom check error: {str(e)[:50]}]"

            results.append(health)

        return results

    def check_data_freshness(
        self, source_updates: Optional[Dict[str, datetime]] = None
    ) -> List[DataFreshness]:
        """Check data freshness for all configured sources."""
        now = datetime.now()
        stale_threshold = timedelta(minutes=self.config.alert_thresholds.data_stale_minutes)
        updates = source_updates or {}

        results = []
        for source in self.config.data_sources:
            last_update = updates.get(source)
            if last_update:
                staleness = (now - last_update).total_seconds() / 60
                is_stale = (now - last_update) > stale_threshold
                status = "stale" if is_stale else "fresh"
            else:
                staleness = float("inf")
                is_stale = True
                status = "unknown"

            results.append(DataFreshness(
                source_name=source,
                last_update=last_update,
                is_stale=is_stale,
                staleness_minutes=staleness if staleness != float("inf") else -1,
                status=status,
            ))

        return results

    def check_dependencies(
        self, dep_data: Optional[List[Dict]] = None
    ) -> List[DependencyStatus]:
        """Check external dependency health."""
        if not dep_data:
            return []

        results = []
        for dep in dep_data:
            status = "healthy" if dep.get("available", True) else "down"
            results.append(DependencyStatus(
                name=dep.get("name", ""),
                endpoint=dep.get("endpoint", ""),
                status=status,
                response_time_ms=dep.get("response_time_ms", 0),
                last_success=dep.get("last_success"),
                failure_count=dep.get("failures", 0),
            ))

        return results

    def capture_snapshot(
        self,
        service_data: Optional[Dict[str, Dict]] = None,
        metrics: Optional[SystemMetrics] = None,
        source_updates: Optional[Dict[str, datetime]] = None,
        dep_data: Optional[List[Dict]] = None,
    ) -> HealthSnapshot:
        """Capture a complete system health snapshot."""
        services = self.check_all_services(service_data)
        freshness = self.check_data_freshness(source_updates)
        dependencies = self.check_dependencies(dep_data)

        # Determine overall status
        down_count = sum(1 for s in services if s.status == "down")
        degraded_count = sum(1 for s in services if s.status == "degraded")

        if down_count > 0:
            overall = "down"
        elif degraded_count > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        snapshot = HealthSnapshot(
            services=services,
            metrics=metrics or SystemMetrics(),
            data_freshness=freshness,
            dependencies=dependencies,
            overall_status=overall,
        )

        self._history.append(snapshot)
        return snapshot

    def get_summary(self, snapshot: HealthSnapshot) -> SystemSummary:
        """Generate a summary from a health snapshot."""
        metrics = snapshot.metrics or SystemMetrics()

        return SystemSummary(
            overall_status=snapshot.overall_status,
            total_services=len(snapshot.services),
            healthy_services=snapshot.n_healthy,
            degraded_services=snapshot.n_degraded,
            down_services=snapshot.n_down,
            active_alerts=len(snapshot.active_alerts),
            critical_alerts=len([a for a in snapshot.active_alerts if a.level == "critical"]),
            cpu_usage=metrics.cpu_usage,
            memory_usage=metrics.memory_usage,
            disk_usage=metrics.disk_usage,
            requests_per_minute=metrics.requests_per_minute,
            avg_response_time_ms=metrics.avg_response_time_ms,
            cache_hit_rate=metrics.cache_hit_rate,
            stale_data_sources=len(snapshot.stale_sources),
        )

    def get_history(self, last_n: int = 10) -> List[HealthSnapshot]:
        return self._history[-last_n:]

    @staticmethod
    def generate_sample_snapshot() -> HealthSnapshot:
        """Generate a realistic sample snapshot for demo."""
        checker = HealthChecker()
        random.seed(42)

        service_data = {
            "api": {"response_time_ms": 45, "error_rate": 0.002, "is_available": True, "version": "2.1.0"},
            "database": {"response_time_ms": 12, "error_rate": 0.0, "is_available": True, "version": "15.4"},
            "cache": {"response_time_ms": 2, "error_rate": 0.0, "is_available": True, "version": "7.2"},
            "data_pipeline": {"response_time_ms": 250, "error_rate": 0.005, "is_available": True},
            "ml_serving": {"response_time_ms": 120, "error_rate": 0.001, "is_available": True, "version": "1.5.0"},
            "websocket": {"response_time_ms": 8, "error_rate": 0.0, "is_available": True},
            "broker": {"response_time_ms": 85, "error_rate": 0.003, "is_available": True},
            "scheduler": {"response_time_ms": 5, "error_rate": 0.0, "is_available": True},
        }

        metrics = SystemMetrics(
            cpu_usage=0.42,
            memory_usage=0.65,
            disk_usage=0.55,
            active_connections=128,
            requests_per_minute=450.0,
            avg_response_time_ms=38.5,
            error_count=12,
            cache_hit_rate=0.94,
            cache_memory_mb=512.0,
            db_connections_active=15,
            db_connections_idle=35,
        )

        now = datetime.now()
        source_updates = {
            "yahoo_finance": now - timedelta(minutes=5),
            "alpha_vantage": now - timedelta(minutes=15),
            "polygon": now - timedelta(minutes=3),
            "finnhub": now - timedelta(minutes=8),
            "fred": now - timedelta(hours=6),
            "sec_edgar": now - timedelta(hours=2),
            "news_api": now - timedelta(minutes=10),
        }

        return checker.capture_snapshot(service_data, metrics, source_updates)
