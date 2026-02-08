"""PRD-121: Event-Driven Architecture — Event Bus.

Topic-based publish/subscribe with guaranteed delivery and dead letter queue.
"""

from __future__ import annotations

import fnmatch
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .config import DeliveryStatus, EventBusConfig, SubscriberState
from .schema import EventEnvelope


@dataclass
class Subscriber:
    """A subscriber to one or more topics."""

    subscriber_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str = ""
    topic_pattern: str = "*"
    handler: Optional[Callable[[EventEnvelope], None]] = None
    state: SubscriberState = SubscriberState.ACTIVE
    filter_fn: Optional[Callable[[EventEnvelope], bool]] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    events_received: int = 0
    events_failed: int = 0


@dataclass
class DeliveryRecord:
    """Record of an event delivery attempt."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_id: str = ""
    subscriber_id: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    last_error: Optional[str] = None
    delivered_at: Optional[datetime] = None


class EventBus:
    """Central event bus with topic-based pub/sub."""

    def __init__(self, config: Optional[EventBusConfig] = None) -> None:
        self.config = config or EventBusConfig()
        self._subscribers: dict[str, Subscriber] = {}
        self._delivery_log: list[DeliveryRecord] = []
        self._dead_letters: list[tuple[EventEnvelope, str, str]] = []  # (event, subscriber_id, error)
        self._published_count: int = 0
        self._delivered_count: int = 0

    @property
    def subscribers(self) -> dict[str, Subscriber]:
        return dict(self._subscribers)

    def subscribe(
        self,
        name: str,
        topic_pattern: str,
        handler: Optional[Callable[[EventEnvelope], None]] = None,
        filter_fn: Optional[Callable[[EventEnvelope], bool]] = None,
    ) -> Subscriber:
        """Register a subscriber for a topic pattern."""
        topic_subs = [
            s for s in self._subscribers.values()
            if s.topic_pattern == topic_pattern
        ]
        if len(topic_subs) >= self.config.max_subscribers_per_topic:
            raise ValueError(
                f"Max subscribers ({self.config.max_subscribers_per_topic}) "
                f"reached for pattern '{topic_pattern}'"
            )

        sub = Subscriber(
            name=name,
            topic_pattern=topic_pattern,
            handler=handler,
            filter_fn=filter_fn,
        )
        self._subscribers[sub.subscriber_id] = sub
        return sub

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber."""
        return self._subscribers.pop(subscriber_id, None) is not None

    def publish(self, topic: str, event: EventEnvelope) -> list[DeliveryRecord]:
        """Publish an event to a topic, delivering to all matching subscribers."""
        self._published_count += 1
        records: list[DeliveryRecord] = []

        matching = self._get_matching_subscribers(topic)
        for sub in matching:
            if sub.state != SubscriberState.ACTIVE:
                continue

            if sub.filter_fn is not None:
                try:
                    if not sub.filter_fn(event):
                        continue
                except Exception:
                    continue

            record = self._deliver(event, sub)
            records.append(record)

        return records

    def _get_matching_subscribers(self, topic: str) -> list[Subscriber]:
        """Get all subscribers matching a topic."""
        matching: list[Subscriber] = []
        for sub in self._subscribers.values():
            if fnmatch.fnmatch(topic, sub.topic_pattern) or sub.topic_pattern == "*":
                matching.append(sub)
        return matching

    def _deliver(
        self, event: EventEnvelope, subscriber: Subscriber,
    ) -> DeliveryRecord:
        """Deliver an event to a subscriber with retry."""
        record = DeliveryRecord(
            event_id=event.event_id,
            subscriber_id=subscriber.subscriber_id,
        )

        for attempt in range(1, self.config.max_retry_attempts + 1):
            record.attempts = attempt
            try:
                if subscriber.handler is not None:
                    subscriber.handler(event)
                record.status = DeliveryStatus.DELIVERED
                record.delivered_at = datetime.now(timezone.utc)
                subscriber.events_received += 1
                self._delivered_count += 1
                break
            except Exception as exc:
                record.last_error = str(exc)
                subscriber.events_failed += 1

        if record.status != DeliveryStatus.DELIVERED:
            record.status = DeliveryStatus.FAILED
            if self.config.dead_letter_enabled:
                record.status = DeliveryStatus.DEAD_LETTER
                self._dead_letters.append(
                    (event, subscriber.subscriber_id, record.last_error or "Unknown")
                )

        self._delivery_log.append(record)
        return record

    def pause_subscriber(self, subscriber_id: str) -> bool:
        """Pause a subscriber."""
        sub = self._subscribers.get(subscriber_id)
        if sub is None:
            return False
        sub.state = SubscriberState.PAUSED
        return True

    def resume_subscriber(self, subscriber_id: str) -> bool:
        """Resume a paused subscriber."""
        sub = self._subscribers.get(subscriber_id)
        if sub is None:
            return False
        sub.state = SubscriberState.ACTIVE
        return True

    def get_dead_letters(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get events in the dead letter queue."""
        return [
            {
                "event_id": evt.event_id,
                "event_type": evt.event_type,
                "subscriber_id": sub_id,
                "error": error,
            }
            for evt, sub_id, error in self._dead_letters[-limit:]
        ]

    def clear_dead_letters(self) -> int:
        """Clear the dead letter queue."""
        count = len(self._dead_letters)
        self._dead_letters.clear()
        return count

    def get_delivery_log(
        self,
        event_id: Optional[str] = None,
        subscriber_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[DeliveryRecord]:
        """Get delivery records with optional filters."""
        records = self._delivery_log
        if event_id is not None:
            records = [r for r in records if r.event_id == event_id]
        if subscriber_id is not None:
            records = [r for r in records if r.subscriber_id == subscriber_id]
        return records[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """Get event bus statistics."""
        active_subs = sum(
            1 for s in self._subscribers.values()
            if s.state == SubscriberState.ACTIVE
        )
        return {
            "total_subscribers": len(self._subscribers),
            "active_subscribers": active_subs,
            "total_published": self._published_count,
            "total_delivered": self._delivered_count,
            "dead_letters": len(self._dead_letters),
            "delivery_log_size": len(self._delivery_log),
        }
