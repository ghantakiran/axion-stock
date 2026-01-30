"""Alert management layer.

High-level CRUD operations, template instantiation, snooze/mute,
and user-facing alert management.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.alerts.config import (
    AlertType,
    AlertPriority,
    AlertStatus,
    ChannelType,
    ComparisonOperator,
    DEFAULT_COOLDOWNS,
    ALERT_TEMPLATES,
)
from src.alerts.models import (
    Alert,
    AlertEvent,
    Notification,
    NotificationPreferences,
    _utc_now,
)
from src.alerts.conditions import ConditionBuilder
from src.alerts.engine import AlertEngine

logger = logging.getLogger(__name__)


class AlertManager:
    """High-level alert management.

    Provides user-facing CRUD operations for alerts,
    template-based alert creation, and management features.
    """

    def __init__(self, engine: Optional[AlertEngine] = None) -> None:
        self.engine = engine or AlertEngine()

    def create_alert(
        self,
        user_id: str,
        name: str,
        alert_type: AlertType,
        metric: str,
        operator: ComparisonOperator,
        threshold: float,
        symbol: Optional[str] = None,
        priority: AlertPriority = AlertPriority.MEDIUM,
        channels: Optional[list[ChannelType]] = None,
        cooldown_seconds: Optional[int] = None,
        message_template: str = "",
        max_triggers: int = 0,
        expires_in_hours: Optional[int] = None,
    ) -> Alert:
        """Create a new alert.

        Args:
            user_id: Owner user ID.
            name: Alert name.
            alert_type: Type of alert.
            metric: Metric to monitor.
            operator: Comparison operator.
            threshold: Threshold value.
            symbol: Target symbol (optional).
            priority: Alert priority.
            channels: Delivery channels.
            cooldown_seconds: Cooldown between triggers.
            message_template: Custom message template.
            max_triggers: Max trigger count (0 = unlimited).
            expires_in_hours: Auto-expire after N hours.

        Returns:
            Created Alert.
        """
        conditions = ConditionBuilder.simple(metric, operator, threshold)

        if cooldown_seconds is None:
            cooldown_seconds = DEFAULT_COOLDOWNS.get(priority, 1800)

        expires_at = None
        if expires_in_hours:
            expires_at = _utc_now() + timedelta(hours=expires_in_hours)

        alert = Alert(
            user_id=user_id,
            name=name,
            alert_type=alert_type,
            symbol=symbol,
            conditions=conditions,
            priority=priority,
            channels=channels or [ChannelType.IN_APP],
            cooldown_seconds=cooldown_seconds,
            message_template=message_template,
            max_triggers=max_triggers,
            expires_at=expires_at,
        )

        self.engine.register_alert(alert)
        logger.info("Created alert %s for user %s", alert.alert_id, user_id)
        return alert

    def create_from_template(
        self,
        user_id: str,
        template_name: str,
        symbol: Optional[str] = None,
        threshold_override: Optional[float] = None,
        channels: Optional[list[ChannelType]] = None,
    ) -> Alert:
        """Create an alert from a pre-built template.

        Args:
            user_id: Owner user ID.
            template_name: Template key.
            symbol: Target symbol.
            threshold_override: Override default threshold.
            channels: Delivery channels.

        Returns:
            Created Alert.

        Raises:
            ValueError: If template not found.
        """
        template = ALERT_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        conditions = ConditionBuilder.from_template(
            template_name, threshold_override,
        )

        priority = template.get("priority", AlertPriority.MEDIUM)
        cooldown = DEFAULT_COOLDOWNS.get(priority, 1800)

        alert = Alert(
            user_id=user_id,
            name=template["name"],
            alert_type=template["alert_type"],
            symbol=symbol,
            conditions=conditions,
            priority=priority,
            channels=channels or [ChannelType.IN_APP],
            cooldown_seconds=cooldown,
        )

        self.engine.register_alert(alert)
        logger.info(
            "Created alert from template '%s' for user %s",
            template_name, user_id,
        )
        return alert

    def create_compound_alert(
        self,
        user_id: str,
        name: str,
        alert_type: AlertType,
        conditions: list[tuple[str, ComparisonOperator, float]],
        logical_operator: str = "and",
        symbol: Optional[str] = None,
        priority: AlertPriority = AlertPriority.MEDIUM,
        channels: Optional[list[ChannelType]] = None,
    ) -> Alert:
        """Create an alert with multiple conditions.

        Args:
            user_id: Owner user ID.
            name: Alert name.
            alert_type: Type of alert.
            conditions: List of (metric, operator, threshold) tuples.
            logical_operator: 'and' or 'or'.
            symbol: Target symbol.
            priority: Alert priority.
            channels: Delivery channels.

        Returns:
            Created Alert.
        """
        from src.alerts.config import LogicalOperator

        log_op = LogicalOperator(logical_operator)
        compound = ConditionBuilder.compound(conditions, log_op)

        alert = Alert(
            user_id=user_id,
            name=name,
            alert_type=alert_type,
            symbol=symbol,
            conditions=compound,
            priority=priority,
            channels=channels or [ChannelType.IN_APP],
            cooldown_seconds=DEFAULT_COOLDOWNS.get(priority, 1800),
        )

        self.engine.register_alert(alert)
        return alert

    def update_alert(
        self,
        alert_id: str,
        name: Optional[str] = None,
        priority: Optional[AlertPriority] = None,
        channels: Optional[list[ChannelType]] = None,
        cooldown_seconds: Optional[int] = None,
        status: Optional[AlertStatus] = None,
    ) -> Optional[Alert]:
        """Update an existing alert.

        Args:
            alert_id: Alert to update.
            name: New name.
            priority: New priority.
            channels: New delivery channels.
            cooldown_seconds: New cooldown.
            status: New status.

        Returns:
            Updated Alert, or None if not found.
        """
        alert = self.engine.get_alert(alert_id)
        if not alert:
            return None

        if name is not None:
            alert.name = name
        if priority is not None:
            alert.priority = priority
        if channels is not None:
            alert.channels = channels
        if cooldown_seconds is not None:
            alert.cooldown_seconds = cooldown_seconds
        if status is not None:
            alert.status = status

        alert.updated_at = _utc_now()
        return alert

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert.

        Args:
            alert_id: Alert to delete.

        Returns:
            True if found and deleted.
        """
        return self.engine.remove_alert(alert_id)

    def snooze_alert(self, alert_id: str, hours: int = 1) -> Optional[Alert]:
        """Snooze an alert for a period.

        Args:
            alert_id: Alert to snooze.
            hours: Snooze duration in hours.

        Returns:
            Updated Alert, or None if not found.
        """
        alert = self.engine.get_alert(alert_id)
        if not alert:
            return None

        alert.snooze_until = _utc_now() + timedelta(hours=hours)
        alert.status = AlertStatus.SNOOZED
        alert.updated_at = _utc_now()
        return alert

    def unsnooze_alert(self, alert_id: str) -> Optional[Alert]:
        """Unsnooze an alert.

        Args:
            alert_id: Alert to unsnooze.

        Returns:
            Updated Alert, or None if not found.
        """
        alert = self.engine.get_alert(alert_id)
        if not alert:
            return None

        alert.snooze_until = None
        alert.status = AlertStatus.ACTIVE
        alert.updated_at = _utc_now()
        return alert

    def disable_alert(self, alert_id: str) -> Optional[Alert]:
        """Disable an alert.

        Args:
            alert_id: Alert to disable.

        Returns:
            Updated Alert, or None if not found.
        """
        return self.update_alert(alert_id, status=AlertStatus.DISABLED)

    def enable_alert(self, alert_id: str) -> Optional[Alert]:
        """Re-enable a disabled alert.

        Args:
            alert_id: Alert to enable.

        Returns:
            Updated Alert, or None if not found.
        """
        return self.update_alert(alert_id, status=AlertStatus.ACTIVE)

    def get_user_alerts(self, user_id: str) -> list[Alert]:
        """Get all alerts for a user.

        Args:
            user_id: User ID.

        Returns:
            List of user's alerts.
        """
        return self.engine.get_alerts(user_id=user_id)

    def get_alert_history(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[AlertEvent]:
        """Get alert event history for a user.

        Args:
            user_id: User ID.
            limit: Max events to return.

        Returns:
            List of events.
        """
        return self.engine.get_events(user_id=user_id, limit=limit)

    def get_available_templates(self) -> dict[str, dict]:
        """Get all available alert templates.

        Returns:
            Template name -> template definition.
        """
        return dict(ALERT_TEMPLATES)

    def set_notification_preferences(
        self,
        user_id: str,
        enabled_channels: Optional[list[ChannelType]] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        webhook_url: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        quiet_hours_enabled: bool = False,
        quiet_start: int = 22,
        quiet_end: int = 7,
    ) -> NotificationPreferences:
        """Set notification preferences for a user.

        Args:
            user_id: User ID.
            enabled_channels: Channels to enable.
            email: Email address.
            phone: Phone number.
            webhook_url: Webhook URL.
            slack_webhook: Slack webhook URL.
            quiet_hours_enabled: Enable quiet hours.
            quiet_start: Quiet hours start (0-23).
            quiet_end: Quiet hours end (0-23).

        Returns:
            Updated preferences.
        """
        settings: dict[str, str] = {}
        if email:
            settings["email"] = email
        if phone:
            settings["phone"] = phone
        if webhook_url:
            settings["webhook_url"] = webhook_url
        if slack_webhook:
            settings["slack_webhook"] = slack_webhook

        prefs = NotificationPreferences(
            user_id=user_id,
            enabled_channels=enabled_channels or [ChannelType.IN_APP],
            channel_settings=settings,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_start_hour=quiet_start,
            quiet_end_hour=quiet_end,
        )

        self.engine.set_preferences(prefs)
        return prefs

    def evaluate(
        self,
        values: dict[str, dict[str, float]],
    ) -> list[AlertEvent]:
        """Evaluate all alerts against current values.

        Args:
            values: Symbol -> {metric: value} mapping.

        Returns:
            List of triggered events.
        """
        return self.engine.evaluate(values)

    def get_stats(self) -> dict:
        """Get system statistics."""
        return self.engine.get_stats()
