"""Connection manager for WebSocket API."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, Any
import asyncio

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
)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or DEFAULT_WEBSOCKET_CONFIG
        self._connections: dict[str, WebSocketConnection] = {}
        self._user_connections: dict[str, list[str]] = {}  # user_id -> [connection_ids]
        self._sequence: int = 0
        self._message_handlers: dict[MessageType, Callable] = {}

    @property
    def connection_count(self) -> int:
        """Get total active connections."""
        return len(self._connections)

    def create_connection(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> WebSocketConnection:
        """Create a new connection."""
        # Check limits
        user_connection_ids = self._user_connections.get(user_id, [])
        if len(user_connection_ids) >= self.config.max_connections_per_user:
            raise ConnectionError(f"Max connections per user ({self.config.max_connections_per_user}) exceeded")

        if self.connection_count >= self.config.max_total_connections:
            raise ConnectionError(f"Max total connections ({self.config.max_total_connections}) exceeded")

        # Create connection
        connection = WebSocketConnection(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status=ConnectionStatus.CONNECTED,
        )

        # Store
        self._connections[connection.connection_id] = connection
        if user_id not in self._user_connections:
            self._user_connections[user_id] = []
        self._user_connections[user_id].append(connection.connection_id)

        return connection

    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> list[WebSocketConnection]:
        """Get all connections for a user."""
        connection_ids = self._user_connections.get(user_id, [])
        return [self._connections[cid] for cid in connection_ids if cid in self._connections]

    def disconnect(self, connection_id: str, reason: str = "client_disconnect") -> bool:
        """Disconnect a connection."""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        connection.status = ConnectionStatus.DISCONNECTED
        connection.disconnected_at = datetime.now(timezone.utc)

        # Remove from storage
        del self._connections[connection_id]

        user_connections = self._user_connections.get(connection.user_id, [])
        if connection_id in user_connections:
            user_connections.remove(connection_id)

        return True

    def heartbeat(self, connection_id: str) -> bool:
        """Process heartbeat from connection."""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        connection.update_heartbeat()
        return True

    def check_stale_connections(self) -> list[str]:
        """Check for stale connections that missed heartbeats."""
        stale = []
        now = datetime.now(timezone.utc)
        timeout = timedelta(seconds=self.config.heartbeat_timeout_seconds)

        for conn_id, connection in list(self._connections.items()):
            if now - connection.last_heartbeat > timeout:
                stale.append(conn_id)

        return stale

    def prune_stale_connections(self) -> int:
        """Disconnect stale connections."""
        stale = self.check_stale_connections()
        for conn_id in stale:
            self.disconnect(conn_id, reason="heartbeat_timeout")
        return len(stale)

    def subscribe(
        self,
        connection_id: str,
        channel: ChannelType,
        symbols: Optional[list[str]] = None,
        throttle_ms: Optional[int] = None,
        filters: Optional[dict] = None,
    ) -> Subscription:
        """Subscribe to a channel."""
        connection = self._connections.get(connection_id)
        if not connection:
            raise ValueError(f"Connection not found: {connection_id}")

        # Check subscription limits
        if len(connection.subscriptions) >= self.config.max_subscriptions_per_connection:
            raise ValueError("Max subscriptions per connection exceeded")

        if symbols and len(symbols) > self.config.max_symbols_per_subscription:
            raise ValueError(f"Max symbols per subscription ({self.config.max_symbols_per_subscription}) exceeded")

        # Create subscription
        subscription = Subscription(
            channel=channel,
            symbols=symbols or [],
            throttle_ms=throttle_ms or self.config.default_throttle_ms,
            filters=filters or {},
        )

        connection.add_subscription(subscription)
        return subscription

    def unsubscribe(self, connection_id: str, subscription_id: str) -> bool:
        """Unsubscribe from a channel."""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        subscription = connection.remove_subscription(subscription_id)
        if subscription:
            subscription.is_active = False
            subscription.unsubscribed_at = datetime.now(timezone.utc)
            return True

        return False

    def get_subscriptions_for_symbol(
        self,
        symbol: str,
        channel: ChannelType,
    ) -> list[tuple[WebSocketConnection, Subscription]]:
        """Get all subscriptions interested in a symbol."""
        results = []
        for connection in self._connections.values():
            for sub in connection.get_subscriptions_for_channel(channel):
                if sub.matches_symbol(symbol):
                    results.append((connection, sub))
        return results

    def broadcast_to_channel(
        self,
        channel: ChannelType,
        data: Any,
        symbol: Optional[str] = None,
    ) -> int:
        """Broadcast message to all subscribers of a channel."""
        message = StreamMessage(
            type=MessageType.UPDATE,
            channel=channel,
            data=data,
            sequence=self._next_sequence(),
        )

        delivered = 0
        for connection in self._connections.values():
            for sub in connection.get_subscriptions_for_channel(channel):
                if symbol and not sub.matches_symbol(symbol):
                    continue

                if sub.should_throttle():
                    continue

                # In a real implementation, this would send via WebSocket
                sub.mark_delivered()
                connection.messages_sent += 1
                delivered += 1

        return delivered

    def send_to_connection(
        self,
        connection_id: str,
        message: StreamMessage,
    ) -> bool:
        """Send message to a specific connection."""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        message.sequence = self._next_sequence()
        # In a real implementation, this would send via WebSocket
        connection.messages_sent += 1
        return True

    def send_to_user(
        self,
        user_id: str,
        message: StreamMessage,
    ) -> int:
        """Send message to all connections for a user."""
        connections = self.get_user_connections(user_id)
        sent = 0
        for connection in connections:
            if self.send_to_connection(connection.connection_id, message):
                sent += 1
        return sent

    def _next_sequence(self) -> int:
        """Get next sequence number."""
        self._sequence += 1
        return self._sequence

    def get_stats(self) -> dict:
        """Get connection statistics."""
        total_subs = sum(len(c.subscriptions) for c in self._connections.values())
        total_sent = sum(c.messages_sent for c in self._connections.values())
        total_received = sum(c.messages_received for c in self._connections.values())

        channel_counts = {}
        for connection in self._connections.values():
            for sub in connection.subscriptions.values():
                channel = sub.channel.value
                channel_counts[channel] = channel_counts.get(channel, 0) + 1

        return {
            "active_connections": self.connection_count,
            "total_subscriptions": total_subs,
            "total_messages_sent": total_sent,
            "total_messages_received": total_received,
            "users_connected": len(self._user_connections),
            "channel_subscriptions": channel_counts,
        }
