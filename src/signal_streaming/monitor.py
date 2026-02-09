"""Stream Health Monitor.

Tracks streaming pipeline health: throughput, latency,
error rates, and backpressure indicators.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """Configuration for stream monitoring."""

    stats_window_seconds: float = 60.0
    max_latency_ms: float = 1000.0  # Alert if latency exceeds
    min_throughput_per_min: float = 0.0  # Alert if throughput drops
    max_error_rate: float = 0.1  # 10% error threshold


@dataclass
class StreamStats:
    """Point-in-time stream statistics."""

    messages_in: int = 0
    messages_out: int = 0
    messages_filtered: int = 0
    messages_errored: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    throughput_per_min: float = 0.0
    error_rate: float = 0.0
    active_tickers: int = 0
    queue_depth: int = 0
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "messages_in": self.messages_in,
            "messages_out": self.messages_out,
            "messages_filtered": self.messages_filtered,
            "messages_errored": self.messages_errored,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "throughput_per_min": round(self.throughput_per_min, 2),
            "error_rate": round(self.error_rate, 4),
            "active_tickers": self.active_tickers,
            "queue_depth": self.queue_depth,
        }


@dataclass
class StreamHealth:
    """Stream pipeline health assessment."""

    status: str = "healthy"  # healthy, degraded, unhealthy
    issues: list[str] = field(default_factory=list)
    stats: Optional[StreamStats] = None
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": self.issues,
            "stats": self.stats.to_dict() if self.stats else {},
        }

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


class StreamMonitor:
    """Monitor stream pipeline health and performance.

    Tracks message throughput, latency, error rates, and
    generates health assessments.

    Example::

        monitor = StreamMonitor()
        monitor.record_in()
        monitor.record_out(latency_ms=15.0)
        health = monitor.check_health()
        print(health.status)  # "healthy"
    """

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._messages_in = 0
        self._messages_out = 0
        self._messages_filtered = 0
        self._messages_errored = 0
        self._latencies: list[float] = []
        self._window_start = datetime.now(timezone.utc)
        self._active_tickers: set[str] = set()
        self._queue_depth = 0

    def record_in(self, ticker: str = ""):
        """Record an incoming message."""
        self._messages_in += 1
        if ticker:
            self._active_tickers.add(ticker)

    def record_out(self, latency_ms: float = 0.0):
        """Record an outgoing (broadcast) message."""
        self._messages_out += 1
        if latency_ms > 0:
            self._latencies.append(latency_ms)

    def record_filtered(self):
        """Record a filtered (dropped) message."""
        self._messages_filtered += 1

    def record_error(self):
        """Record a processing error."""
        self._messages_errored += 1

    def set_queue_depth(self, depth: int):
        """Update current queue depth."""
        self._queue_depth = depth

    def get_stats(self) -> StreamStats:
        """Get current window statistics."""
        now = datetime.now(timezone.utc)
        elapsed_seconds = max(
            (now - self._window_start).total_seconds(), 1.0
        )

        avg_latency = (
            sum(self._latencies) / len(self._latencies)
            if self._latencies else 0.0
        )
        max_latency = max(self._latencies) if self._latencies else 0.0

        total = self._messages_in
        error_rate = self._messages_errored / total if total > 0 else 0.0

        return StreamStats(
            messages_in=self._messages_in,
            messages_out=self._messages_out,
            messages_filtered=self._messages_filtered,
            messages_errored=self._messages_errored,
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            throughput_per_min=self._messages_out / elapsed_seconds * 60,
            error_rate=error_rate,
            active_tickers=len(self._active_tickers),
            queue_depth=self._queue_depth,
            window_start=self._window_start,
            window_end=now,
        )

    def check_health(self) -> StreamHealth:
        """Assess stream pipeline health.

        Returns:
            StreamHealth with status and any issues detected.
        """
        stats = self.get_stats()
        issues = []

        # Check latency
        if stats.max_latency_ms > self.config.max_latency_ms:
            issues.append(
                f"High latency: {stats.max_latency_ms:.0f}ms "
                f"(max allowed: {self.config.max_latency_ms:.0f}ms)"
            )

        # Check error rate
        if stats.error_rate > self.config.max_error_rate:
            issues.append(
                f"High error rate: {stats.error_rate:.1%} "
                f"(max allowed: {self.config.max_error_rate:.1%})"
            )

        # Check throughput (only if minimum is configured)
        if (
            self.config.min_throughput_per_min > 0
            and stats.throughput_per_min < self.config.min_throughput_per_min
        ):
            issues.append(
                f"Low throughput: {stats.throughput_per_min:.1f}/min "
                f"(min expected: {self.config.min_throughput_per_min:.1f}/min)"
            )

        # Determine status
        if len(issues) >= 2:
            status = "unhealthy"
        elif len(issues) == 1:
            status = "degraded"
        else:
            status = "healthy"

        return StreamHealth(
            status=status,
            issues=issues,
            stats=stats,
            checked_at=datetime.now(timezone.utc),
        )

    def reset(self):
        """Reset all monitoring state."""
        self._messages_in = 0
        self._messages_out = 0
        self._messages_filtered = 0
        self._messages_errored = 0
        self._latencies.clear()
        self._window_start = datetime.now(timezone.utc)
        self._active_tickers.clear()
        self._queue_depth = 0
