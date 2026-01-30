"""Alert evaluation and notification dispatch engine.

Core engine that evaluates alert conditions, triggers notifications,
and manages delivery across channels.
"""

import logging
from typing import Optional

from src.alerts.config import (
    AlertPriority,
    AlertingConfig,
    ChannelType,
    DEFAULT_ALERTING_CONFIG,
    MAX_DELIVERY_RETRIES,
    RETRY_BACKOFF_SECONDS,
)
from src.alerts.models import (
    Alert,
    AlertEvent,
    Notification,
    NotificationPreferences,
    _new_id,
    _utc_now,
)
from src.alerts.conditions import ConditionEvaluator
from src.alerts.channels.base import DeliveryChannel
from src.alerts.channels.in_app import InAppChannel
from src.alerts.channels.email import EmailChannel
from src.alerts.channels.sms import SMSChannel
from src.alerts.channels.webhook import WebhookChannel
from src.alerts.channels.slack import SlackChannel

logger = logging.getLogger(__name__)


class AlertEngine:
    """Core alert evaluation and dispatch engine.

    Evaluates alert conditions against market data, generates events,
    and dispatches notifications through configured channels.
    """

    def __init__(self, config: Optional[AlertingConfig] = None) -> None:
        self.config = config or DEFAULT_ALERTING_CONFIG
        self._evaluator = ConditionEvaluator()
        self._alerts: dict[str, Alert] = {}
        self._events: list[AlertEvent] = []
        self._preferences: dict[str, NotificationPreferences] = {}

        # Initialize delivery channels
        self._channels: dict[ChannelType, DeliveryChannel] = {
            ChannelType.IN_APP: InAppChannel(),
            ChannelType.EMAIL: EmailChannel(self.config.email),
            ChannelType.SMS: SMSChannel(self.config.sms),
            ChannelType.WEBHOOK: WebhookChannel(self.config.webhook),
            ChannelType.SLACK: SlackChannel(self.config.slack),
        }

    @property
    def in_app_channel(self) -> InAppChannel:
        """Get the in-app channel for direct notification access."""
        return self._channels[ChannelType.IN_APP]  # type: ignore[return-value]

    def register_alert(self, alert: Alert) -> None:
        """Register an alert for evaluation.

        Args:
            alert: Alert to register.
        """
        self._alerts[alert.alert_id] = alert
        logger.debug("Registered alert %s: %s", alert.alert_id, alert.name)

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert.

        Args:
            alert_id: Alert to remove.

        Returns:
            True if alert was found and removed.
        """
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            self._evaluator.clear_state(alert_id)
            return True
        return False

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    def get_alerts(self, user_id: Optional[str] = None) -> list[Alert]:
        """Get all alerts, optionally filtered by user.

        Args:
            user_id: Filter by user ID.

        Returns:
            List of alerts.
        """
        alerts = list(self._alerts.values())
        if user_id:
            alerts = [a for a in alerts if a.user_id == user_id]
        return alerts

    def set_preferences(self, preferences: NotificationPreferences) -> None:
        """Set notification preferences for a user.

        Args:
            preferences: User notification preferences.
        """
        self._preferences[preferences.user_id] = preferences

    def get_preferences(self, user_id: str) -> NotificationPreferences:
        """Get notification preferences for a user.

        Args:
            user_id: User ID.

        Returns:
            NotificationPreferences (default if not set).
        """
        return self._preferences.get(user_id, NotificationPreferences(user_id=user_id))

    def evaluate(
        self,
        values: dict[str, dict[str, float]],
        current_hour: Optional[int] = None,
    ) -> list[AlertEvent]:
        """Evaluate all active alerts against provided values.

        Args:
            values: Symbol -> {metric: value} mapping. Use "*" for
                    portfolio-level/non-symbol-specific alerts.
            current_hour: Current hour (0-23) for quiet hours check.
                         If None, uses current UTC hour.

        Returns:
            List of newly triggered AlertEvent objects.
        """
        if current_hour is None:
            current_hour = _utc_now().hour

        triggered_events: list[AlertEvent] = []

        for alert in list(self._alerts.values()):
            if not alert.is_active():
                continue

            if alert.is_in_cooldown():
                continue

            # Get values for this alert's symbol
            symbol_key = alert.symbol or "*"
            alert_values = values.get(symbol_key, {})

            if not alert_values:
                continue

            # Evaluate conditions
            if self._evaluator.evaluate(
                alert.alert_id, alert.conditions, alert_values,
            ):
                event = self._trigger_alert(alert, alert_values)
                triggered_events.append(event)

                # Dispatch notifications
                self._dispatch(alert, event, current_hour)

        return triggered_events

    def _trigger_alert(
        self,
        alert: Alert,
        values: dict[str, float],
    ) -> AlertEvent:
        """Trigger an alert and create an event.

        Args:
            alert: Alert being triggered.
            values: Current metric values.

        Returns:
            AlertEvent record.
        """
        message = alert.format_message(values)
        alert.trigger()

        event = AlertEvent(
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            values=dict(values),
            message=message,
            priority=alert.priority,
        )

        self._events.append(event)
        logger.info(
            "Alert triggered: %s (%s) for user %s",
            alert.name, alert.alert_id, alert.user_id,
        )
        return event

    def _dispatch(
        self,
        alert: Alert,
        event: AlertEvent,
        current_hour: int,
    ) -> list[Notification]:
        """Dispatch notifications for a triggered alert.

        Args:
            alert: Triggered alert.
            event: Alert event.
            current_hour: Current hour for quiet hours check.

        Returns:
            List of created notifications.
        """
        prefs = self.get_preferences(alert.user_id)
        notifications: list[Notification] = []

        # Determine channels
        channels = alert.channels
        pref_channels = prefs.get_channels_for_priority(alert.priority)
        effective_channels = [c for c in channels if c in pref_channels] or channels

        # Check quiet hours
        in_quiet = prefs.is_in_quiet_hours(current_hour)

        for channel_type in effective_channels:
            # Skip non-critical alerts during quiet hours (except in-app)
            if (
                in_quiet
                and channel_type != ChannelType.IN_APP
                and alert.priority != AlertPriority.CRITICAL
            ):
                continue

            # Get recipient
            recipient = self._get_recipient(prefs, channel_type)

            notification = Notification(
                event_id=event.event_id,
                user_id=alert.user_id,
                channel=channel_type,
                message=event.message,
                subject=f"Axion Alert: {alert.name}",
                recipient=recipient,
            )

            # Deliver
            channel = self._channels.get(channel_type)
            if channel:
                notification.attempts += 1
                channel.send(notification)

            notifications.append(notification)

        return notifications

    def _get_recipient(
        self,
        prefs: NotificationPreferences,
        channel_type: ChannelType,
    ) -> str:
        """Get recipient for a channel from user preferences.

        Args:
            prefs: User preferences.
            channel_type: Channel type.

        Returns:
            Recipient string.
        """
        settings = prefs.channel_settings
        key_map = {
            ChannelType.EMAIL: "email",
            ChannelType.SMS: "phone",
            ChannelType.WEBHOOK: "webhook_url",
            ChannelType.SLACK: "slack_webhook",
        }
        return settings.get(key_map.get(channel_type, ""), "")

    def get_events(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[AlertEvent]:
        """Get alert event history.

        Args:
            user_id: Filter by user ID.
            limit: Maximum events to return.

        Returns:
            List of events, most recent first.
        """
        events = self._events
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        return sorted(
            events, key=lambda e: e.triggered_at, reverse=True,
        )[:limit]

    def get_stats(self) -> dict:
        """Get engine statistics.

        Returns:
            Dict with alert and event counts.
        """
        active = sum(1 for a in self._alerts.values() if a.is_active())
        return {
            "total_alerts": len(self._alerts),
            "active_alerts": active,
            "total_events": len(self._events),
            "alerts_by_type": self._count_by(
                self._alerts.values(), lambda a: a.alert_type.value,
            ),
            "alerts_by_priority": self._count_by(
                self._alerts.values(), lambda a: a.priority.value,
            ),
        }

    @staticmethod
    def _count_by(items, key_fn) -> dict[str, int]:
        """Count items by a key function."""
        counts: dict[str, int] = {}
        for item in items:
            k = key_fn(item)
            counts[k] = counts.get(k, 0) + 1
        return counts
