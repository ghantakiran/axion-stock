"""Configuration for system dashboard."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ServiceName(str, Enum):
    API = "api"
    DATABASE = "database"
    CACHE = "cache"
    DATA_PIPELINE = "data_pipeline"
    ML_SERVING = "ml_serving"
    WEBSOCKET = "websocket"
    BROKER = "broker"
    SCHEDULER = "scheduler"


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class HealthLevel(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"


# Default thresholds
DEFAULT_RESPONSE_TIME_WARN_MS = 500
DEFAULT_RESPONSE_TIME_CRIT_MS = 2000
DEFAULT_ERROR_RATE_WARN = 0.01  # 1%
DEFAULT_ERROR_RATE_CRIT = 0.05  # 5%
DEFAULT_CPU_WARN = 0.80  # 80%
DEFAULT_CPU_CRIT = 0.95  # 95%
DEFAULT_MEMORY_WARN = 0.80
DEFAULT_MEMORY_CRIT = 0.95
DEFAULT_DISK_WARN = 0.85
DEFAULT_DISK_CRIT = 0.95
DEFAULT_DATA_STALE_MINUTES = 60


@dataclass
class AlertThresholds:
    """Thresholds for system alerts."""

    response_time_warn_ms: float = DEFAULT_RESPONSE_TIME_WARN_MS
    response_time_crit_ms: float = DEFAULT_RESPONSE_TIME_CRIT_MS
    error_rate_warn: float = DEFAULT_ERROR_RATE_WARN
    error_rate_crit: float = DEFAULT_ERROR_RATE_CRIT
    cpu_warn: float = DEFAULT_CPU_WARN
    cpu_crit: float = DEFAULT_CPU_CRIT
    memory_warn: float = DEFAULT_MEMORY_WARN
    memory_crit: float = DEFAULT_MEMORY_CRIT
    disk_warn: float = DEFAULT_DISK_WARN
    disk_crit: float = DEFAULT_DISK_CRIT
    data_stale_minutes: int = DEFAULT_DATA_STALE_MINUTES


@dataclass
class SystemConfig:
    """Master system dashboard configuration."""

    check_interval_seconds: int = 60
    metrics_retention_days: int = 30
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    monitored_services: List[ServiceName] = field(
        default_factory=lambda: list(ServiceName)
    )
    data_sources: List[str] = field(default_factory=lambda: [
        "yahoo_finance", "alpha_vantage", "polygon", "finnhub",
        "fred", "sec_edgar", "news_api",
    ])
