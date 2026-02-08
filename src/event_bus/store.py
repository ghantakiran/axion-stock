"""PRD-121: Event-Driven Architecture — Event Store.

Immutable append-only event log with replay and snapshot support.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .schema import EventEnvelope


@dataclass
class EventRecord:
    """A persisted event record in the store."""

    sequence_number: int = 0
    event: Optional[EventEnvelope] = None
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None
    stored_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Snapshot:
    """An aggregate state snapshot for fast replay."""

    snapshot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    aggregate_id: str = ""
    aggregate_type: str = ""
    state: dict[str, Any] = field(default_factory=dict)
    sequence_number: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class EventStore:
    """Immutable append-only event store with replay capability."""

    def __init__(self) -> None:
        self._events: list[EventRecord] = []
        self._sequence: int = 0
        self._snapshots: dict[str, Snapshot] = {}  # aggregate_id -> latest snapshot
        self._aggregate_index: dict[str, list[int]] = {}  # aggregate_id -> [sequence_numbers]

    @property
    def size(self) -> int:
        return len(self._events)

    def append(
        self,
        event: EventEnvelope,
        aggregate_id: Optional[str] = None,
        aggregate_type: Optional[str] = None,
    ) -> EventRecord:
        """Append an event to the store (immutable)."""
        self._sequence += 1
        record = EventRecord(
            sequence_number=self._sequence,
            event=event,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
        )
        self._events.append(record)

        if aggregate_id is not None:
            if aggregate_id not in self._aggregate_index:
                self._aggregate_index[aggregate_id] = []
            self._aggregate_index[aggregate_id].append(self._sequence)

        return record

    def get_event(self, sequence_number: int) -> Optional[EventRecord]:
        """Get an event by sequence number."""
        if sequence_number < 1 or sequence_number > len(self._events):
            return None
        return self._events[sequence_number - 1]

    def replay(
        self,
        from_sequence: int = 1,
        to_sequence: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> list[EventRecord]:
        """Replay events from a range with optional type filter."""
        end = to_sequence or self._sequence
        if from_sequence < 1:
            from_sequence = 1

        records = [
            r for r in self._events
            if from_sequence <= r.sequence_number <= end
        ]

        if event_type is not None:
            records = [
                r for r in records
                if r.event is not None and r.event.event_type == event_type
            ]

        return records

    def get_aggregate_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
    ) -> list[EventRecord]:
        """Get all events for an aggregate, optionally after a sequence."""
        sequences = self._aggregate_index.get(aggregate_id, [])
        records = []
        for seq in sequences:
            if seq > from_sequence:
                record = self.get_event(seq)
                if record is not None:
                    records.append(record)
        return records

    def create_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        state: dict[str, Any],
    ) -> Snapshot:
        """Create a snapshot of aggregate state at current sequence."""
        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            state=state,
            sequence_number=self._sequence,
        )
        self._snapshots[aggregate_id] = snapshot
        return snapshot

    def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        """Get the latest snapshot for an aggregate."""
        return self._snapshots.get(aggregate_id)

    def replay_from_snapshot(
        self, aggregate_id: str,
    ) -> tuple[Optional[Snapshot], list[EventRecord]]:
        """Replay from latest snapshot + subsequent events."""
        snapshot = self.get_snapshot(aggregate_id)
        from_seq = snapshot.sequence_number if snapshot else 0
        events = self.get_aggregate_events(aggregate_id, from_seq)
        return snapshot, events

    def get_statistics(self) -> dict[str, Any]:
        """Get event store statistics."""
        type_counts: dict[str, int] = {}
        for record in self._events:
            if record.event is not None:
                et = record.event.event_type
                type_counts[et] = type_counts.get(et, 0) + 1

        return {
            "total_events": len(self._events),
            "current_sequence": self._sequence,
            "aggregates": len(self._aggregate_index),
            "snapshots": len(self._snapshots),
            "event_types": type_counts,
        }
