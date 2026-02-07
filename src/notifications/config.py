"""Configuration for Push Notifications."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NotificationCategory(Enum):
    """Notification categories."""
    PRICE_ALERTS = "price_alerts"
    TRADE_EXECUTIONS = "trade_executions"
    PORTFOLIO = "portfolio"
    RISK_ALERTS = "risk_alerts"
    NEWS = "news"
    SYSTEM = "system"
    EARNINGS = "earnings"
    DIVIDENDS = "dividends"


class NotificationPriority(Enum):
    """Notification priority levels."""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class NotificationStatus(Enum):
    """Notification delivery status."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    FAILED = "failed"
    EXPIRED = "expired"


class Platform(Enum):
    """Mobile platforms."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class TokenType(Enum):
    """Push token types."""
    FCM = "fcm"  # Firebase Cloud Messaging
    APNS = "apns"  # Apple Push Notification Service
    WEB_PUSH = "web_push"


@dataclass
class NotificationConfig:
    """Notification system configuration."""

    # Delivery settings
    max_retries: int = 3
    retry_delay_seconds: int = 60
    batch_size: int = 500
    max_queue_age_hours: int = 24

    # Rate limits
    max_per_user_per_hour: int = 50
    max_per_user_per_day: int = 200
    max_per_device_per_minute: int = 5

    # Timeouts
    send_timeout_seconds: int = 30
    delivery_timeout_seconds: int = 300

    # FCM settings
    fcm_api_key: Optional[str] = None
    fcm_project_id: Optional[str] = None
    fcm_sender_id: Optional[str] = None

    # APNs settings
    apns_key_id: Optional[str] = None
    apns_team_id: Optional[str] = None
    apns_bundle_id: Optional[str] = None
    apns_use_sandbox: bool = True

    # Analytics
    track_opens: bool = True
    track_delivery: bool = True
    retention_days: int = 90


DEFAULT_NOTIFICATION_CONFIG = NotificationConfig()


# Category-specific configurations
CATEGORY_CONFIGS: dict[NotificationCategory, dict] = {
    NotificationCategory.PRICE_ALERTS: {
        "description": "Price target and threshold alerts",
        "default_priority": NotificationPriority.HIGH,
        "default_enabled": True,
        "icon": "trending_up",
        "color": "#4CAF50",
        "sound": "price_alert.wav",
        "ttl_seconds": 3600,  # 1 hour
    },
    NotificationCategory.TRADE_EXECUTIONS: {
        "description": "Order fills, cancellations, rejections",
        "default_priority": NotificationPriority.URGENT,
        "default_enabled": True,
        "icon": "swap_horiz",
        "color": "#2196F3",
        "sound": "trade.wav",
        "ttl_seconds": 7200,
    },
    NotificationCategory.PORTFOLIO: {
        "description": "Daily P&L summaries, significant changes",
        "default_priority": NotificationPriority.NORMAL,
        "default_enabled": True,
        "icon": "account_balance_wallet",
        "color": "#9C27B0",
        "sound": "default",
        "ttl_seconds": 86400,
    },
    NotificationCategory.RISK_ALERTS: {
        "description": "Stop-loss triggers, margin warnings",
        "default_priority": NotificationPriority.URGENT,
        "default_enabled": True,
        "icon": "warning",
        "color": "#F44336",
        "sound": "alert.wav",
        "ttl_seconds": 1800,
    },
    NotificationCategory.NEWS: {
        "description": "Breaking news for watched symbols",
        "default_priority": NotificationPriority.NORMAL,
        "default_enabled": False,
        "icon": "article",
        "color": "#FF9800",
        "sound": "default",
        "ttl_seconds": 14400,
    },
    NotificationCategory.SYSTEM: {
        "description": "Maintenance, updates, announcements",
        "default_priority": NotificationPriority.LOW,
        "default_enabled": True,
        "icon": "info",
        "color": "#607D8B",
        "sound": None,
        "ttl_seconds": 86400,
    },
    NotificationCategory.EARNINGS: {
        "description": "Earnings announcements and surprises",
        "default_priority": NotificationPriority.HIGH,
        "default_enabled": False,
        "icon": "trending_up",
        "color": "#00BCD4",
        "sound": "default",
        "ttl_seconds": 7200,
    },
    NotificationCategory.DIVIDENDS: {
        "description": "Dividend declarations and ex-dates",
        "default_priority": NotificationPriority.NORMAL,
        "default_enabled": False,
        "icon": "payments",
        "color": "#8BC34A",
        "sound": None,
        "ttl_seconds": 86400,
    },
}
