"""Configuration for WebSocket Scaling & Real-time Infrastructure."""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MessagePriority(str, Enum):
    """Priority levels for WebSocket messages."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ConnectionState(str, Enum):
    """Lifecycle states for a WebSocket connection."""
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


class DropStrategy(str, Enum):
    """Strategies for dropping messages under backpressure."""
    OLDEST_FIRST = "oldest_first"
    LOWEST_PRIORITY = "lowest_priority"
    RANDOM = "random"


@dataclass
class WSScalingConfig:
    """Master configuration for WebSocket scaling infrastructure."""

    max_connections_per_user: int = 5
    max_global_connections: int = 10000
    message_buffer_size: int = 1000
    backpressure_threshold: int = 800
    slow_consumer_threshold_ms: int = 5000
    reconnection_window_seconds: int = 30
    max_reconnection_attempts: int = 5
    heartbeat_interval_seconds: int = 30
