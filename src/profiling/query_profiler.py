"""Query profiling and fingerprinting engine."""

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.profiling.config import ProfilingConfig, QuerySeverity

logger = logging.getLogger(__name__)


@dataclass
class QueryFingerprint:
    """Aggregated statistics for a normalized query pattern."""

    fingerprint: str
    query_template: str
    call_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    durations: List[float] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    severity: QuerySeverity = QuerySeverity.NORMAL

    @property
    def avg_duration_ms(self) -> float:
        """Average query duration in milliseconds."""
        if self.call_count == 0:
            return 0.0
        return self.total_duration_ms / self.call_count

    @property
    def p95_duration_ms(self) -> float:
        """95th percentile duration in milliseconds."""
        if not self.durations:
            return 0.0
        sorted_d = sorted(self.durations)
        idx = int(len(sorted_d) * 0.95)
        idx = min(idx, len(sorted_d) - 1)
        return sorted_d[idx]

    @property
    def p99_duration_ms(self) -> float:
        """99th percentile duration in milliseconds."""
        if not self.durations:
            return 0.0
        sorted_d = sorted(self.durations)
        idx = int(len(sorted_d) * 0.99)
        idx = min(idx, len(sorted_d) - 1)
        return sorted_d[idx]


class QueryProfiler:
    """Profiles SQL queries and tracks performance fingerprints."""

    def __init__(self, config: Optional[ProfilingConfig] = None):
        self._config = config or ProfilingConfig()
        self._fingerprints: Dict[str, QueryFingerprint] = {}
        self._lock = threading.Lock()

    def record_query(
        self, query_text: str, duration_ms: float, params: Optional[dict] = None
    ) -> QueryFingerprint:
        """Record a query execution and update its fingerprint stats."""
        normalized = self._normalize_query(query_text)
        fp_hash = hashlib.md5(normalized.encode()).hexdigest()

        with self._lock:
            if fp_hash not in self._fingerprints:
                self._fingerprints[fp_hash] = QueryFingerprint(
                    fingerprint=fp_hash,
                    query_template=normalized,
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                )

            fp = self._fingerprints[fp_hash]
            fp.call_count += 1
            fp.total_duration_ms += duration_ms
            fp.min_duration_ms = min(fp.min_duration_ms, duration_ms)
            fp.max_duration_ms = max(fp.max_duration_ms, duration_ms)
            fp.last_seen = datetime.now()

            # Keep durations bounded
            if len(fp.durations) < self._config.max_query_history:
                fp.durations.append(duration_ms)
            else:
                # Rotate: drop oldest
                fp.durations.pop(0)
                fp.durations.append(duration_ms)

            # Classify severity
            if duration_ms >= self._config.critical_query_threshold_ms:
                fp.severity = QuerySeverity.CRITICAL
            elif duration_ms >= self._config.slow_query_threshold_ms:
                if fp.severity != QuerySeverity.CRITICAL:
                    fp.severity = QuerySeverity.SLOW

            return fp

    def get_slow_queries(
        self, threshold_ms: Optional[float] = None
    ) -> List[QueryFingerprint]:
        """Return fingerprints where average duration exceeds threshold."""
        threshold = threshold_ms or self._config.slow_query_threshold_ms
        with self._lock:
            return [
                fp
                for fp in self._fingerprints.values()
                if fp.avg_duration_ms >= threshold
            ]

    def get_top_queries(
        self, n: int = 10, sort_by: str = "total_duration"
    ) -> List[QueryFingerprint]:
        """Return top N queries by total duration or call count."""
        with self._lock:
            fps = list(self._fingerprints.values())

        if sort_by == "call_count":
            fps.sort(key=lambda f: f.call_count, reverse=True)
        elif sort_by == "avg_duration":
            fps.sort(key=lambda f: f.avg_duration_ms, reverse=True)
        elif sort_by == "max_duration":
            fps.sort(key=lambda f: f.max_duration_ms, reverse=True)
        else:  # total_duration
            fps.sort(key=lambda f: f.total_duration_ms, reverse=True)

        return fps[:n]

    def get_fingerprint(self, fingerprint: str) -> Optional[QueryFingerprint]:
        """Get a specific fingerprint by hash."""
        with self._lock:
            return self._fingerprints.get(fingerprint)

    def get_query_stats(self) -> dict:
        """Aggregate statistics across all tracked queries."""
        with self._lock:
            total_queries = sum(fp.call_count for fp in self._fingerprints.values())
            total_duration = sum(
                fp.total_duration_ms for fp in self._fingerprints.values()
            )
            unique_fingerprints = len(self._fingerprints)

            avg_duration = total_duration / total_queries if total_queries > 0 else 0.0

            return {
                "total_queries": total_queries,
                "unique_fingerprints": unique_fingerprints,
                "total_duration_ms": total_duration,
                "avg_duration_ms": avg_duration,
            }

    def detect_regressions(self, window_size: int = 10) -> List[QueryFingerprint]:
        """Find fingerprints where recent performance regressed vs historical.

        A regression is detected when the average of the last `window_size`
        executions is more than 2x the overall historical average.
        """
        regressions = []
        with self._lock:
            for fp in self._fingerprints.values():
                if len(fp.durations) < window_size * 2:
                    continue

                recent = fp.durations[-window_size:]
                historical = fp.durations[:-window_size]

                recent_avg = sum(recent) / len(recent)
                hist_avg = sum(historical) / len(historical)

                if hist_avg > 0 and recent_avg > 2.0 * hist_avg:
                    regressions.append(fp)

        return regressions

    def _normalize_query(self, query: str) -> str:
        """Replace string and numeric literals with '?' placeholders."""
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", query.strip())
        # Replace quoted strings
        normalized = re.sub(r"'[^']*'", "?", normalized)
        normalized = re.sub(r'"[^"]*"', "?", normalized)
        # Replace numeric literals (integers and floats)
        normalized = re.sub(r"\b\d+\.?\d*\b", "?", normalized)
        return normalized

    def reset(self) -> None:
        """Clear all profiling data."""
        with self._lock:
            self._fingerprints.clear()
