"""PRD-121: Event-Driven Architecture — Async Consumer.

Background worker pool for async event processing with retry and checkpointing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .config import EventBusConfig
from .schema import EventEnvelope
from .store import EventStore


@dataclass
class ConsumerCheckpoint:
    """Checkpoint tracking consumer progress."""

    consumer_id: str = ""
    topic: str = ""
    last_sequence: int = 0
    events_processed: int = 0
    events_failed: int = 0
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ConsumerGroup:
    """A group of consumers competing to process events."""

    group_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    topic: str = ""
    handler: Optional[Callable[[EventEnvelope], None]] = None
    members: list[str] = field(default_factory=list)
    checkpoint: Optional[ConsumerCheckpoint] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    active: bool = True


class AsyncConsumer:
    """Async consumer with checkpoint-based progress tracking."""

    def __init__(
        self,
        store: EventStore,
        config: Optional[EventBusConfig] = None,
    ) -> None:
        self.store = store
        self.config = config or EventBusConfig()
        self._groups: dict[str, ConsumerGroup] = {}
        self._checkpoints: dict[str, ConsumerCheckpoint] = {}  # consumer_id -> checkpoint
        self._processing_errors: list[dict[str, Any]] = []

    def create_group(
        self,
        name: str,
        topic: str,
        handler: Optional[Callable[[EventEnvelope], None]] = None,
    ) -> ConsumerGroup:
        """Create a consumer group for a topic."""
        group = ConsumerGroup(name=name, topic=topic, handler=handler)
        self._groups[group.group_id] = group
        # Initialize checkpoint
        group.checkpoint = ConsumerCheckpoint(
            consumer_id=group.group_id,
            topic=topic,
        )
        self._checkpoints[group.group_id] = group.checkpoint
        return group

    def add_member(self, group_id: str, member_id: str) -> bool:
        """Add a member to a consumer group."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        if member_id not in group.members:
            group.members.append(member_id)
        return True

    def remove_member(self, group_id: str, member_id: str) -> bool:
        """Remove a member from a consumer group."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        if member_id in group.members:
            group.members.remove(member_id)
            return True
        return False

    def consume(
        self,
        group_id: str,
        max_events: Optional[int] = None,
    ) -> dict[str, Any]:
        """Consume events from the store for a consumer group."""
        group = self._groups.get(group_id)
        if group is None:
            return {"processed": 0, "failed": 0, "error": "Group not found"}

        if not group.active:
            return {"processed": 0, "failed": 0, "error": "Group is inactive"}

        checkpoint = group.checkpoint
        if checkpoint is None:
            return {"processed": 0, "failed": 0, "error": "No checkpoint"}

        batch_size = max_events or self.config.max_batch_size
        events = self.store.replay(
            from_sequence=checkpoint.last_sequence + 1,
        )

        # Filter by topic if specified
        if group.topic != "*":
            events = [
                e for e in events
                if e.event is not None
                and (e.event.event_type == group.topic or group.topic == "*")
            ]

        events = events[:batch_size]
        processed = 0
        failed = 0

        for record in events:
            if record.event is None:
                continue
            try:
                if group.handler is not None:
                    group.handler(record.event)
                processed += 1
                checkpoint.events_processed += 1
            except Exception as exc:
                failed += 1
                checkpoint.events_failed += 1
                self._processing_errors.append({
                    "group_id": group_id,
                    "sequence": record.sequence_number,
                    "event_id": record.event.event_id,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            checkpoint.last_sequence = record.sequence_number

        checkpoint.last_updated = datetime.now(timezone.utc)
        return {"processed": processed, "failed": failed}

    def get_checkpoint(self, group_id: str) -> Optional[ConsumerCheckpoint]:
        """Get the checkpoint for a consumer group."""
        return self._checkpoints.get(group_id)

    def reset_checkpoint(self, group_id: str, sequence: int = 0) -> bool:
        """Reset a consumer group's checkpoint to a specific sequence."""
        checkpoint = self._checkpoints.get(group_id)
        if checkpoint is None:
            return False
        checkpoint.last_sequence = sequence
        checkpoint.last_updated = datetime.now(timezone.utc)
        return True

    def pause_group(self, group_id: str) -> bool:
        """Pause a consumer group."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        group.active = False
        return True

    def resume_group(self, group_id: str) -> bool:
        """Resume a consumer group."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        group.active = True
        return True

    def get_group(self, group_id: str) -> Optional[ConsumerGroup]:
        """Get a consumer group by ID."""
        return self._groups.get(group_id)

    def list_groups(self) -> list[ConsumerGroup]:
        """List all consumer groups."""
        return list(self._groups.values())

    def get_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get processing errors."""
        return self._processing_errors[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get consumer statistics."""
        total_processed = sum(
            c.events_processed for c in self._checkpoints.values()
        )
        total_failed = sum(
            c.events_failed for c in self._checkpoints.values()
        )
        return {
            "total_groups": len(self._groups),
            "active_groups": sum(1 for g in self._groups.values() if g.active),
            "total_processed": total_processed,
            "total_failed": total_failed,
            "total_errors": len(self._processing_errors),
        }
