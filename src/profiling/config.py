"""Configuration for performance profiling & query optimization."""

from dataclasses import dataclass
from enum import Enum


class QuerySeverity(str, Enum):
    """Severity classification for query performance."""

    NORMAL = "normal"
    SLOW = "slow"
    CRITICAL = "critical"


class IndexStatus(str, Enum):
    """Lifecycle status of an index recommendation."""

    RECOMMENDED = "recommended"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass
class ProfilingConfig:
    """Master configuration for profiling subsystem."""

    slow_query_threshold_ms: float = 1000.0
    critical_query_threshold_ms: float = 5000.0
    max_query_history: int = 10000
    enable_explain: bool = True
    enable_n1_detection: bool = True
    pool_warning_threshold: float = 0.8
    pool_critical_threshold: float = 0.95
    idle_connection_timeout_seconds: int = 300
