"""Anomaly lifecycle management: recording, tracking, and investigation."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .config import AnomalySeverity, AnomalyStatus
from .detector import AnomalyResult


@dataclass
class AnomalyRecord:
    """Persistent record tracking an anomaly through its lifecycle."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    anomaly_result: Optional[AnomalyResult] = None
    status: AnomalyStatus = AnomalyStatus.DETECTED
    assigned_to: Optional[str] = None
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class AnomalyManager:
    """Manages the lifecycle of detected anomalies."""

    def __init__(self):
        self._records: Dict[str, AnomalyRecord] = {}

    def record_anomaly(self, result: AnomalyResult) -> AnomalyRecord:
        """Create a new AnomalyRecord from a detection result."""
        record = AnomalyRecord(anomaly_result=result)
        self._records[record.record_id] = record
        return record

    def update_status(
        self,
        record_id: str,
        status: AnomalyStatus,
        notes: str = "",
    ) -> AnomalyRecord:
        """Update the status and notes on an anomaly record."""
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(f"Record not found: {record_id}")
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        if notes:
            record.notes = notes
        if status == AnomalyStatus.RESOLVED:
            record.resolved_at = datetime.now(timezone.utc)
        return record

    def get_open_anomalies(self) -> List[AnomalyRecord]:
        """Return all anomalies that are not resolved or marked false positive."""
        closed = {AnomalyStatus.RESOLVED, AnomalyStatus.FALSE_POSITIVE}
        return [r for r in self._records.values() if r.status not in closed]

    def mark_false_positive(
        self, record_id: str, reason: str = ""
    ) -> AnomalyRecord:
        """Mark an anomaly as a false positive with an optional reason."""
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(f"Record not found: {record_id}")
        record.status = AnomalyStatus.FALSE_POSITIVE
        record.updated_at = datetime.now(timezone.utc)
        record.resolved_at = datetime.now(timezone.utc)
        if reason:
            record.notes = reason
        return record

    def anomaly_statistics(self, period: Optional[timedelta] = None) -> Dict[str, Any]:
        """Compute statistics over anomalies, optionally filtered by period."""
        now = datetime.now(timezone.utc)
        records = list(self._records.values())
        if period is not None:
            cutoff = now - period
            records = [r for r in records if r.created_at >= cutoff]

        total = len(records)
        open_count = sum(
            1
            for r in records
            if r.status not in {AnomalyStatus.RESOLVED, AnomalyStatus.FALSE_POSITIVE}
        )
        resolved = sum(1 for r in records if r.status == AnomalyStatus.RESOLVED)
        false_pos = sum(1 for r in records if r.status == AnomalyStatus.FALSE_POSITIVE)
        return {
            "total": total,
            "open": open_count,
            "resolved": resolved,
            "false_positives": false_pos,
        }

    def severity_distribution(self) -> Dict[str, int]:
        """Return counts of anomalies grouped by severity."""
        dist: Dict[str, int] = defaultdict(int)
        for record in self._records.values():
            if record.anomaly_result:
                dist[record.anomaly_result.severity.value] += 1
        return dict(dist)

    def top_anomalous_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the top metrics by anomaly count."""
        counts: Dict[str, int] = defaultdict(int)
        for record in self._records.values():
            if record.anomaly_result and record.anomaly_result.data_point:
                metric = record.anomaly_result.data_point.metric_name
                counts[metric] += 1
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"metric_name": name, "anomaly_count": count}
            for name, count in sorted_items[:limit]
        ]
