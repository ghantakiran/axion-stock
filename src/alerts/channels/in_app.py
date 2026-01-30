"""In-app notification channel.

Stores notifications in memory for retrieval by the UI.
"""

import logging
from collections import defaultdict

from src.alerts.channels.base import DeliveryChannel
from src.alerts.models import Notification

logger = logging.getLogger(__name__)


class InAppChannel(DeliveryChannel):
    """In-app notification delivery.

    Stores notifications in memory, organized by user_id.
    The UI polls for unread notifications.
    """

    def __init__(self, max_per_user: int = 100) -> None:
        self.max_per_user = max_per_user
        self._notifications: dict[str, list[Notification]] = defaultdict(list)

    def send(self, notification: Notification) -> bool:
        """Store notification for in-app display.

        Args:
            notification: Notification to store.

        Returns:
            True (always succeeds for in-app).
        """
        user_notifs = self._notifications[notification.user_id]
        user_notifs.append(notification)

        # Trim old notifications
        if len(user_notifs) > self.max_per_user:
            self._notifications[notification.user_id] = user_notifs[
                -self.max_per_user:
            ]

        notification.mark_delivered()
        logger.debug(
            "In-app notification stored for user %s", notification.user_id,
        )
        return True

    def validate_recipient(self, recipient: str) -> bool:
        """In-app always valid (uses user_id)."""
        return True

    def get_unread(self, user_id: str) -> list[Notification]:
        """Get unread notifications for a user.

        Args:
            user_id: User ID.

        Returns:
            List of unread notifications.
        """
        return [
            n for n in self._notifications.get(user_id, [])
            if not n.is_read
        ]

    def get_all(self, user_id: str) -> list[Notification]:
        """Get all notifications for a user.

        Args:
            user_id: User ID.

        Returns:
            List of all notifications.
        """
        return list(self._notifications.get(user_id, []))

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark a specific notification as read.

        Args:
            user_id: User ID.
            notification_id: Notification to mark.

        Returns:
            True if notification was found and marked.
        """
        for n in self._notifications.get(user_id, []):
            if n.notification_id == notification_id:
                n.mark_read()
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user.

        Args:
            user_id: User ID.

        Returns:
            Number of notifications marked.
        """
        count = 0
        for n in self._notifications.get(user_id, []):
            if not n.is_read:
                n.mark_read()
                count += 1
        return count

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications.

        Args:
            user_id: User ID.

        Returns:
            Unread count.
        """
        return len(self.get_unread(user_id))

    def clear(self, user_id: str) -> None:
        """Clear all notifications for a user.

        Args:
            user_id: User ID.
        """
        self._notifications.pop(user_id, None)
