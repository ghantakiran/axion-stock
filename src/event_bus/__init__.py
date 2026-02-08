"""PRD-121: Event-Driven Architecture & Message Bus."""

from .config import (
    EventPriority,
    DeliveryStatus,
    SubscriberState,
    EventCategory,
    EventBusConfig,
)
from .schema import (
    EventEnvelope,
    SchemaDefinition,
    SchemaRegistry,
    order_executed_event,
    alert_triggered_event,
    model_updated_event,
    compliance_violation_event,
)
from .bus import Subscriber, DeliveryRecord, EventBus
from .store import EventRecord, Snapshot, EventStore
from .consumer import ConsumerCheckpoint, ConsumerGroup, AsyncConsumer

__all__ = [
    # Config
    "EventPriority",
    "DeliveryStatus",
    "SubscriberState",
    "EventCategory",
    "EventBusConfig",
    # Schema
    "EventEnvelope",
    "SchemaDefinition",
    "SchemaRegistry",
    "order_executed_event",
    "alert_triggered_event",
    "model_updated_event",
    "compliance_violation_event",
    # Bus
    "Subscriber",
    "DeliveryRecord",
    "EventBus",
    # Store
    "EventRecord",
    "Snapshot",
    "EventStore",
    # Consumer
    "ConsumerCheckpoint",
    "ConsumerGroup",
    "AsyncConsumer",
]
