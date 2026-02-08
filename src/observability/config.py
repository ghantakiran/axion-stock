"""PRD-103: Observability & Metrics Export — Configuration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class MetricType(Enum):
    """Supported metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class ExportFormat(Enum):
    """Supported export formats."""

    PROMETHEUS = "prometheus"
    JSON = "json"


@dataclass
class HistogramBuckets:
    """Configurable histogram bucket boundaries."""

    # Default latency buckets (seconds)
    latency: List[float] = field(
        default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    # Order latency buckets (seconds)
    order_latency: List[float] = field(
        default_factory=lambda: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    # Slippage buckets (basis points)
    slippage: List[float] = field(
        default_factory=lambda: [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
    )
    # Duration buckets (seconds)
    duration: List[float] = field(
        default_factory=lambda: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
    )


@dataclass
class MetricsConfig:
    """Central configuration for the observability module."""

    # Export settings
    export_format: ExportFormat = ExportFormat.PROMETHEUS
    endpoint_path: str = "/metrics"
    include_timestamp: bool = True

    # Histogram buckets
    buckets: HistogramBuckets = field(default_factory=HistogramBuckets)

    # Metric prefix (applied to all metric names)
    prefix: str = "axion"

    # Labels applied to every metric
    global_labels: dict = field(default_factory=dict)

    # Collection settings
    collection_interval_seconds: float = 15.0
    retention_minutes: int = 60

    # Feature flags
    enable_trading_metrics: bool = True
    enable_system_metrics: bool = True
    enable_runtime_metrics: bool = True

    def prefixed(self, name: str) -> str:
        """Return metric name with prefix."""
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name
