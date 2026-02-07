"""Data models for Real-time WebSocket API."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid

from src.websocket.config import ChannelType, MessageType, ConnectionStatus


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection."""

    user_id: str
    connection_id: str = field(default_factory=_new_id)
    session_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: ConnectionStatus = ConnectionStatus.CONNECTING

    # Connection info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    client_version: Optional[str] = None

    # Metrics
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

    # Timestamps
    connected_at: datetime = field(default_factory=_now)
    last_heartbeat: datetime = field(default_factory=_now)
    disconnected_at: Optional[datetime] = None

    # Subscriptions
    subscriptions: dict[str, "Subscription"] = field(default_factory=dict)

    def update_heartbeat(self) -> None:
        """Update last heartbeat time."""
        self.last_heartbeat = _now()

    def add_subscription(self, subscription: "Subscription") -> None:
        """Add a subscription."""
        self.subscriptions[subscription.subscription_id] = subscription

    def remove_subscription(self, subscription_id: str) -> Optional["Subscription"]:
        """Remove a subscription."""
        return self.subscriptions.pop(subscription_id, None)

    def get_subscriptions_for_channel(self, channel: ChannelType) -> list["Subscription"]:
        """Get all subscriptions for a channel."""
        return [s for s in self.subscriptions.values() if s.channel == channel and s.is_active]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "connected_at": self.connected_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "subscription_count": len(self.subscriptions),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
        }


@dataclass
class Subscription:
    """Represents a channel subscription."""

    channel: ChannelType
    subscription_id: str = field(default_factory=_new_id)
    symbols: list[str] = field(default_factory=list)
    throttle_ms: int = 100
    filters: dict = field(default_factory=dict)
    is_active: bool = True
    subscribed_at: datetime = field(default_factory=_now)
    unsubscribed_at: Optional[datetime] = None

    # Tracking
    messages_delivered: int = 0
    last_message_at: Optional[datetime] = None

    def matches_symbol(self, symbol: str) -> bool:
        """Check if subscription matches a symbol."""
        if not self.symbols:
            return True  # No symbol filter = all symbols
        return symbol in self.symbols

    def should_throttle(self) -> bool:
        """Check if message should be throttled."""
        if self.throttle_ms <= 0:
            return False
        if self.last_message_at is None:
            return False

        elapsed_ms = (_now() - self.last_message_at).total_seconds() * 1000
        return elapsed_ms < self.throttle_ms

    def mark_delivered(self) -> None:
        """Mark message as delivered."""
        self.messages_delivered += 1
        self.last_message_at = _now()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "subscription_id": self.subscription_id,
            "channel": self.channel.value,
            "symbols": self.symbols,
            "throttle_ms": self.throttle_ms,
            "is_active": self.is_active,
            "subscribed_at": self.subscribed_at.isoformat(),
            "messages_delivered": self.messages_delivered,
        }


@dataclass
class StreamMessage:
    """A message sent over WebSocket."""

    type: MessageType
    channel: Optional[ChannelType] = None
    data: Any = None
    sequence: int = 0
    timestamp: datetime = field(default_factory=_now)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to wire format."""
        msg = {
            "type": self.type.value,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.channel:
            msg["channel"] = self.channel.value
        if self.data is not None:
            msg["data"] = self.data
        if self.error:
            msg["error"] = self.error
        return msg

    @classmethod
    def error_message(cls, error: str, sequence: int = 0) -> "StreamMessage":
        """Create an error message."""
        return cls(
            type=MessageType.ERROR,
            error=error,
            sequence=sequence,
        )

    @classmethod
    def connected_message(cls, connection_id: str) -> "StreamMessage":
        """Create a connected message."""
        return cls(
            type=MessageType.CONNECTED,
            data={"connection_id": connection_id},
        )

    @classmethod
    def subscribed_message(cls, subscription: Subscription) -> "StreamMessage":
        """Create a subscribed message."""
        return cls(
            type=MessageType.SUBSCRIBED,
            channel=subscription.channel,
            data=subscription.to_dict(),
        )


# Channel-specific data models

@dataclass
class QuoteData:
    """Real-time quote data."""

    symbol: str
    bid: float
    ask: float
    last: float
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "change": self.change,
            "change_pct": self.change_pct,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TradeData:
    """Individual trade execution data."""

    symbol: str
    price: float
    size: int
    exchange: str = ""
    conditions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "size": self.size,
            "exchange": self.exchange,
            "conditions": self.conditions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BarData:
    """OHLC bar data."""

    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    vwap: float = 0.0
    trade_count: int = 0
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
            "trade_count": self.trade_count,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OrderUpdate:
    """Order status update."""

    order_id: str
    symbol: str
    status: str  # pending, open, partial, filled, cancelled, rejected
    side: str  # buy, sell
    order_type: str  # market, limit, stop
    quantity: int
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "status": self.status,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PortfolioUpdate:
    """Portfolio value update."""

    total_value: float
    cash_balance: float
    positions_value: float
    day_pnl: float
    day_return_pct: float
    total_pnl: float
    total_return_pct: float
    buying_power: float = 0.0
    positions: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "total_value": self.total_value,
            "cash_balance": self.cash_balance,
            "positions_value": self.positions_value,
            "day_pnl": self.day_pnl,
            "day_return_pct": self.day_return_pct,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return_pct,
            "buying_power": self.buying_power,
            "positions": self.positions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AlertNotification:
    """Alert notification."""

    alert_id: str
    alert_type: str  # price, volume, technical, news
    symbol: Optional[str]
    condition: str
    message: str
    triggered_value: Optional[float] = None
    triggered_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "symbol": self.symbol,
            "condition": self.condition,
            "message": self.message,
            "triggered_value": self.triggered_value,
            "triggered_at": self.triggered_at.isoformat(),
        }
