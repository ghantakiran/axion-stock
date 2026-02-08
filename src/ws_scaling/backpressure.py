"""Backpressure handling for WebSocket message queues."""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import DropStrategy, MessagePriority, WSScalingConfig
from .router import Message

logger = logging.getLogger(__name__)


@dataclass
class QueueStats:
    """Per-connection queue statistics."""

    connection_id: str = ""
    queue_depth: int = 0
    oldest_message_age_ms: float = 0.0
    messages_dropped: int = 0
    is_slow: bool = False


class BackpressureHandler:
    """Manages per-connection message queues with backpressure, slow-consumer
    detection, and configurable drop strategies.
    """

    def __init__(self, config: Optional[WSScalingConfig] = None):
        self._config = config or WSScalingConfig()
        self._queues: Dict[str, List[Message]] = {}
        self._stats: Dict[str, QueueStats] = {}
        self._lock = threading.Lock()

    def _ensure_connection(self, connection_id: str) -> None:
        """Lazily initialise queue and stats for a connection."""
        if connection_id not in self._queues:
            self._queues[connection_id] = []
        if connection_id not in self._stats:
            self._stats[connection_id] = QueueStats(connection_id=connection_id)

    def enqueue(self, connection_id: str, message: Message) -> bool:
        """Add a message to the connection's outbound queue.

        Returns True if the message was accepted, False if the queue is full
        and the message had to be dropped.
        """
        with self._lock:
            self._ensure_connection(connection_id)
            queue = self._queues[connection_id]
            stats = self._stats[connection_id]

            # Apply backpressure when queue exceeds buffer size
            if len(queue) >= self._config.message_buffer_size:
                stats.messages_dropped += 1
                logger.warning(
                    "Queue full for %s (%d msgs), dropping message %s",
                    connection_id,
                    len(queue),
                    message.message_id,
                )
                return False

            queue.append(message)
            stats.queue_depth = len(queue)

            # Update oldest-message age
            if queue:
                age_ms = (time.time() - queue[0].timestamp.timestamp()) * 1000
                stats.oldest_message_age_ms = max(age_ms, 0.0)

            # Mark slow if over backpressure threshold
            if len(queue) >= self._config.backpressure_threshold:
                stats.is_slow = True

            return True

    def dequeue(self, connection_id: str, count: int = 1) -> List[Message]:
        """Pop up to *count* messages from the front of the queue."""
        with self._lock:
            self._ensure_connection(connection_id)
            queue = self._queues[connection_id]
            stats = self._stats[connection_id]

            result = queue[:count]
            del queue[:count]

            stats.queue_depth = len(queue)
            if queue:
                age_ms = (time.time() - queue[0].timestamp.timestamp()) * 1000
                stats.oldest_message_age_ms = max(age_ms, 0.0)
            else:
                stats.oldest_message_age_ms = 0.0
                stats.is_slow = False

            return result

    def get_queue_depth(self, connection_id: str) -> int:
        """Current number of queued messages for a connection."""
        return len(self._queues.get(connection_id, []))

    def detect_slow_consumers(self) -> List[str]:
        """Return connection IDs whose queue depth exceeds the backpressure threshold."""
        slow: List[str] = []
        for cid, queue in self._queues.items():
            if len(queue) >= self._config.backpressure_threshold:
                slow.append(cid)
                if cid in self._stats:
                    self._stats[cid].is_slow = True
        return slow

    def drop_messages(
        self,
        connection_id: str,
        strategy: DropStrategy,
        count: Optional[int] = None,
    ) -> int:
        """Drop messages from a connection's queue per the given strategy.

        If *count* is None, drops messages until the queue is back under the
        backpressure threshold.  Returns the number of messages dropped.
        """
        with self._lock:
            self._ensure_connection(connection_id)
            queue = self._queues[connection_id]
            stats = self._stats[connection_id]

            if not queue:
                return 0

            to_drop = count if count is not None else max(
                0, len(queue) - self._config.backpressure_threshold + 1
            )
            to_drop = min(to_drop, len(queue))

            if to_drop <= 0:
                return 0

            if strategy == DropStrategy.OLDEST_FIRST:
                del queue[:to_drop]
            elif strategy == DropStrategy.LOWEST_PRIORITY:
                # Sort by priority (LOW > NORMAL > HIGH > CRITICAL → drop lowest first)
                priority_order = {
                    MessagePriority.LOW: 0,
                    MessagePriority.NORMAL: 1,
                    MessagePriority.HIGH: 2,
                    MessagePriority.CRITICAL: 3,
                }
                queue.sort(key=lambda m: priority_order.get(m.priority, 1))
                del queue[:to_drop]
            elif strategy == DropStrategy.RANDOM:
                indices = random.sample(range(len(queue)), to_drop)
                for idx in sorted(indices, reverse=True):
                    del queue[idx]

            stats.messages_dropped += to_drop
            stats.queue_depth = len(queue)

            if queue:
                age_ms = (time.time() - queue[0].timestamp.timestamp()) * 1000
                stats.oldest_message_age_ms = max(age_ms, 0.0)
            else:
                stats.oldest_message_age_ms = 0.0
                stats.is_slow = False

            logger.info(
                "Dropped %d messages for %s using strategy=%s",
                to_drop,
                connection_id,
                strategy.value,
            )
            return to_drop

    def get_queue_stats(self, connection_id: str) -> QueueStats:
        """Return queue statistics for a single connection."""
        self._ensure_connection(connection_id)
        stats = self._stats[connection_id]
        stats.queue_depth = len(self._queues.get(connection_id, []))
        return stats

    def get_all_stats(self) -> Dict[str, QueueStats]:
        """Return queue statistics for every tracked connection."""
        for cid in list(self._stats):
            self._stats[cid].queue_depth = len(self._queues.get(cid, []))
        return dict(self._stats)

    def get_total_queued(self) -> int:
        """Total messages queued across all connections."""
        return sum(len(q) for q in self._queues.values())

    def reset(self) -> None:
        """Clear all queues and statistics."""
        with self._lock:
            self._queues.clear()
            self._stats.clear()
