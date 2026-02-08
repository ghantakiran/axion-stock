"""Message routing for WebSocket channels."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .config import MessagePriority

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A routable WebSocket message."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: str = ""
    payload: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sender_id: Optional[str] = None
    target_connection_ids: Optional[List[str]] = None


class MessageRouter:
    """Routes messages to subscribers on named channels.

    Supports broadcast (all subscribers on a channel), unicast (single connection),
    and multicast (explicit set of connections).  Maintains a message log for
    auditing / replay.
    """

    def __init__(self):
        self._channels: Dict[str, Set[str]] = {}
        self._message_log: List[Message] = []
        self._lock = threading.Lock()

    def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe a connection to a channel. Returns True if newly added."""
        with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            if connection_id in self._channels[channel]:
                return False
            self._channels[channel].add(connection_id)
            logger.debug("Connection %s subscribed to %s", connection_id, channel)
            return True

    def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel. Returns True if was present."""
        with self._lock:
            subs = self._channels.get(channel)
            if subs and connection_id in subs:
                subs.discard(connection_id)
                if not subs:
                    del self._channels[channel]
                return True
            return False

    def get_subscribers(self, channel: str) -> Set[str]:
        """Return the set of connection IDs subscribed to a channel."""
        return set(self._channels.get(channel, set()))

    def route_message(self, message: Message) -> int:
        """Determine target connections for *message* and return the count.

        If ``target_connection_ids`` is already set on the message, that list
        is used directly.  Otherwise, the message is routed to all subscribers
        of its channel.
        """
        if message.target_connection_ids is not None:
            count = len(message.target_connection_ids)
        else:
            subs = self.get_subscribers(message.channel)
            message.target_connection_ids = list(subs)
            count = len(subs)

        with self._lock:
            self._message_log.append(message)

        logger.debug(
            "Routed message %s to %d connections on channel=%s",
            message.message_id,
            count,
            message.channel,
        )
        return count

    def broadcast(
        self,
        channel: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        sender_id: Optional[str] = None,
    ) -> Message:
        """Create and route a broadcast message to all subscribers of *channel*."""
        msg = Message(
            channel=channel,
            payload=payload,
            priority=priority,
            sender_id=sender_id,
        )
        self.route_message(msg)
        return msg

    def unicast(
        self,
        connection_id: str,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        sender_id: Optional[str] = None,
    ) -> Message:
        """Create and route a message to a single connection."""
        msg = Message(
            channel="__unicast__",
            payload=payload,
            priority=priority,
            sender_id=sender_id,
            target_connection_ids=[connection_id],
        )
        self.route_message(msg)
        return msg

    def multicast(
        self,
        connection_ids: List[str],
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        sender_id: Optional[str] = None,
    ) -> Message:
        """Create and route a message to an explicit set of connections."""
        msg = Message(
            channel="__multicast__",
            payload=payload,
            priority=priority,
            sender_id=sender_id,
            target_connection_ids=list(connection_ids),
        )
        self.route_message(msg)
        return msg

    def get_channel_stats(self) -> Dict[str, int]:
        """Return a mapping of channel -> subscriber count."""
        return {ch: len(subs) for ch, subs in self._channels.items()}

    def get_message_log(
        self, channel: Optional[str] = None, limit: int = 100
    ) -> List[Message]:
        """Return recent messages, optionally filtered by channel."""
        with self._lock:
            if channel:
                filtered = [m for m in self._message_log if m.channel == channel]
            else:
                filtered = list(self._message_log)
        return filtered[-limit:]

    def reset(self) -> None:
        """Clear all channels and message log."""
        with self._lock:
            self._channels.clear()
            self._message_log.clear()
