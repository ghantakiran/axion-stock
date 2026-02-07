"""Notification queue management."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict
import heapq

from src.notifications.config import (
    NotificationConfig,
    NotificationStatus,
    NotificationPriority,
    NotificationCategory,
    DEFAULT_NOTIFICATION_CONFIG,
)
from src.notifications.models import Notification, NotificationResult


class NotificationQueue:
    """Priority queue for notification delivery."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or DEFAULT_NOTIFICATION_CONFIG
        # Priority queue: (priority_score, timestamp, notification)
        self._queue: list[tuple[int, float, Notification]] = []
        # Notification lookup by ID
        self._notifications: dict[str, Notification] = {}
        # Failed notifications for retry
        self._retry_queue: dict[str, int] = {}  # notification_id -> retry_count
        # Dead letter queue
        self._dead_letter: list[Notification] = []

    def _priority_score(self, notification: Notification) -> int:
        """Calculate priority score (lower = higher priority)."""
        scores = {
            NotificationPriority.URGENT: 0,
            NotificationPriority.HIGH: 1,
            NotificationPriority.NORMAL: 2,
            NotificationPriority.LOW: 3,
        }
        return scores.get(notification.priority, 2)

    def enqueue(self, notification: Notification) -> bool:
        """Add notification to queue."""
        if notification.notification_id in self._notifications:
            return False

        notification.status = NotificationStatus.QUEUED

        # Calculate when to send
        send_time = notification.scheduled_at or datetime.now(timezone.utc)
        timestamp = send_time.timestamp()

        # Add to priority queue
        priority_score = self._priority_score(notification)
        heapq.heappush(self._queue, (priority_score, timestamp, notification))

        # Store for lookup
        self._notifications[notification.notification_id] = notification

        return True

    def dequeue(self) -> Optional[Notification]:
        """Get next notification to send."""
        now = datetime.now(timezone.utc).timestamp()

        while self._queue:
            priority, timestamp, notification = heapq.heappop(self._queue)

            # Check if it's time to send
            if timestamp > now:
                # Put it back, not ready yet
                heapq.heappush(self._queue, (priority, timestamp, notification))
                return None

            # Check if expired
            if notification.is_expired():
                notification.status = NotificationStatus.EXPIRED
                del self._notifications[notification.notification_id]
                continue

            # Check if already processed
            if notification.notification_id not in self._notifications:
                continue

            notification.status = NotificationStatus.SENDING
            return notification

        return None

    def get_batch(self, max_size: int = 100) -> list[Notification]:
        """Get a batch of notifications ready to send."""
        batch = []
        now = datetime.now(timezone.utc).timestamp()

        while len(batch) < max_size and self._queue:
            priority, timestamp, notification = self._queue[0]

            # Check if ready
            if timestamp > now:
                break

            heapq.heappop(self._queue)

            # Skip expired
            if notification.is_expired():
                notification.status = NotificationStatus.EXPIRED
                if notification.notification_id in self._notifications:
                    del self._notifications[notification.notification_id]
                continue

            # Skip already processed
            if notification.notification_id not in self._notifications:
                continue

            notification.status = NotificationStatus.SENDING
            batch.append(notification)

        return batch

    def mark_success(self, notification_id: str) -> bool:
        """Mark notification as successfully sent."""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.mark_sent()
        del self._notifications[notification_id]

        # Remove from retry queue if present
        if notification_id in self._retry_queue:
            del self._retry_queue[notification_id]

        return True

    def mark_failed(self, notification_id: str, error: str) -> bool:
        """Mark notification as failed and schedule retry if applicable."""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        retry_count = self._retry_queue.get(notification_id, 0)

        if retry_count < self.config.max_retries:
            # Schedule retry
            self._retry_queue[notification_id] = retry_count + 1
            delay = self.config.retry_delay_seconds * (2 ** retry_count)  # Exponential backoff
            notification.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            notification.status = NotificationStatus.QUEUED

            # Re-add to queue
            priority_score = self._priority_score(notification)
            timestamp = notification.scheduled_at.timestamp()
            heapq.heappush(self._queue, (priority_score, timestamp, notification))

            return True
        else:
            # Move to dead letter queue
            notification.mark_failed()
            self._dead_letter.append(notification)
            del self._notifications[notification_id]
            if notification_id in self._retry_queue:
                del self._retry_queue[notification_id]

            return False

    def cancel(self, notification_id: str) -> bool:
        """Cancel a queued notification."""
        if notification_id in self._notifications:
            del self._notifications[notification_id]
            if notification_id in self._retry_queue:
                del self._retry_queue[notification_id]
            return True
        return False

    def get_pending_count(self) -> int:
        """Get count of pending notifications."""
        return len(self._notifications)

    def get_dead_letter_count(self) -> int:
        """Get count of dead letter notifications."""
        return len(self._dead_letter)

    def get_dead_letter_queue(self) -> list[Notification]:
        """Get dead letter queue contents."""
        return self._dead_letter.copy()

    def clear_dead_letter(self) -> int:
        """Clear dead letter queue."""
        count = len(self._dead_letter)
        self._dead_letter = []
        return count

    def retry_dead_letter(self) -> int:
        """Retry all dead letter notifications."""
        count = 0
        for notification in self._dead_letter:
            notification.status = NotificationStatus.PENDING
            notification.scheduled_at = None
            if self.enqueue(notification):
                count += 1

        self._dead_letter = []
        return count

    def cleanup_expired(self) -> int:
        """Remove expired notifications from queue."""
        count = 0
        expired_ids = []

        for nid, notification in self._notifications.items():
            if notification.is_expired():
                expired_ids.append(nid)
                notification.status = NotificationStatus.EXPIRED
                count += 1

        for nid in expired_ids:
            del self._notifications[nid]

        return count

    def get_user_pending(self, user_id: str) -> list[Notification]:
        """Get pending notifications for a user."""
        return [n for n in self._notifications.values() if n.user_id == user_id]

    def cancel_user_notifications(self, user_id: str) -> int:
        """Cancel all pending notifications for a user."""
        to_cancel = [n.notification_id for n in self._notifications.values() if n.user_id == user_id]
        count = 0
        for nid in to_cancel:
            if self.cancel(nid):
                count += 1
        return count

    def get_stats(self) -> dict:
        """Get queue statistics."""
        by_priority = defaultdict(int)
        by_category = defaultdict(int)
        by_status = defaultdict(int)

        for notification in self._notifications.values():
            by_priority[notification.priority.value] += 1
            by_category[notification.category.value] += 1
            by_status[notification.status.value] += 1

        return {
            "pending_count": len(self._notifications),
            "queue_size": len(self._queue),
            "retry_count": len(self._retry_queue),
            "dead_letter_count": len(self._dead_letter),
            "by_priority": dict(by_priority),
            "by_category": dict(by_category),
            "by_status": dict(by_status),
        }
