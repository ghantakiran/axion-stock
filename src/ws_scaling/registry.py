"""Connection registry for tracking WebSocket connections."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from .config import ConnectionState, WSScalingConfig

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Metadata for a single WebSocket connection."""

    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    instance_id: str = ""
    subscriptions: List[str] = field(default_factory=list)
    state: ConnectionState = ConnectionState.CONNECTED
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)


class ConnectionRegistry:
    """Thread-safe registry for managing WebSocket connections.

    Tracks connections per user, per instance, supports heartbeat updates,
    stale detection, and enforces per-user and global connection limits.
    """

    def __init__(self, config: Optional[WSScalingConfig] = None):
        self._config = config or WSScalingConfig()
        self._connections: Dict[str, ConnectionInfo] = {}
        self._user_connections: Dict[str, Set[str]] = {}
        self._instance_connections: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def register(
        self,
        user_id: str,
        instance_id: str,
        subscriptions: Optional[List[str]] = None,
    ) -> ConnectionInfo:
        """Register a new WebSocket connection.

        Returns the ConnectionInfo for the newly created connection.
        Raises ValueError if per-user or global limits are exceeded.
        """
        with self._lock:
            if not self._can_connect_unlocked(user_id):
                raise ValueError(
                    f"Connection limit reached for user '{user_id}' or global limit exceeded"
                )

            info = ConnectionInfo(
                user_id=user_id,
                instance_id=instance_id,
                subscriptions=subscriptions or [],
            )

            self._connections[info.connection_id] = info

            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(info.connection_id)

            if instance_id not in self._instance_connections:
                self._instance_connections[instance_id] = set()
            self._instance_connections[instance_id].add(info.connection_id)

            logger.info(
                "Registered connection %s for user=%s instance=%s",
                info.connection_id,
                user_id,
                instance_id,
            )
            return info

    def unregister(self, connection_id: str) -> bool:
        """Remove a connection from the registry. Returns True if found."""
        with self._lock:
            info = self._connections.pop(connection_id, None)
            if info is None:
                return False

            user_set = self._user_connections.get(info.user_id)
            if user_set:
                user_set.discard(connection_id)
                if not user_set:
                    del self._user_connections[info.user_id]

            inst_set = self._instance_connections.get(info.instance_id)
            if inst_set:
                inst_set.discard(connection_id)
                if not inst_set:
                    del self._instance_connections[info.instance_id]

            logger.info("Unregistered connection %s", connection_id)
            return True

    def get_connection(self, connection_id: str) -> Optional[ConnectionInfo]:
        """Retrieve connection info by ID."""
        return self._connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> List[ConnectionInfo]:
        """Return all connections for a given user."""
        conn_ids = self._user_connections.get(user_id, set())
        return [self._connections[cid] for cid in conn_ids if cid in self._connections]

    def get_instance_connections(self, instance_id: str) -> List[ConnectionInfo]:
        """Return all connections on a given server instance."""
        conn_ids = self._instance_connections.get(instance_id, set())
        return [self._connections[cid] for cid in conn_ids if cid in self._connections]

    def update_heartbeat(self, connection_id: str) -> None:
        """Update the last-heartbeat timestamp for a connection."""
        info = self._connections.get(connection_id)
        if info:
            info.last_heartbeat = datetime.utcnow()

    def update_subscriptions(self, connection_id: str, subscriptions: List[str]) -> None:
        """Replace the subscription list for a connection."""
        info = self._connections.get(connection_id)
        if info:
            info.subscriptions = subscriptions

    def get_stale_connections(self, timeout_seconds: int = 60) -> List[ConnectionInfo]:
        """Return connections whose heartbeat is older than *timeout_seconds*."""
        now = datetime.utcnow()
        stale: List[ConnectionInfo] = []
        for info in self._connections.values():
            elapsed = (now - info.last_heartbeat).total_seconds()
            if elapsed > timeout_seconds:
                stale.append(info)
        return stale

    def get_connection_count(self) -> int:
        """Total number of registered connections."""
        return len(self._connections)

    def get_user_count(self) -> int:
        """Number of distinct users with active connections."""
        return len(self._user_connections)

    def get_instance_count(self) -> int:
        """Number of distinct instances with active connections."""
        return len(self._instance_connections)

    def can_connect(self, user_id: str) -> bool:
        """Check whether a new connection is allowed for the given user."""
        with self._lock:
            return self._can_connect_unlocked(user_id)

    def _can_connect_unlocked(self, user_id: str) -> bool:
        """Internal limit check (caller must hold the lock)."""
        if len(self._connections) >= self._config.max_global_connections:
            return False
        user_conns = self._user_connections.get(user_id, set())
        if len(user_conns) >= self._config.max_connections_per_user:
            return False
        return True

    def get_stats(self) -> dict:
        """Return a summary of registry statistics."""
        return {
            "total_connections": self.get_connection_count(),
            "total_users": self.get_user_count(),
            "total_instances": self.get_instance_count(),
            "max_connections_per_user": self._config.max_connections_per_user,
            "max_global_connections": self._config.max_global_connections,
        }

    def reset(self) -> None:
        """Clear all connections (useful for testing)."""
        with self._lock:
            self._connections.clear()
            self._user_connections.clear()
            self._instance_connections.clear()
