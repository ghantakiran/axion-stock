"""Real-time WebSocket API for streaming market data and updates.

Provides live streaming for quotes, trades, orders, portfolio updates,
alerts, and news via WebSocket connections.
"""

from src.websocket.config import (
    WebSocketConfig,
    ChannelType,
    MessageType,
    ConnectionStatus,
    DEFAULT_WEBSOCKET_CONFIG,
)
from src.websocket.models import (
    WebSocketConnection,
    Subscription,
    StreamMessage,
    QuoteData,
    TradeData,
    BarData,
    OrderUpdate,
    PortfolioUpdate,
    AlertNotification,
)
from src.websocket.manager import ConnectionManager
from src.websocket.channels import ChannelRouter
from src.websocket.subscriptions import SubscriptionManager


__all__ = [
    # Config
    "WebSocketConfig",
    "ChannelType",
    "MessageType",
    "ConnectionStatus",
    "DEFAULT_WEBSOCKET_CONFIG",
    # Models
    "WebSocketConnection",
    "Subscription",
    "StreamMessage",
    "QuoteData",
    "TradeData",
    "BarData",
    "OrderUpdate",
    "PortfolioUpdate",
    "AlertNotification",
    # Core
    "ConnectionManager",
    "ChannelRouter",
    "SubscriptionManager",
]
