"""Data models for Push Notifications."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid

from src.notifications.config import (
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    Platform,
    TokenType,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Device:
    """Registered device for push notifications."""

    user_id: str
    device_token: str
    platform: Platform
    token_type: TokenType
    device_id: str = field(default_factory=_new_id)
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    os_version: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=_now)
    last_used_at: Optional[datetime] = None
    token_refreshed_at: Optional[datetime] = None

    def refresh_token(self, new_token: str) -> None:
        """Refresh the device token."""
        self.device_token = new_token
        self.token_refreshed_at = _now()

    def mark_used(self) -> None:
        """Mark device as recently used."""
        self.last_used_at = _now()

    def deactivate(self) -> None:
        """Deactivate the device."""
        self.is_active = False

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "platform": self.platform.value,
            "token_type": self.token_type.value,
            "device_name": self.device_name,
            "device_model": self.device_model,
            "app_version": self.app_version,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


@dataclass
class NotificationPreference:
    """User notification preferences for a category."""

    user_id: str
    category: NotificationCategory
    enabled: bool = True
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: list[str] = field(default_factory=lambda: ["push"])
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None  # HH:MM
    quiet_hours_end: Optional[str] = None
    timezone: str = "UTC"
    max_per_hour: Optional[int] = None

    def is_in_quiet_hours(self, current_time: datetime) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False

        try:
            start_hour, start_min = map(int, self.quiet_hours_start.split(":"))
            end_hour, end_min = map(int, self.quiet_hours_end.split(":"))

            current_minutes = current_time.hour * 60 + current_time.minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min

            if start_minutes <= end_minutes:
                return start_minutes <= current_minutes <= end_minutes
            else:
                # Overnight quiet hours (e.g., 22:00 - 08:00)
                return current_minutes >= start_minutes or current_minutes <= end_minutes
        except (ValueError, AttributeError):
            return False

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "category": self.category.value,
            "enabled": self.enabled,
            "priority": self.priority.value,
            "channels": self.channels,
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "timezone": self.timezone,
            "max_per_hour": self.max_per_hour,
        }


@dataclass
class Notification:
    """A push notification message."""

    user_id: str
    category: NotificationCategory
    title: str
    body: str
    notification_id: str = field(default_factory=_new_id)
    device_id: Optional[str] = None  # None = all devices
    data: dict = field(default_factory=dict)
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=_now)
    sent_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if notification has expired."""
        if self.expires_at is None:
            return False
        return _now() > self.expires_at

    def mark_sent(self) -> None:
        """Mark notification as sent."""
        self.status = NotificationStatus.SENT
        self.sent_at = _now()

    def mark_failed(self) -> None:
        """Mark notification as failed."""
        self.status = NotificationStatus.FAILED

    def to_push_payload(self) -> dict:
        """Convert to push notification payload."""
        payload = {
            "notification": {
                "title": self.title,
                "body": self.body,
            },
            "data": {
                "notification_id": self.notification_id,
                "category": self.category.value,
                **self.data,
            },
        }

        if self.image_url:
            payload["notification"]["image"] = self.image_url

        if self.action_url:
            payload["data"]["action_url"] = self.action_url

        return payload

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "category": self.category.value,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


@dataclass
class NotificationResult:
    """Result of sending a notification."""

    notification_id: str
    device_id: str
    success: bool
    status: NotificationStatus
    message_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "device_id": self.device_id,
            "success": self.success,
            "status": self.status.value,
            "message_id": self.message_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DeliveryStats:
    """Notification delivery statistics."""

    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_failed: int = 0
    avg_latency_ms: float = 0.0
    delivery_rate: float = 0.0
    open_rate: float = 0.0
    by_category: dict[str, dict] = field(default_factory=dict)
    by_platform: dict[str, dict] = field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    def calculate_rates(self) -> None:
        """Calculate delivery and open rates."""
        if self.total_sent > 0:
            self.delivery_rate = self.total_delivered / self.total_sent
            self.open_rate = self.total_opened / self.total_delivered if self.total_delivered > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_sent": self.total_sent,
            "total_delivered": self.total_delivered,
            "total_opened": self.total_opened,
            "total_failed": self.total_failed,
            "avg_latency_ms": self.avg_latency_ms,
            "delivery_rate": round(self.delivery_rate * 100, 2),
            "open_rate": round(self.open_rate * 100, 2),
            "by_category": self.by_category,
            "by_platform": self.by_platform,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


@dataclass
class PriceAlertPayload:
    """Payload for price alert notifications."""

    symbol: str
    current_price: float
    target_price: float
    direction: str  # above, below
    alert_id: str
    change_pct: Optional[float] = None

    def to_notification(self, user_id: str) -> Notification:
        """Create notification from price alert."""
        direction_text = "reached" if self.direction == "above" else "fell to"
        return Notification(
            user_id=user_id,
            category=NotificationCategory.PRICE_ALERTS,
            title=f"{self.symbol} Price Alert",
            body=f"{self.symbol} {direction_text} ${self.current_price:.2f} (target: ${self.target_price:.2f})",
            priority=NotificationPriority.HIGH,
            data={
                "type": "price_alert",
                "symbol": self.symbol,
                "price": str(self.current_price),
                "target": str(self.target_price),
                "alert_id": self.alert_id,
                "action": "open_stock",
            },
        )


@dataclass
class TradeExecutionPayload:
    """Payload for trade execution notifications."""

    order_id: str
    symbol: str
    side: str  # buy, sell
    quantity: int
    status: str  # filled, partial, cancelled, rejected
    fill_price: Optional[float] = None
    filled_qty: Optional[int] = None

    def to_notification(self, user_id: str) -> Notification:
        """Create notification from trade execution."""
        status_emoji = {
            "filled": "Filled",
            "partial": "Partially Filled",
            "cancelled": "Cancelled",
            "rejected": "Rejected",
        }

        title = f"Order {status_emoji.get(self.status, self.status)}"
        body = f"{self.side.upper()} {self.quantity} {self.symbol}"

        if self.fill_price:
            body += f" @ ${self.fill_price:.2f}"

        return Notification(
            user_id=user_id,
            category=NotificationCategory.TRADE_EXECUTIONS,
            title=title,
            body=body,
            priority=NotificationPriority.URGENT,
            data={
                "type": "trade_execution",
                "order_id": self.order_id,
                "symbol": self.symbol,
                "side": self.side,
                "status": self.status,
                "action": "open_order",
            },
        )


@dataclass
class PortfolioUpdatePayload:
    """Payload for portfolio update notifications."""

    total_value: float
    day_pnl: float
    day_return_pct: float
    significant_movers: list[dict] = field(default_factory=list)

    def to_notification(self, user_id: str) -> Notification:
        """Create notification from portfolio update."""
        pnl_sign = "+" if self.day_pnl >= 0 else ""
        return Notification(
            user_id=user_id,
            category=NotificationCategory.PORTFOLIO,
            title="Daily Portfolio Summary",
            body=f"P&L: {pnl_sign}${self.day_pnl:,.2f} ({pnl_sign}{self.day_return_pct:.2f}%)",
            priority=NotificationPriority.NORMAL,
            data={
                "type": "portfolio_update",
                "total_value": str(self.total_value),
                "day_pnl": str(self.day_pnl),
                "action": "open_portfolio",
            },
        )


@dataclass
class RiskAlertPayload:
    """Payload for risk alert notifications."""

    alert_type: str  # stop_loss, margin_warning, position_limit
    symbol: Optional[str] = None
    message: str = ""
    severity: str = "warning"  # warning, critical

    def to_notification(self, user_id: str) -> Notification:
        """Create notification from risk alert."""
        title = "Risk Alert"
        if self.alert_type == "stop_loss":
            title = "Stop-Loss Triggered"
        elif self.alert_type == "margin_warning":
            title = "Margin Warning"

        return Notification(
            user_id=user_id,
            category=NotificationCategory.RISK_ALERTS,
            title=title,
            body=self.message,
            priority=NotificationPriority.URGENT,
            data={
                "type": "risk_alert",
                "alert_type": self.alert_type,
                "symbol": self.symbol,
                "severity": self.severity,
                "action": "open_risk",
            },
        )
