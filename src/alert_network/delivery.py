"""Delivery Tracking (PRD-142).

Tracks notification delivery status, supports throttling,
quiet hours, and batched digest delivery.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.alert_network.channels import ChannelKind

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """Delivery attempt status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    THROTTLED = "throttled"
    QUEUED = "queued"


@dataclass
class DeliveryRecord:
    """Record of a notification delivery attempt."""
    delivery_id: str = ""
    channel: ChannelKind = ChannelKind.IN_APP
    status: DeliveryStatus = DeliveryStatus.PENDING
    rule_id: str = ""
    symbol: str = ""
    message: str = ""
    error: str = ""
    attempts: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    delivered_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "delivery_id": self.delivery_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "symbol": self.symbol,
            "message": self.message,
            "attempts": self.attempts,
        }


@dataclass
class DeliveryPreferences:
    """User delivery preferences."""
    user_id: str = "default"
    quiet_hours_enabled: bool = False
    quiet_hours_start: int = 22
    quiet_hours_end: int = 7
    max_per_hour: int = 20
    max_per_day: int = 100
    batch_enabled: bool = False
    batch_interval_minutes: int = 60
    enabled_channels: list = field(default_factory=lambda: [
        ChannelKind.IN_APP, ChannelKind.PUSH, ChannelKind.EMAIL,
    ])

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "quiet_hours": f"{self.quiet_hours_start:02d}:00-{self.quiet_hours_end:02d}:00" if self.quiet_hours_enabled else "disabled",
            "max_per_hour": self.max_per_hour,
            "enabled_channels": [c.value for c in self.enabled_channels],
        }


class DeliveryTracker:
    """Tracks delivery state and enforces throttling.

    Maintains delivery history, respects quiet hours, and
    enforces per-user rate limits.

    Example:
        tracker = DeliveryTracker()
        tracker.set_preferences("user_1", prefs)
        if tracker.can_deliver("user_1"):
            result = await channel.send(payload)
            tracker.record(record)
    """

    def __init__(self):
        self._preferences: dict[str, DeliveryPreferences] = {}
        self._history: list[DeliveryRecord] = []
        self._hourly_counts: dict[str, int] = {}
        self._daily_counts: dict[str, int] = {}
        self._batch_queue: list[DeliveryRecord] = []
        self._last_reset_hour: Optional[int] = None

    def set_preferences(self, user_id: str, prefs: DeliveryPreferences) -> None:
        prefs.user_id = user_id
        self._preferences[user_id] = prefs

    def get_preferences(self, user_id: str) -> DeliveryPreferences:
        return self._preferences.get(user_id, DeliveryPreferences(user_id=user_id))

    def can_deliver(self, user_id: str) -> bool:
        """Check if delivery is allowed right now."""
        self._maybe_reset_counts()
        prefs = self.get_preferences(user_id)

        if prefs.quiet_hours_enabled:
            hour = datetime.now(timezone.utc).hour
            if self._in_quiet_hours(hour, prefs.quiet_hours_start, prefs.quiet_hours_end):
                return False

        if self._hourly_counts.get(user_id, 0) >= prefs.max_per_hour:
            return False

        if self._daily_counts.get(user_id, 0) >= prefs.max_per_day:
            return False

        return True

    def record(self, record: DeliveryRecord, user_id: str = "default") -> None:
        """Record a delivery attempt."""
        self._history.append(record)
        if record.status == DeliveryStatus.SENT:
            self._hourly_counts[user_id] = self._hourly_counts.get(user_id, 0) + 1
            self._daily_counts[user_id] = self._daily_counts.get(user_id, 0) + 1

    def get_history(self, limit: int = 50) -> list[DeliveryRecord]:
        """Get recent delivery history."""
        return self._history[-limit:]

    def get_stats(self) -> dict:
        """Get delivery statistics."""
        total = len(self._history)
        sent = sum(1 for r in self._history if r.status == DeliveryStatus.SENT)
        failed = sum(1 for r in self._history if r.status == DeliveryStatus.FAILED)
        return {
            "total_deliveries": total,
            "sent": sent,
            "failed": failed,
            "success_rate": sent / total if total > 0 else 0.0,
        }

    def queue_for_batch(self, record: DeliveryRecord) -> None:
        """Queue a notification for batch digest delivery."""
        self._batch_queue.append(record)

    def flush_batch(self) -> list[DeliveryRecord]:
        """Get and clear the batch queue."""
        batch = list(self._batch_queue)
        self._batch_queue.clear()
        return batch

    def _in_quiet_hours(self, hour: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end

    def _maybe_reset_counts(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_reset_hour is None or now.hour != self._last_reset_hour:
            self._hourly_counts.clear()
            self._last_reset_hour = now.hour
