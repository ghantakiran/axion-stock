"""Alert & Notification Network (PRD-142).

Multi-channel alert system with user-configurable rules,
delivery tracking, throttling, quiet hours, and batched digests.
Supports Email, SMS, Push, Slack, Discord, Telegram channels.

Example:
    from src.alert_network import (
        NotificationManager, AlertRule, TriggerType, ChannelKind,
    )

    mgr = NotificationManager()
    mgr.add_rule(AlertRule(
        name="AAPL Volume Spike",
        trigger_type=TriggerType.VOLUME_SPIKE,
        symbol="AAPL",
        threshold=3.0,
        channels=[ChannelKind.PUSH, ChannelKind.EMAIL],
    ))
    result = await mgr.evaluate_and_notify(data)
"""

from src.alert_network.rules import (
    AlertRule,
    TriggerType,
    RuleEngine,
    TriggeredAlert,
)
from src.alert_network.channels import (
    ChannelKind,
    NotificationChannel,
    NotificationPayload,
    ChannelResult,
    EmailChannel,
    SMSChannel,
    PushChannel,
    SlackChannel,
    DiscordChannel,
    TelegramChannel,
    ChannelRegistry,
)
from src.alert_network.delivery import (
    DeliveryRecord,
    DeliveryStatus,
    DeliveryPreferences,
    DeliveryTracker,
)
from src.alert_network.manager import (
    NotificationManager,
    NotificationResult,
    BatchDigest,
)

__all__ = [
    # Rules
    "AlertRule",
    "TriggerType",
    "RuleEngine",
    "TriggeredAlert",
    # Channels
    "ChannelKind",
    "NotificationChannel",
    "NotificationPayload",
    "ChannelResult",
    "EmailChannel",
    "SMSChannel",
    "PushChannel",
    "SlackChannel",
    "DiscordChannel",
    "TelegramChannel",
    "ChannelRegistry",
    # Delivery
    "DeliveryRecord",
    "DeliveryStatus",
    "DeliveryPreferences",
    "DeliveryTracker",
    # Manager
    "NotificationManager",
    "NotificationResult",
    "BatchDigest",
]
