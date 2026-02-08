"""PRD-103: Observability & Metrics Export — System Metrics."""

import logging
from typing import Optional

from .config import MetricsConfig
from .registry import Counter, Gauge, Histogram, MetricsRegistry

logger = logging.getLogger(__name__)


class SystemMetrics:
    """System-level metrics for API, database, cache, and infrastructure."""

    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self.registry = MetricsRegistry()
        self._register_metrics()

    def _register_metrics(self) -> None:
        """Register all system metrics."""
        prefix = self.config.prefix

        # ── API Metrics ───────────────────────────────────────────────
        self.api_requests_total: Counter = self.registry.counter(
            name=f"{prefix}_api_requests_total",
            description="Total API requests processed",
            label_names=("method", "path", "status_code"),
        )

        self.api_request_duration_seconds: Histogram = self.registry.histogram(
            name=f"{prefix}_api_request_duration_seconds",
            description="API request duration in seconds",
            label_names=(),
            buckets=self.config.buckets.latency,
        )

        # ── Database Metrics ──────────────────────────────────────────
        self.db_query_duration_seconds: Histogram = self.registry.histogram(
            name=f"{prefix}_db_query_duration_seconds",
            description="Database query duration in seconds",
            label_names=("operation",),
            buckets=self.config.buckets.duration,
        )

        # ── Cache Metrics ─────────────────────────────────────────────
        self.cache_hits_total: Counter = self.registry.counter(
            name=f"{prefix}_cache_hits_total",
            description="Total cache hits",
        )

        self.cache_misses_total: Counter = self.registry.counter(
            name=f"{prefix}_cache_misses_total",
            description="Total cache misses",
        )

        # ── WebSocket Metrics ─────────────────────────────────────────
        self.websocket_connections_active: Gauge = self.registry.gauge(
            name=f"{prefix}_websocket_connections_active",
            description="Number of active WebSocket connections",
        )

        # ── Data Pipeline Metrics ─────────────────────────────────────
        self.data_pipeline_lag_seconds: Gauge = self.registry.gauge(
            name=f"{prefix}_data_pipeline_lag_seconds",
            description="Data pipeline lag in seconds",
            label_names=("source",),
        )

        logger.info("System metrics registered")

    # ── Convenience Methods ───────────────────────────────────────────

    def record_api_request(
        self,
        method: str,
        path: str,
        status_code: str,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Record an API request."""
        self.api_requests_total.increment(
            labels={"method": method, "path": path, "status_code": status_code}
        )
        if duration_seconds is not None:
            self.api_request_duration_seconds.observe(duration_seconds)

    def record_db_query(self, operation: str, duration_seconds: float) -> None:
        """Record a database query."""
        self.db_query_duration_seconds.observe(
            duration_seconds, labels={"operation": operation}
        )

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits_total.increment()

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses_total.increment()

    def update_websocket_connections(self, count: int) -> None:
        """Update active WebSocket connection count."""
        self.websocket_connections_active.set(count)

    def update_pipeline_lag(self, source: str, lag_seconds: float) -> None:
        """Update data pipeline lag for a source."""
        self.data_pipeline_lag_seconds.set(lag_seconds, labels={"source": source})

    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        hits = self.cache_hits_total.value
        misses = self.cache_misses_total.value
        total = hits + misses
        if total == 0:
            return 0.0
        return hits / total

    @staticmethod
    def generate_sample_data() -> "SystemMetrics":
        """Generate sample system metrics for dashboards."""
        sm = SystemMetrics()

        # API requests
        for _ in range(500):
            sm.record_api_request("GET", "/api/v1/quotes", "200", duration_seconds=0.05)
        for _ in range(120):
            sm.record_api_request("POST", "/api/v1/orders", "201", duration_seconds=0.15)
        for _ in range(30):
            sm.record_api_request("GET", "/api/v1/portfolio", "200", duration_seconds=0.08)
        for _ in range(8):
            sm.record_api_request("GET", "/api/v1/quotes", "500", duration_seconds=1.2)

        # DB queries
        for _ in range(200):
            sm.record_db_query("select", 0.003)
        for _ in range(50):
            sm.record_db_query("insert", 0.012)
        for _ in range(15):
            sm.record_db_query("update", 0.008)

        # Cache
        for _ in range(800):
            sm.record_cache_hit()
        for _ in range(200):
            sm.record_cache_miss()

        # WebSocket
        sm.update_websocket_connections(42)

        # Pipeline lag
        sm.update_pipeline_lag("polygon", 0.5)
        sm.update_pipeline_lag("yahoo_finance", 15.0)
        sm.update_pipeline_lag("alpaca", 0.2)

        return sm
