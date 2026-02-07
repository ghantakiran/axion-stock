"""PRD-60: Mobile Push Notifications.

Push notification system for mobile devices supporting:
- Device registration (FCM/APNs)
- User notification preferences
- Priority queue delivery
- Delivery analytics
"""

from src.notifications.config import (
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    Platform,
    TokenType,
    NotificationConfig,
    DEFAULT_NOTIFICATION_CONFIG,
    CATEGORY_CONFIGS,
)
from src.notifications.models import (
    Device,
    NotificationPreference,
    Notification,
    NotificationResult,
    DeliveryStats,
)
from src.notifications.devices import DeviceManager
from src.notifications.preferences import PreferenceManager
from src.notifications.sender import NotificationSender
from src.notifications.queue import NotificationQueue

__all__ = [
    # Config
    "NotificationCategory",
    "NotificationPriority",
    "NotificationStatus",
    "Platform",
    "TokenType",
    "NotificationConfig",
    "DEFAULT_NOTIFICATION_CONFIG",
    "CATEGORY_CONFIGS",
    # Models
    "Device",
    "NotificationPreference",
    "Notification",
    "NotificationResult",
    "DeliveryStats",
    # Managers
    "DeviceManager",
    "PreferenceManager",
    "NotificationSender",
    "NotificationQueue",
]
