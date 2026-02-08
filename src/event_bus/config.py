"""PRD-121: Event-Driven Architecture & Message Bus — Configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventPriority(str, Enum):
    """Priority level for events."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DeliveryStatus(str, Enum):
    """Delivery status for an event to a subscriber."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class SubscriberState(str, Enum):
    """State of a subscriber."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class EventCategory(str, Enum):
    """Standard event categories."""

    ORDER = "order"
    TRADE = "trade"
    ALERT = "alert"
    MODEL = "model"
    COMPLIANCE = "compliance"
    SYSTEM = "system"


@dataclass
class EventBusConfig:
    """Configuration for the event bus system."""

    max_subscribers_per_topic: int = 100
    max_retry_attempts: int = 3
    retry_backoff_base_seconds: float = 1.0
    dead_letter_enabled: bool = True
    event_ttl_seconds: int = 86400  # 24 hours
    max_batch_size: int = 100
    consumer_concurrency: int = 4
    checkpoint_interval: int = 10
    max_event_size_bytes: int = 1024 * 1024  # 1MB
    enable_event_dedup: bool = True
