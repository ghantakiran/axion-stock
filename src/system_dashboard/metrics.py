"""Metrics collection and aggregation."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .config import MetricType
from .models import SystemMetrics


class MetricsCollector:
    """Collects and aggregates system metrics over time."""

    def __init__(self, max_history: int = 1440):  # 24 hours at 1-min intervals
        self.max_history = max_history
        self._snapshots: List[SystemMetrics] = []
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}

    def record_snapshot(self, metrics: SystemMetrics) -> None:
        """Record a metrics snapshot."""
        self._snapshots.append(metrics)
        if len(self._snapshots) > self.max_history:
            self._snapshots = self._snapshots[-self.max_history:]

    def increment_counter(self, name: str, value: float = 1.0) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_counter(self, name: str) -> float:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0)

    def get_latest(self) -> Optional[SystemMetrics]:
        return self._snapshots[-1] if self._snapshots else None

    def get_history(self, last_n: int = 60) -> List[SystemMetrics]:
        return self._snapshots[-last_n:]

    def get_averages(self, last_n: int = 60) -> Dict[str, float]:
        """Calculate average metrics over last N snapshots."""
        snapshots = self.get_history(last_n)
        if not snapshots:
            return {}

        n = len(snapshots)
        return {
            "avg_cpu": sum(s.cpu_usage for s in snapshots) / n,
            "avg_memory": sum(s.memory_usage for s in snapshots) / n,
            "avg_disk": sum(s.disk_usage for s in snapshots) / n,
            "avg_response_time_ms": sum(s.avg_response_time_ms for s in snapshots) / n,
            "avg_requests_per_min": sum(s.requests_per_minute for s in snapshots) / n,
            "avg_cache_hit_rate": sum(s.cache_hit_rate for s in snapshots) / n,
            "total_errors": sum(s.error_count for s in snapshots),
            "max_cpu": max(s.cpu_usage for s in snapshots),
            "max_memory": max(s.memory_usage for s in snapshots),
            "max_response_time_ms": max(s.avg_response_time_ms for s in snapshots),
        }

    def get_percentiles(
        self, metric: str, percentiles: List[float] = None
    ) -> Dict[str, float]:
        """Calculate percentiles for a metric."""
        pcts = percentiles or [50, 90, 95, 99]
        values = []

        for s in self._snapshots:
            val = getattr(s, metric, None)
            if val is not None:
                values.append(val)

        if not values:
            return {f"p{p}": 0 for p in pcts}

        values.sort()
        n = len(values)
        result = {}
        for p in pcts:
            idx = min(int(n * p / 100), n - 1)
            result[f"p{p}"] = values[idx]

        return result

    def detect_anomaly(
        self, metric: str, threshold_std: float = 2.0
    ) -> Optional[Dict]:
        """Detect anomalies using standard deviation."""
        values = [getattr(s, metric, 0) for s in self._snapshots]
        if len(values) < 10:
            return None

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5

        if std == 0:
            return None

        latest = values[-1]
        z_score = abs(latest - mean) / std

        if z_score > threshold_std:
            return {
                "metric": metric,
                "latest": latest,
                "mean": mean,
                "std": std,
                "z_score": z_score,
                "is_anomaly": True,
            }

        return None

    def reset_counters(self) -> None:
        self._counters.clear()

    @staticmethod
    def generate_sample_history(n_points: int = 60) -> "MetricsCollector":
        """Generate sample metrics history for demo."""
        import random
        random.seed(42)

        collector = MetricsCollector()
        base_time = datetime.now() - timedelta(minutes=n_points)

        for i in range(n_points):
            metrics = SystemMetrics(
                cpu_usage=0.30 + random.gauss(0, 0.10),
                memory_usage=0.60 + random.gauss(0, 0.05),
                disk_usage=0.50 + i * 0.001,
                active_connections=100 + random.randint(-20, 30),
                requests_per_minute=400 + random.gauss(0, 50),
                avg_response_time_ms=35 + random.gauss(0, 10),
                error_count=random.randint(0, 3),
                cache_hit_rate=0.92 + random.gauss(0, 0.02),
                cache_memory_mb=500 + i * 0.5,
                db_connections_active=10 + random.randint(0, 10),
                db_connections_idle=30 + random.randint(0, 15),
                recorded_at=base_time + timedelta(minutes=i),
            )
            collector.record_snapshot(metrics)

        return collector
