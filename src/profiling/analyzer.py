"""Performance analysis, N+1 detection, and snapshot comparison."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Point-in-time capture of system performance metrics."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    endpoint_stats: Dict = field(default_factory=dict)
    query_stats: Dict = field(default_factory=dict)
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    active_connections: int = 0


class PerformanceAnalyzer:
    """Analyzes performance snapshots and detects N+1 query patterns."""

    def __init__(self):
        self._snapshots: List[PerformanceSnapshot] = []
        self._n1_detections: List[Dict] = []
        self._lock = threading.Lock()

    def take_snapshot(
        self,
        endpoint_stats: Optional[Dict] = None,
        query_stats: Optional[Dict] = None,
        memory_mb: float = 0.0,
        cpu_pct: float = 0.0,
        connections: int = 0,
    ) -> PerformanceSnapshot:
        """Create and store a performance snapshot."""
        snap = PerformanceSnapshot(
            endpoint_stats=endpoint_stats or {},
            query_stats=query_stats or {},
            memory_usage_mb=memory_mb,
            cpu_percent=cpu_pct,
            active_connections=connections,
        )
        with self._lock:
            self._snapshots.append(snap)
        logger.info("Performance snapshot %s captured", snap.snapshot_id)
        return snap

    def detect_n1_queries(self, queries_log: List[Dict]) -> List[Dict]:
        """Detect N+1 query patterns in a log of query executions.

        Looks for the same query template executing more than 5 times
        within a 100ms window, which suggests an N+1 pattern.

        Each entry in queries_log should have:
            - template: str (normalized query)
            - timestamp_ms: float (epoch ms or relative ms offset)
        """
        if not queries_log:
            return []

        # Group by template
        by_template: Dict[str, List[float]] = {}
        for entry in queries_log:
            tmpl = entry.get("template", "")
            ts = entry.get("timestamp_ms", 0.0)
            by_template.setdefault(tmpl, []).append(ts)

        detections = []
        for template, timestamps in by_template.items():
            timestamps.sort()
            # Sliding window: check for >5 executions within 100ms
            for i in range(len(timestamps)):
                window_end = timestamps[i] + 100.0
                count = 0
                for j in range(i, len(timestamps)):
                    if timestamps[j] <= window_end:
                        count += 1
                    else:
                        break
                if count > 5:
                    detection = {
                        "template": template,
                        "count_in_window": count,
                        "window_start_ms": timestamps[i],
                        "window_end_ms": window_end,
                        "detected_at": datetime.now().isoformat(),
                    }
                    detections.append(detection)
                    break  # One detection per template is enough

        with self._lock:
            self._n1_detections.extend(detections)

        if detections:
            logger.warning("Detected %d N+1 query patterns", len(detections))

        return detections

    def compare_snapshots(self, a_id: str, b_id: str) -> Dict:
        """Compare two snapshots and report metric changes."""
        snap_a = None
        snap_b = None

        with self._lock:
            for s in self._snapshots:
                if s.snapshot_id == a_id:
                    snap_a = s
                if s.snapshot_id == b_id:
                    snap_b = s

        if snap_a is None or snap_b is None:
            return {"error": "One or both snapshot IDs not found"}

        return {
            "snapshot_a": a_id,
            "snapshot_b": b_id,
            "memory_change_mb": snap_b.memory_usage_mb - snap_a.memory_usage_mb,
            "cpu_change_pct": snap_b.cpu_percent - snap_a.cpu_percent,
            "connection_change": snap_b.active_connections - snap_a.active_connections,
            "time_delta_seconds": (
                snap_b.timestamp - snap_a.timestamp
            ).total_seconds(),
        }

    def get_snapshots(self, limit: int = 10) -> List[PerformanceSnapshot]:
        """Return recent snapshots, most recent first."""
        with self._lock:
            return list(reversed(self._snapshots[-limit:]))

    def get_memory_trend(self) -> List[float]:
        """Extract memory usage values from snapshot history."""
        with self._lock:
            return [s.memory_usage_mb for s in self._snapshots]

    def get_n1_detections(self) -> List[Dict]:
        """Return all N+1 query detections."""
        with self._lock:
            return list(self._n1_detections)

    def reset(self) -> None:
        """Clear all analysis data."""
        with self._lock:
            self._snapshots.clear()
            self._n1_detections.clear()
