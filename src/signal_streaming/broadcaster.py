"""Signal Broadcaster — pushes updates to WebSocket channels.

Maps aggregated sentiment updates and influencer alerts to
WebSocket message format for real-time client delivery.
"""

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ChannelMapping(enum.Enum):
    """Signal stream channel types (extend existing WebSocket channels)."""

    SENTIMENT = "sentiment"
    INFLUENCER = "influencer"
    SIGNAL = "signal"
    ALERT = "alert"


@dataclass
class BroadcasterConfig:
    """Configuration for signal broadcaster."""

    max_queue_size: int = 500
    batch_size: int = 20
    include_metadata: bool = True
    dedup_window_seconds: float = 5.0  # Suppress duplicate messages


@dataclass
class BroadcastMessage:
    """A message formatted for WebSocket delivery."""

    channel: str = "sentiment"
    message_type: str = "update"
    ticker: str = ""
    data: dict = field(default_factory=dict)
    sequence: int = 0
    timestamp: Optional[datetime] = None

    def to_wire(self) -> dict:
        """Convert to wire format compatible with StreamMessage."""
        return {
            "type": self.message_type,
            "channel": self.channel,
            "data": self.data,
            "sequence": self.sequence,
            "timestamp": (self.timestamp or datetime.now(timezone.utc)).isoformat(),
        }


class SignalBroadcaster:
    """Broadcast signal updates to WebSocket clients.

    Converts AggregatedUpdate and InfluencerAlert objects into
    BroadcastMessage format compatible with the existing WebSocket
    infrastructure.

    Example::

        broadcaster = SignalBroadcaster()
        messages = broadcaster.format_sentiment_updates(updates)
        messages += broadcaster.format_influencer_alerts(alerts)

        for msg in messages:
            # Push to WebSocket ChannelRouter
            channel_router.broadcast(msg.to_wire())
    """

    def __init__(self, config: Optional[BroadcasterConfig] = None):
        self.config = config or BroadcasterConfig()
        self._sequence = 0
        self._queue: list[BroadcastMessage] = []
        self._recent_keys: dict[str, datetime] = {}  # dedup tracking

    def format_sentiment_updates(
        self, updates: list
    ) -> list[BroadcastMessage]:
        """Format aggregated sentiment updates for broadcast.

        Args:
            updates: List of AggregatedUpdate objects.

        Returns:
            List of BroadcastMessage ready for WebSocket delivery.
        """
        messages = []

        for update in updates:
            ticker = getattr(update, "ticker", "")
            dedup_key = f"sentiment:{ticker}"

            if self._is_duplicate(dedup_key):
                continue

            self._sequence += 1

            data = {
                "ticker": ticker,
                "score": round(getattr(update, "score", 0.0), 3),
                "score_change": round(getattr(update, "score_change", 0.0), 3),
                "sentiment": getattr(update, "sentiment", "neutral"),
                "confidence": round(getattr(update, "confidence", 0.0), 3),
                "observation_count": getattr(update, "observation_count", 0),
                "urgency": getattr(update, "urgency", "low"),
            }

            if self.config.include_metadata:
                data["source_types"] = getattr(update, "source_types", [])

            msg = BroadcastMessage(
                channel=ChannelMapping.SENTIMENT.value,
                message_type="update",
                ticker=ticker,
                data=data,
                sequence=self._sequence,
                timestamp=datetime.now(timezone.utc),
            )
            messages.append(msg)
            self._record_send(dedup_key)

        self._enqueue(messages)
        return messages

    def format_influencer_alerts(
        self, alerts: list
    ) -> list[BroadcastMessage]:
        """Format influencer alerts for broadcast.

        Args:
            alerts: List of InfluencerAlert objects.

        Returns:
            List of BroadcastMessage for WebSocket delivery.
        """
        messages = []

        for alert in alerts:
            alert_id = getattr(alert, "alert_id", "")
            dedup_key = f"influencer:{alert_id}"

            if self._is_duplicate(dedup_key):
                continue

            self._sequence += 1

            data = {
                "alert_type": getattr(alert, "alert_type", ""),
                "priority": getattr(alert, "priority", "medium"),
                "author_id": getattr(alert, "author_id", ""),
                "platform": getattr(alert, "platform", ""),
                "tier": getattr(alert, "tier", ""),
                "ticker": getattr(alert, "ticker", ""),
                "sentiment": round(getattr(alert, "sentiment", 0.0), 3),
                "message": getattr(alert, "message", ""),
            }

            # Handle priority as enum
            priority = data["priority"]
            if hasattr(priority, "value"):
                data["priority"] = priority.value

            msg = BroadcastMessage(
                channel=ChannelMapping.INFLUENCER.value,
                message_type="alert",
                ticker=getattr(alert, "ticker", ""),
                data=data,
                sequence=self._sequence,
                timestamp=datetime.now(timezone.utc),
            )
            messages.append(msg)
            self._record_send(dedup_key)

        self._enqueue(messages)
        return messages

    def format_signal(
        self,
        ticker: str,
        signal_type: str,
        direction: str,
        confidence: float,
        source: str = "",
    ) -> BroadcastMessage:
        """Format a generic trading signal for broadcast.

        Args:
            ticker: Stock ticker.
            signal_type: Type of signal (e.g., "ema_cloud", "fusion").
            direction: bullish/bearish/neutral.
            confidence: 0-1 confidence level.
            source: Signal source identifier.

        Returns:
            BroadcastMessage for WebSocket delivery.
        """
        self._sequence += 1

        msg = BroadcastMessage(
            channel=ChannelMapping.SIGNAL.value,
            message_type="signal",
            ticker=ticker,
            data={
                "ticker": ticker,
                "signal_type": signal_type,
                "direction": direction,
                "confidence": round(confidence, 3),
                "source": source,
            },
            sequence=self._sequence,
            timestamp=datetime.now(timezone.utc),
        )
        self._enqueue([msg])
        return msg

    def drain_queue(self, max_items: int = 0) -> list[BroadcastMessage]:
        """Drain the message queue.

        Args:
            max_items: Max messages to drain (0 = all).

        Returns:
            List of BroadcastMessage from the queue.
        """
        if max_items <= 0:
            messages = list(self._queue)
            self._queue.clear()
            return messages

        messages = self._queue[:max_items]
        self._queue[:] = self._queue[max_items:]
        return messages

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def total_sent(self) -> int:
        return self._sequence

    def clear(self):
        """Reset broadcaster state."""
        self._queue.clear()
        self._recent_keys.clear()
        self._sequence = 0

    def _enqueue(self, messages: list[BroadcastMessage]):
        """Add messages to the queue, trimming if needed."""
        self._queue.extend(messages)
        if len(self._queue) > self.config.max_queue_size:
            self._queue[:] = self._queue[-self.config.max_queue_size:]

    def _is_duplicate(self, key: str) -> bool:
        """Check if a message was recently sent."""
        now = datetime.now(timezone.utc)
        last_sent = self._recent_keys.get(key)
        if not last_sent:
            return False
        elapsed = (now - last_sent).total_seconds()
        return elapsed < self.config.dedup_window_seconds

    def _record_send(self, key: str):
        """Record that a message was sent."""
        self._recent_keys[key] = datetime.now(timezone.utc)
