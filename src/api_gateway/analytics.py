"""API analytics: per-endpoint stats, latency percentiles, top-user tracking."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EndpointStats:
    """Accumulated statistics for one endpoint (path + method)."""

    path: str = ""
    method: str = ""
    total_requests: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    status_codes: Dict[int, int] = field(default_factory=dict)
    latencies: List[float] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    def _percentile(self, pct: int) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * pct / 100)
        idx = min(idx, len(sorted_lat) - 1)
        return sorted_lat[idx]


class APIAnalytics:
    """Collects and reports on API usage analytics."""

    def __init__(self) -> None:
        self._stats: Dict[str, EndpointStats] = {}
        self._user_stats: Dict[str, int] = {}
        self._lock = threading.Lock()

    # ── recording ────────────────────────────────────────────────────

    def record_request(
        self,
        path: str,
        method: str,
        status_code: int,
        latency_ms: float,
        user_id: Optional[str] = None,
    ) -> None:
        """Record a single request for analytics."""
        with self._lock:
            key = f"{path}:{method}"
            if key not in self._stats:
                self._stats[key] = EndpointStats(path=path, method=method)
            stats = self._stats[key]
            stats.total_requests += 1
            stats.total_latency_ms += latency_ms
            stats.latencies.append(latency_ms)
            stats.status_codes[status_code] = stats.status_codes.get(status_code, 0) + 1
            if status_code >= 400:
                stats.error_count += 1
            if user_id:
                self._user_stats[user_id] = self._user_stats.get(user_id, 0) + 1
            logger.debug("Recorded %s %s -> %d (%.1f ms)", method, path, status_code, latency_ms)

    # ── queries ──────────────────────────────────────────────────────

    def get_endpoint_stats(self, path: str, method: str) -> Optional[EndpointStats]:
        """Return stats for a specific endpoint."""
        with self._lock:
            return self._stats.get(f"{path}:{method}")

    def get_all_stats(self) -> Dict[str, EndpointStats]:
        """Return all endpoint stats."""
        with self._lock:
            return dict(self._stats)

    def get_top_endpoints(self, n: int = 10) -> List[EndpointStats]:
        """Return top-n endpoints by total request count."""
        with self._lock:
            return sorted(
                self._stats.values(),
                key=lambda s: s.total_requests,
                reverse=True,
            )[:n]

    def get_top_users(self, n: int = 10) -> List[Dict]:
        """Return top-n users by request count."""
        with self._lock:
            sorted_users = sorted(
                self._user_stats.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:n]
            return [{"user_id": uid, "requests": cnt} for uid, cnt in sorted_users]

    def get_error_endpoints(self) -> List[EndpointStats]:
        """Return endpoints whose error rate exceeds 5 %."""
        with self._lock:
            return [s for s in self._stats.values() if s.error_rate > 0.05]

    def get_summary(self) -> Dict:
        """Produce an aggregate summary across all endpoints."""
        with self._lock:
            total_requests = sum(s.total_requests for s in self._stats.values())
            total_latency = sum(s.total_latency_ms for s in self._stats.values())
            total_errors = sum(s.error_count for s in self._stats.values())
            return {
                "total_requests": total_requests,
                "total_endpoints": len(self._stats),
                "avg_latency_ms": (total_latency / total_requests) if total_requests else 0.0,
                "error_rate": (total_errors / total_requests) if total_requests else 0.0,
                "total_errors": total_errors,
                "total_users": len(self._user_stats),
            }

    def reset(self) -> None:
        """Clear all analytics data."""
        with self._lock:
            self._stats.clear()
            self._user_stats.clear()
            logger.info("Analytics data reset")
