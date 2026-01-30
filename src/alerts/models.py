"""Alerting & Notifications data models.

Dataclasses for alerts, conditions, notifications, and delivery records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from src.alerts.config import (
    AlertType,
    AlertPriority,
    AlertStatus,
    ComparisonOperator,
    LogicalOperator,
    ChannelType,
    DeliveryStatus,
    DigestFrequency,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class AlertCondition:
    """Single condition within an alert.

    Attributes:
        metric: The metric to evaluate (e.g., 'price', 'rsi_14', 'composite_score').
        operator: Comparison operator.
        threshold: Threshold value for comparison.
        previous_value: Last known value (for crosses_above/below detection).
    """
    metric: str
    operator: ComparisonOperator
    threshold: float
    previous_value: Optional[float] = None

    def evaluate(self, current_value: float) -> bool:
        """Evaluate condition against current value.

        Args:
            current_value: Current metric value.

        Returns:
            True if condition is met.
        """
        op = self.operator
        prev = self.previous_value

        if op == ComparisonOperator.GT:
            result = current_value > self.threshold
        elif op == ComparisonOperator.GTE:
            result = current_value >= self.threshold
        elif op == ComparisonOperator.LT:
            result = current_value < self.threshold
        elif op == ComparisonOperator.LTE:
            result = current_value <= self.threshold
        elif op == ComparisonOperator.EQ:
            result = current_value == self.threshold
        elif op == ComparisonOperator.NEQ:
            result = current_value != self.threshold
        elif op == ComparisonOperator.CROSSES_ABOVE:
            result = (
                prev is not None
                and prev <= self.threshold
                and current_value > self.threshold
            )
        elif op == ComparisonOperator.CROSSES_BELOW:
            result = (
                prev is not None
                and prev >= self.threshold
                and current_value < self.threshold
            )
        elif op == ComparisonOperator.PCT_CHANGE_GT:
            if prev is not None and prev != 0:
                pct = (current_value - prev) / abs(prev) * 100
                result = pct > self.threshold
            else:
                result = False
        elif op == ComparisonOperator.PCT_CHANGE_LT:
            if prev is not None and prev != 0:
                pct = (current_value - prev) / abs(prev) * 100
                result = pct < self.threshold
            else:
                result = False
        else:
            result = False

        # Update previous value for next evaluation
        self.previous_value = current_value
        return result


@dataclass
class CompoundCondition:
    """Group of conditions combined with a logical operator.

    Attributes:
        conditions: List of AlertCondition objects.
        logical_operator: AND or OR.
    """
    conditions: list[AlertCondition] = field(default_factory=list)
    logical_operator: LogicalOperator = LogicalOperator.AND

    def evaluate(self, values: dict[str, float]) -> bool:
        """Evaluate all conditions against provided values.

        Args:
            values: Metric name -> current value mapping.

        Returns:
            True if compound condition is satisfied.
        """
        if not self.conditions:
            return False

        results = []
        for cond in self.conditions:
            if cond.metric in values:
                results.append(cond.evaluate(values[cond.metric]))
            else:
                results.append(False)

        if self.logical_operator == LogicalOperator.AND:
            return all(results)
        else:
            return any(results)


@dataclass
class Alert:
    """Alert definition.

    Attributes:
        alert_id: Unique alert identifier.
        user_id: Owner user ID.
        name: Human-readable alert name.
        alert_type: Type of alert.
        symbol: Target symbol (optional for portfolio/risk alerts).
        conditions: Compound condition to evaluate.
        priority: Alert priority level.
        status: Current alert status.
        channels: Delivery channels for this alert.
        cooldown_seconds: Minimum seconds between triggers.
        message_template: Custom message template.
        last_triggered_at: Timestamp of last trigger.
        snooze_until: Snooze expiration timestamp.
        expires_at: Alert expiration timestamp.
        trigger_count: Total number of times triggered.
        max_triggers: Maximum triggers before auto-disable (0 = unlimited).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        metadata: Additional alert metadata.
    """
    alert_id: str = field(default_factory=_new_id)
    user_id: str = ""
    name: str = ""
    alert_type: AlertType = AlertType.PRICE
    symbol: Optional[str] = None
    conditions: CompoundCondition = field(default_factory=CompoundCondition)
    priority: AlertPriority = AlertPriority.MEDIUM
    status: AlertStatus = AlertStatus.ACTIVE
    channels: list[ChannelType] = field(default_factory=lambda: [ChannelType.IN_APP])
    cooldown_seconds: int = 1800
    message_template: str = ""
    last_triggered_at: Optional[datetime] = None
    snooze_until: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    trigger_count: int = 0
    max_triggers: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Check if alert is currently active and evaluable."""
        now = _utc_now()

        if self.status != AlertStatus.ACTIVE:
            return False

        if self.expires_at and now >= self.expires_at:
            self.status = AlertStatus.EXPIRED
            return False

        if self.snooze_until and now < self.snooze_until:
            return False

        if self.max_triggers > 0 and self.trigger_count >= self.max_triggers:
            self.status = AlertStatus.DISABLED
            return False

        return True

    def is_in_cooldown(self) -> bool:
        """Check if alert is in cooldown period."""
        if self.last_triggered_at is None:
            return False

        now = _utc_now()
        elapsed = (now - self.last_triggered_at).total_seconds()
        return elapsed < self.cooldown_seconds

    def trigger(self) -> None:
        """Mark alert as triggered."""
        self.last_triggered_at = _utc_now()
        self.trigger_count += 1
        self.updated_at = _utc_now()

    def format_message(self, values: dict[str, float]) -> str:
        """Format the alert notification message.

        Args:
            values: Current metric values.

        Returns:
            Formatted message string.
        """
        if self.message_template:
            try:
                return self.message_template.format(
                    name=self.name,
                    symbol=self.symbol or "",
                    **values,
                )
            except (KeyError, IndexError):
                pass

        # Default message
        parts = [f"Alert: {self.name}"]
        if self.symbol:
            parts.append(f"Symbol: {self.symbol}")

        for cond in self.conditions.conditions:
            if cond.metric in values:
                parts.append(
                    f"{cond.metric} = {values[cond.metric]:.4f} "
                    f"({cond.operator.value} {cond.threshold})"
                )

        return " | ".join(parts)


@dataclass
class AlertEvent:
    """Record of an alert being triggered.

    Attributes:
        event_id: Unique event identifier.
        alert_id: Reference to the alert.
        user_id: Alert owner.
        triggered_at: When the alert was triggered.
        values: Metric values at trigger time.
        message: Formatted alert message.
        priority: Alert priority at trigger time.
    """
    event_id: str = field(default_factory=_new_id)
    alert_id: str = ""
    user_id: str = ""
    triggered_at: datetime = field(default_factory=_utc_now)
    values: dict[str, float] = field(default_factory=dict)
    message: str = ""
    priority: AlertPriority = AlertPriority.MEDIUM


@dataclass
class Notification:
    """Notification delivery record.

    Attributes:
        notification_id: Unique notification identifier.
        event_id: Reference to the triggering event.
        user_id: Recipient user ID.
        channel: Delivery channel.
        status: Delivery status.
        message: Notification message content.
        subject: Message subject (for email).
        recipient: Channel-specific recipient (email addr, phone, URL).
        attempts: Number of delivery attempts.
        delivered_at: Successful delivery timestamp.
        error_message: Last error message if failed.
        created_at: Creation timestamp.
        is_read: Whether the notification has been read (in-app).
    """
    notification_id: str = field(default_factory=_new_id)
    event_id: str = ""
    user_id: str = ""
    channel: ChannelType = ChannelType.IN_APP
    status: DeliveryStatus = DeliveryStatus.PENDING
    message: str = ""
    subject: str = ""
    recipient: str = ""
    attempts: int = 0
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)
    is_read: bool = False

    def mark_sent(self) -> None:
        """Mark notification as successfully sent."""
        self.status = DeliveryStatus.SENT
        self.delivered_at = _utc_now()

    def mark_delivered(self) -> None:
        """Mark notification as delivered."""
        self.status = DeliveryStatus.DELIVERED
        self.delivered_at = _utc_now()

    def mark_failed(self, error: str) -> None:
        """Mark notification as failed."""
        self.status = DeliveryStatus.FAILED
        self.error_message = error

    def mark_read(self) -> None:
        """Mark in-app notification as read."""
        self.is_read = True


@dataclass
class NotificationPreferences:
    """Per-user notification preferences.

    Attributes:
        user_id: User ID.
        enabled_channels: Channels the user has enabled.
        channel_settings: Per-channel settings (email addr, phone, etc).
        quiet_hours_enabled: Whether quiet hours are active.
        quiet_start_hour: Quiet hours start (0-23).
        quiet_end_hour: Quiet hours end (0-23).
        digest_frequency: How often to batch notifications.
        priority_overrides: Channel overrides by priority level.
    """
    user_id: str = ""
    enabled_channels: list[ChannelType] = field(
        default_factory=lambda: [ChannelType.IN_APP]
    )
    channel_settings: dict[str, str] = field(default_factory=dict)
    quiet_hours_enabled: bool = False
    quiet_start_hour: int = 22
    quiet_end_hour: int = 7
    digest_frequency: DigestFrequency = DigestFrequency.IMMEDIATE
    priority_overrides: dict[str, list[ChannelType]] = field(default_factory=dict)

    def get_channels_for_priority(self, priority: AlertPriority) -> list[ChannelType]:
        """Get delivery channels for a given priority.

        Args:
            priority: Alert priority.

        Returns:
            List of channels to deliver to.
        """
        override = self.priority_overrides.get(priority.value)
        if override:
            return override
        return self.enabled_channels

    def is_in_quiet_hours(self, hour: int) -> bool:
        """Check if current hour is within quiet hours.

        Args:
            hour: Current hour (0-23).

        Returns:
            True if in quiet hours.
        """
        if not self.quiet_hours_enabled:
            return False

        if self.quiet_start_hour > self.quiet_end_hour:
            # Wraps midnight (e.g., 22-7)
            return hour >= self.quiet_start_hour or hour < self.quiet_end_hour
        else:
            return self.quiet_start_hour <= hour < self.quiet_end_hour
