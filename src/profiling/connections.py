"""Connection pool monitoring and leak detection."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.profiling.config import ProfilingConfig

logger = logging.getLogger(__name__)


@dataclass
class ConnectionStats:
    """Snapshot of connection pool state."""

    pool_size: int = 10
    active: int = 0
    idle: int = 0
    waiting: int = 0
    max_overflow: int = 0
    overflow_used: int = 0

    @property
    def utilization(self) -> float:
        """Connection pool utilization ratio."""
        if self.pool_size == 0:
            return 0.0
        return self.active / self.pool_size

    @property
    def is_saturated(self) -> bool:
        """Whether the pool is nearly fully utilized."""
        return self.utilization > 0.9


@dataclass
class LongRunningQuery:
    """A query that has been running for an extended period."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    user: str = "unknown"
    state: str = "active"


class ConnectionMonitor:
    """Monitors database connection pools and detects issues."""

    def __init__(self, config: Optional[ProfilingConfig] = None):
        self._config = config or ProfilingConfig()
        self._stats_history: List[ConnectionStats] = []
        self._long_queries: Dict[str, LongRunningQuery] = {}
        self._leaks: List[Dict] = []
        self._lock = threading.Lock()

    def record_stats(self, stats: ConnectionStats) -> None:
        """Record a connection pool stats snapshot."""
        with self._lock:
            self._stats_history.append(stats)
        logger.debug(
            "Connection stats recorded: %d active, %d idle, utilization %.1f%%",
            stats.active,
            stats.idle,
            stats.utilization * 100,
        )

    def get_current_stats(self) -> Optional[ConnectionStats]:
        """Return the most recent stats snapshot."""
        with self._lock:
            if self._stats_history:
                return self._stats_history[-1]
        return None

    def get_utilization_trend(self, limit: int = 100) -> List[float]:
        """Return recent utilization values."""
        with self._lock:
            entries = self._stats_history[-limit:]
            return [s.utilization for s in entries]

    def detect_pool_exhaustion(self) -> dict:
        """Check if the connection pool is approaching exhaustion."""
        with self._lock:
            if not self._stats_history:
                return {
                    "at_risk": False,
                    "utilization": 0.0,
                    "recommendation": "No data available",
                }

            current = self._stats_history[-1]
            util = current.utilization

            if util >= self._config.pool_critical_threshold:
                return {
                    "at_risk": True,
                    "utilization": util,
                    "recommendation": (
                        "CRITICAL: Pool exhaustion imminent. "
                        "Increase pool_size or reduce connection usage."
                    ),
                }
            elif util >= self._config.pool_warning_threshold:
                return {
                    "at_risk": True,
                    "utilization": util,
                    "recommendation": (
                        "WARNING: Pool utilization high. "
                        "Consider increasing pool_size."
                    ),
                }
            else:
                return {
                    "at_risk": False,
                    "utilization": util,
                    "recommendation": "Pool utilization is healthy.",
                }

    def track_long_query(self, query_text: str, user: str = "unknown") -> str:
        """Start tracking a potentially long-running query. Returns query_id."""
        lq = LongRunningQuery(
            query_text=query_text,
            user=user,
        )
        with self._lock:
            self._long_queries[lq.query_id] = lq
        logger.debug("Tracking long query %s", lq.query_id)
        return lq.query_id

    def complete_query(self, query_id: str, duration_ms: float) -> None:
        """Mark a tracked query as complete."""
        with self._lock:
            lq = self._long_queries.get(query_id)
            if lq:
                lq.duration_ms = duration_ms
                lq.state = "completed"
                logger.debug("Query %s completed in %.1fms", query_id, duration_ms)

    def get_long_running(self, threshold_ms: float = 30000) -> List[LongRunningQuery]:
        """Return queries that have been running longer than threshold."""
        now = datetime.now()
        results = []
        with self._lock:
            for lq in self._long_queries.values():
                if lq.state == "active":
                    elapsed = (now - lq.started_at).total_seconds() * 1000
                    lq.duration_ms = elapsed
                    if elapsed >= threshold_ms:
                        results.append(lq)
                elif lq.state == "completed" and lq.duration_ms >= threshold_ms:
                    results.append(lq)
        return results

    def detect_leaks(self) -> List[Dict]:
        """Detect suspected connection leaks from stats patterns.

        A leak is suspected when active connections grow steadily while
        idle connections remain at zero.
        """
        with self._lock:
            if len(self._stats_history) < 5:
                return []

            recent = self._stats_history[-5:]
            active_trend = [s.active for s in recent]
            idle_trend = [s.idle for s in recent]

            # Check for monotonically increasing active with zero idle
            is_growing = all(
                active_trend[i] <= active_trend[i + 1]
                for i in range(len(active_trend) - 1)
            )
            all_idle_zero = all(i == 0 for i in idle_trend)

            if is_growing and all_idle_zero and active_trend[-1] > active_trend[0]:
                leak = {
                    "type": "connection_leak",
                    "description": (
                        f"Active connections grew from {active_trend[0]} to "
                        f"{active_trend[-1]} with no idle connections"
                    ),
                    "active_trend": active_trend,
                    "detected_at": datetime.now().isoformat(),
                }
                return [leak]

            return []

    def report_leak(self, description: str) -> dict:
        """Manually report a suspected connection leak."""
        entry = {
            "type": "manual_report",
            "description": description,
            "reported_at": datetime.now().isoformat(),
        }
        with self._lock:
            self._leaks.append(entry)
        logger.warning("Connection leak reported: %s", description)
        return entry

    def get_pool_health(self) -> dict:
        """Overall connection pool health summary."""
        with self._lock:
            current = self._stats_history[-1] if self._stats_history else None
            util = current.utilization if current else 0.0
            long_running = [
                lq
                for lq in self._long_queries.values()
                if lq.state == "active"
            ]

            if util >= self._config.pool_critical_threshold:
                status = "critical"
            elif util >= self._config.pool_warning_threshold:
                status = "warning"
            else:
                status = "healthy"

            return {
                "status": status,
                "utilization": util,
                "long_running_count": len(long_running),
                "leak_count": len(self._leaks),
            }

    def reset(self) -> None:
        """Clear all monitoring data."""
        with self._lock:
            self._stats_history.clear()
            self._long_queries.clear()
            self._leaks.clear()
