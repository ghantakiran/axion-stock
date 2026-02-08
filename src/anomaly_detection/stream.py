"""Stream monitoring for real-time anomaly detection."""

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from .config import (
    AnomalyConfig,
    DetectorConfig,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_EMIT_INTERVAL,
)
from .detector import AnomalyResult, DataPoint, DetectorEngine


@dataclass
class StreamConfig:
    """Configuration for a monitored stream."""

    metric_name: str = ""
    detector_config: DetectorConfig = field(default_factory=DetectorConfig)
    buffer_size: int = DEFAULT_BUFFER_SIZE
    emit_interval: float = DEFAULT_EMIT_INTERVAL


class _StreamState:
    """Internal per-stream runtime state."""

    def __init__(self, config: StreamConfig, stream_id: str):
        self.stream_id = stream_id
        self.config = config
        self.engine = DetectorEngine(
            AnomalyConfig(detectors=[config.detector_config])
        )
        self.anomalies: Deque[AnomalyResult] = deque(maxlen=config.buffer_size)
        self.data_count: int = 0
        self.paused: bool = False
        self.created_at: datetime = datetime.now(timezone.utc)
        self.last_ingest_at: Optional[datetime] = None


class StreamMonitor:
    """Manages multiple real-time anomaly detection streams."""

    def __init__(self):
        self._streams: Dict[str, _StreamState] = {}
        self._metric_to_stream: Dict[str, str] = {}

    def register_stream(self, config: StreamConfig) -> str:
        """Register a new monitoring stream. Returns stream_id."""
        stream_id = uuid.uuid4().hex[:16]
        state = _StreamState(config, stream_id)
        self._streams[stream_id] = state
        self._metric_to_stream[config.metric_name] = stream_id
        return stream_id

    def ingest(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[AnomalyResult]:
        """Ingest a value for a registered metric. Returns AnomalyResult if anomalous."""
        stream_id = self._metric_to_stream.get(metric_name)
        if stream_id is None:
            return None
        state = self._streams[stream_id]
        if state.paused:
            return None

        ts = timestamp or datetime.now(timezone.utc)
        point = DataPoint(timestamp=ts, value=value, metric_name=metric_name)
        state.data_count += 1
        state.last_ingest_at = ts

        result = state.engine.add_data_point(point)
        if result is not None:
            state.anomalies.append(result)
        return result

    def get_stream_status(self, stream_id: str) -> Dict[str, Any]:
        """Return runtime status for a stream."""
        state = self._streams.get(stream_id)
        if state is None:
            return {"error": "stream_not_found"}
        return {
            "stream_id": stream_id,
            "metric_name": state.config.metric_name,
            "data_count": state.data_count,
            "anomaly_count": len(state.anomalies),
            "paused": state.paused,
            "created_at": state.created_at.isoformat(),
            "last_ingest_at": (
                state.last_ingest_at.isoformat() if state.last_ingest_at else None
            ),
        }

    def get_recent_anomalies(
        self, stream_id: str, limit: int = 10
    ) -> List[AnomalyResult]:
        """Return the most recent anomalies for a stream."""
        state = self._streams.get(stream_id)
        if state is None:
            return []
        items = list(state.anomalies)
        return items[-limit:]

    def pause_stream(self, stream_id: str) -> None:
        """Pause anomaly detection on a stream."""
        state = self._streams.get(stream_id)
        if state is not None:
            state.paused = True

    def resume_stream(self, stream_id: str) -> None:
        """Resume anomaly detection on a stream."""
        state = self._streams.get(stream_id)
        if state is not None:
            state.paused = False

    def stream_statistics(self) -> Dict[str, Any]:
        """Return aggregate statistics across all streams."""
        total_streams = len(self._streams)
        active_streams = sum(1 for s in self._streams.values() if not s.paused)
        paused_streams = total_streams - active_streams
        total_data = sum(s.data_count for s in self._streams.values())
        total_anomalies = sum(len(s.anomalies) for s in self._streams.values())
        return {
            "total_streams": total_streams,
            "active_streams": active_streams,
            "paused_streams": paused_streams,
            "total_data_points": total_data,
            "total_anomalies": total_anomalies,
        }
