"""Configuration for Real-time WebSocket API."""

import enum
from dataclasses import dataclass


class ChannelType(enum.Enum):
    """Available streaming channels."""
    QUOTES = "quotes"
    TRADES = "trades"
    BARS = "bars"
    ORDERS = "orders"
    PORTFOLIO = "portfolio"
    ALERTS = "alerts"
    NEWS = "news"


class MessageType(enum.Enum):
    """WebSocket message types."""
    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"

    # Server -> Client
    SNAPSHOT = "snapshot"
    UPDATE = "update"
    PONG = "pong"
    ERROR = "error"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"


class ConnectionStatus(enum.Enum):
    """Connection status values."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class BarInterval(enum.Enum):
    """Bar aggregation intervals."""
    SECOND_1 = "1s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    DAY_1 = "1d"


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket server."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8765
    path: str = "/v1/stream"

    # Connection limits
    max_connections_per_user: int = 5
    max_total_connections: int = 10000

    # Subscription limits
    max_subscriptions_per_connection: int = 100
    max_symbols_per_subscription: int = 500

    # Timeouts
    heartbeat_interval_seconds: int = 30
    heartbeat_timeout_seconds: int = 60
    connection_timeout_seconds: int = 10

    # Rate limiting
    max_messages_per_second: int = 100
    max_subscriptions_per_minute: int = 60

    # Throttling
    default_throttle_ms: int = 100
    min_throttle_ms: int = 50
    max_throttle_ms: int = 5000

    # Message settings
    max_message_size_bytes: int = 65536
    enable_compression: bool = True

    # Authentication
    token_expiry_seconds: int = 3600
    require_authentication: bool = True


DEFAULT_WEBSOCKET_CONFIG = WebSocketConfig()


# Channel configurations
CHANNEL_CONFIGS = {
    ChannelType.QUOTES: {
        "description": "Real-time bid/ask/last quotes",
        "requires_symbols": True,
        "default_throttle_ms": 100,
        "max_symbols": 500,
    },
    ChannelType.TRADES: {
        "description": "Individual trade executions",
        "requires_symbols": True,
        "default_throttle_ms": 0,  # No throttle for trades
        "max_symbols": 100,
    },
    ChannelType.BARS: {
        "description": "OHLC bar aggregations",
        "requires_symbols": True,
        "default_throttle_ms": 1000,
        "max_symbols": 50,
    },
    ChannelType.ORDERS: {
        "description": "User order status updates",
        "requires_symbols": False,
        "default_throttle_ms": 0,
        "max_symbols": 0,
    },
    ChannelType.PORTFOLIO: {
        "description": "Portfolio value and position updates",
        "requires_symbols": False,
        "default_throttle_ms": 1000,
        "max_symbols": 0,
    },
    ChannelType.ALERTS: {
        "description": "Triggered alert notifications",
        "requires_symbols": False,
        "default_throttle_ms": 0,
        "max_symbols": 0,
    },
    ChannelType.NEWS: {
        "description": "Breaking news and events",
        "requires_symbols": True,
        "default_throttle_ms": 0,
        "max_symbols": 100,
    },
}
