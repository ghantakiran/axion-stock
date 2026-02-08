"""PRD-119: WebSocket Scaling & Real-time Infrastructure."""

from .config import (
    MessagePriority,
    ConnectionState,
    DropStrategy,
    WSScalingConfig,
)
from .registry import ConnectionInfo, ConnectionRegistry
from .router import Message, MessageRouter
from .backpressure import QueueStats, BackpressureHandler
from .reconnection import ReconnectionSession, ReconnectionManager

__all__ = [
    # Config
    "MessagePriority",
    "ConnectionState",
    "DropStrategy",
    "WSScalingConfig",
    # Registry
    "ConnectionInfo",
    "ConnectionRegistry",
    # Router
    "Message",
    "MessageRouter",
    # Backpressure
    "QueueStats",
    "BackpressureHandler",
    # Reconnection
    "ReconnectionSession",
    "ReconnectionManager",
]
