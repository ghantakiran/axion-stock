"""Alerting & Notifications System.

Multi-channel alerting with condition evaluation, template-based alerts,
and notification delivery via in-app, email, SMS, webhook, and Slack.

Example:
    from src.alerts import AlertManager, AlertType, ComparisonOperator

    manager = AlertManager()

    # Create a price alert
    alert = manager.create_alert(
        user_id="user1",
        name="AAPL Above $200",
        alert_type=AlertType.PRICE,
        metric="price",
        operator=ComparisonOperator.GT,
        threshold=200.0,
        symbol="AAPL",
    )

    # Create from template
    alert = manager.create_from_template(
        user_id="user1",
        template_name="rsi_overbought",
        symbol="MSFT",
    )

    # Evaluate alerts
    events = manager.evaluate({
        "AAPL": {"price": 205.0},
        "MSFT": {"rsi_14": 72.0},
    })
"""

from src.alerts.config import (
    AlertType,
    AlertPriority,
    AlertStatus,
    ComparisonOperator,
    LogicalOperator,
    ChannelType,
    DeliveryStatus,
    DigestFrequency,
    DEFAULT_COOLDOWNS,
    MAX_ALERTS_PER_USER,
    ALERT_TEMPLATES,
    EmailConfig,
    SMSConfig,
    SlackConfig,
    WebhookConfig,
    QuietHours,
    AlertingConfig,
    DEFAULT_ALERTING_CONFIG,
)

from src.alerts.models import (
    AlertCondition,
    CompoundCondition,
    Alert,
    AlertEvent,
    Notification,
    NotificationPreferences,
)

from src.alerts.conditions import (
    ConditionBuilder,
    ConditionEvaluator,
)

from src.alerts.engine import AlertEngine

from src.alerts.manager import AlertManager

from src.alerts.channels import (
    DeliveryChannel,
    InAppChannel,
    EmailChannel,
    SMSChannel,
    WebhookChannel,
    SlackChannel,
)

__all__ = [
    # Config
    "AlertType",
    "AlertPriority",
    "AlertStatus",
    "ComparisonOperator",
    "LogicalOperator",
    "ChannelType",
    "DeliveryStatus",
    "DigestFrequency",
    "DEFAULT_COOLDOWNS",
    "MAX_ALERTS_PER_USER",
    "ALERT_TEMPLATES",
    "EmailConfig",
    "SMSConfig",
    "SlackConfig",
    "WebhookConfig",
    "QuietHours",
    "AlertingConfig",
    "DEFAULT_ALERTING_CONFIG",
    # Models
    "AlertCondition",
    "CompoundCondition",
    "Alert",
    "AlertEvent",
    "Notification",
    "NotificationPreferences",
    # Conditions
    "ConditionBuilder",
    "ConditionEvaluator",
    # Engine
    "AlertEngine",
    # Manager
    "AlertManager",
    # Channels
    "DeliveryChannel",
    "InAppChannel",
    "EmailChannel",
    "SMSChannel",
    "WebhookChannel",
    "SlackChannel",
]
