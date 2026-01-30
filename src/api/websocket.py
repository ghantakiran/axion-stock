"""WebSocket Manager.

Manages real-time WebSocket connections, subscriptions, and message broadcasting.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from src.api.config import WebSocketChannel, WebSocketConfig, DEFAULT_WS_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    """Represents a WebSocket connection."""

    connection_id: str
    user_id: str
    subscriptions: set[str] = field(default_factory=set)
    symbol_subscriptions: dict[str, set[str]] = field(default_factory=dict)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: float = field(default_factory=time.time)
    message_count: int = 0


class WebSocketManager:
    """Manages WebSocket connections and message routing.

    Features:
    - Connection lifecycle management
    - Channel-based subscriptions (quotes, portfolio, alerts, signals, orders)
    - Symbol-level subscriptions within channels
    - Message broadcasting to subscribers
    - Heartbeat tracking for stale connections
    """

    def __init__(self, config: Optional[WebSocketConfig] = None):
        self.config = config or DEFAULT_WS_CONFIG
        # connection_id -> WSConnection
        self._connections: dict[str, WSConnection] = {}
        # user_id -> list of connection_ids
        self._user_connections: dict[str, list[str]] = {}
        # channel -> set of connection_ids
        self._channel_subscribers: dict[str, set[str]] = {}
        # channel:symbol -> set of connection_ids
        self._symbol_subscribers: dict[str, set[str]] = {}

    def connect(self, connection_id: str, user_id: str) -> tuple[bool, str]:
        """Register a new WebSocket connection.

        Args:
            connection_id: Unique connection identifier.
            user_id: User owning the connection.

        Returns:
            Tuple of (success, message).
        """
        user_conns = self._user_connections.get(user_id, [])
        if len(user_conns) >= self.config.max_connections_per_user:
            return False, "Max connections per user exceeded"

        conn = WSConnection(connection_id=connection_id, user_id=user_id)
        self._connections[connection_id] = conn

        if user_id not in self._user_connections:
            self._user_connections[user_id] = []
        self._user_connections[user_id].append(connection_id)

        logger.info(f"WebSocket connected: {connection_id} (user={user_id})")
        return True, "connected"

    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection.

        Args:
            connection_id: Connection to remove.
        """
        conn = self._connections.pop(connection_id, None)
        if not conn:
            return

        # Clean up user connections
        user_conns = self._user_connections.get(conn.user_id, [])
        if connection_id in user_conns:
            user_conns.remove(connection_id)
        if not user_conns:
            self._user_connections.pop(conn.user_id, None)

        # Clean up channel subscriptions
        for channel in conn.subscriptions:
            subs = self._channel_subscribers.get(channel, set())
            subs.discard(connection_id)

        # Clean up symbol subscriptions
        for key in list(self._symbol_subscribers.keys()):
            self._symbol_subscribers[key].discard(connection_id)
            if not self._symbol_subscribers[key]:
                del self._symbol_subscribers[key]

        logger.info(f"WebSocket disconnected: {connection_id}")

    def subscribe(
        self,
        connection_id: str,
        channel: str,
        symbols: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        """Subscribe a connection to a channel.

        Args:
            connection_id: Connection ID.
            channel: Channel name (quotes, portfolio, alerts, etc.).
            symbols: Optional list of symbols for quote channel.

        Returns:
            Tuple of (success, message).
        """
        conn = self._connections.get(connection_id)
        if not conn:
            return False, "Connection not found"

        total_subs = len(conn.subscriptions) + sum(
            len(s) for s in conn.symbol_subscriptions.values()
        )
        if total_subs >= self.config.max_subscriptions_per_connection:
            return False, "Max subscriptions exceeded"

        # Subscribe to channel
        conn.subscriptions.add(channel)
        if channel not in self._channel_subscribers:
            self._channel_subscribers[channel] = set()
        self._channel_subscribers[channel].add(connection_id)

        # Subscribe to specific symbols within channel
        if symbols:
            if channel not in conn.symbol_subscriptions:
                conn.symbol_subscriptions[channel] = set()

            for sym in symbols:
                sym = sym.upper()
                conn.symbol_subscriptions[channel].add(sym)
                key = f"{channel}:{sym}"
                if key not in self._symbol_subscribers:
                    self._symbol_subscribers[key] = set()
                self._symbol_subscribers[key].add(connection_id)

        logger.debug(
            f"Subscribed {connection_id} to {channel}"
            + (f" symbols={symbols}" if symbols else "")
        )
        return True, "subscribed"

    def unsubscribe(
        self,
        connection_id: str,
        channel: str,
        symbols: Optional[list[str]] = None,
    ) -> tuple[bool, str]:
        """Unsubscribe from a channel.

        Args:
            connection_id: Connection ID.
            channel: Channel to unsubscribe from.
            symbols: Specific symbols to unsubscribe (None = all).

        Returns:
            Tuple of (success, message).
        """
        conn = self._connections.get(connection_id)
        if not conn:
            return False, "Connection not found"

        if symbols:
            # Unsubscribe specific symbols
            sym_subs = conn.symbol_subscriptions.get(channel, set())
            for sym in symbols:
                sym = sym.upper()
                sym_subs.discard(sym)
                key = f"{channel}:{sym}"
                if key in self._symbol_subscribers:
                    self._symbol_subscribers[key].discard(connection_id)
        else:
            # Unsubscribe from entire channel
            conn.subscriptions.discard(channel)
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(connection_id)
            conn.symbol_subscriptions.pop(channel, None)

        return True, "unsubscribed"

    def get_subscribers(
        self,
        channel: str,
        symbol: Optional[str] = None,
    ) -> set[str]:
        """Get connection IDs subscribed to a channel/symbol.

        Args:
            channel: Channel name.
            symbol: Optional symbol filter.

        Returns:
            Set of connection IDs.
        """
        if symbol:
            key = f"{channel}:{symbol.upper()}"
            return set(self._symbol_subscribers.get(key, set()))

        return set(self._channel_subscribers.get(channel, set()))

    def broadcast(
        self,
        channel: str,
        data: dict,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """Prepare broadcast messages for channel subscribers.

        Args:
            channel: Target channel.
            data: Message payload.
            symbol: Optional symbol filter.

        Returns:
            List of {connection_id, message} dicts to send.
        """
        subscribers = self.get_subscribers(channel, symbol)
        message = json.dumps({"channel": channel, **data})

        return [
            {"connection_id": cid, "message": message}
            for cid in subscribers
            if cid in self._connections
        ]

    def heartbeat(self, connection_id: str) -> bool:
        """Update heartbeat timestamp for a connection.

        Args:
            connection_id: Connection ID.

        Returns:
            True if connection exists.
        """
        conn = self._connections.get(connection_id)
        if conn:
            conn.last_heartbeat = time.time()
            return True
        return False

    def get_stale_connections(self) -> list[str]:
        """Get connections that haven't sent a heartbeat recently.

        Returns:
            List of stale connection IDs.
        """
        cutoff = time.time() - (self.config.heartbeat_interval * 3)
        return [
            cid for cid, conn in self._connections.items()
            if conn.last_heartbeat < cutoff
        ]

    def get_connection_info(self, connection_id: str) -> Optional[dict]:
        """Get info about a connection.

        Args:
            connection_id: Connection ID.

        Returns:
            Connection details or None.
        """
        conn = self._connections.get(connection_id)
        if not conn:
            return None

        return {
            "connection_id": conn.connection_id,
            "user_id": conn.user_id,
            "subscriptions": list(conn.subscriptions),
            "symbol_subscriptions": {
                ch: list(syms) for ch, syms in conn.symbol_subscriptions.items()
            },
            "connected_at": conn.connected_at.isoformat(),
            "message_count": conn.message_count,
        }

    def get_stats(self) -> dict:
        """Get WebSocket service stats.

        Returns:
            Service statistics.
        """
        return {
            "total_connections": len(self._connections),
            "total_users": len(self._user_connections),
            "channel_subscribers": {
                ch: len(subs) for ch, subs in self._channel_subscribers.items()
            },
            "symbol_subscriptions": len(self._symbol_subscribers),
        }
