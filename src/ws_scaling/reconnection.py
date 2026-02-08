"""Reconnection session management for WebSocket connections."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import WSScalingConfig
from .router import Message

logger = logging.getLogger(__name__)


@dataclass
class ReconnectionSession:
    """Tracks a single reconnection attempt for a dropped WebSocket connection."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    original_connection_id: str = ""
    attempt_count: int = 0
    max_attempts: int = 5
    last_attempt_at: Optional[datetime] = None
    reconnected_at: Optional[datetime] = None
    missed_messages: List[Message] = field(default_factory=list)
    state: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)


class ReconnectionManager:
    """Manages reconnection sessions and buffers messages for disconnected clients.

    When a connection drops, a session is opened.  Messages that arrive while
    the session is pending are buffered so they can be replayed once the client
    reconnects.
    """

    def __init__(self, config: Optional[WSScalingConfig] = None):
        self._config = config or WSScalingConfig()
        self._sessions: Dict[str, ReconnectionSession] = {}
        self._message_buffer: Dict[str, List[Message]] = {}
        self._lock = threading.Lock()

    def start_session(self, user_id: str, connection_id: str) -> ReconnectionSession:
        """Create a new reconnection session for a dropped connection."""
        with self._lock:
            session = ReconnectionSession(
                user_id=user_id,
                original_connection_id=connection_id,
                max_attempts=self._config.max_reconnection_attempts,
                state="pending",
            )
            self._sessions[session.session_id] = session
            self._message_buffer[connection_id] = []

            logger.info(
                "Started reconnection session %s for user=%s conn=%s",
                session.session_id,
                user_id,
                connection_id,
            )
            return session

    def attempt_reconnect(
        self, session_id: str, new_connection_id: str
    ) -> Dict:
        """Attempt to reconnect using an existing session.

        Returns a dict with keys ``success`` (bool) and ``missed_message_count`` (int).
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return {"success": False, "missed_message_count": 0}

            session.attempt_count += 1
            session.last_attempt_at = datetime.utcnow()

            if session.state != "pending":
                return {"success": False, "missed_message_count": 0}

            if session.attempt_count > session.max_attempts:
                session.state = "failed"
                logger.warning(
                    "Reconnection session %s exceeded max attempts", session_id
                )
                return {"success": False, "missed_message_count": 0}

            # Gather missed messages from the buffer
            buffered = self._message_buffer.pop(session.original_connection_id, [])
            session.missed_messages = buffered
            session.reconnected_at = datetime.utcnow()
            session.state = "reconnected"

            logger.info(
                "Reconnection session %s succeeded with %d missed messages",
                session_id,
                len(buffered),
            )
            return {"success": True, "missed_message_count": len(buffered)}

    def buffer_message(self, connection_id: str, message: Message) -> None:
        """Buffer a message for a disconnected connection.

        Only buffers if there is an active message buffer (i.e. a reconnection
        session has been started for the connection).
        """
        with self._lock:
            if connection_id in self._message_buffer:
                buf = self._message_buffer[connection_id]
                if len(buf) < self._config.message_buffer_size:
                    buf.append(message)

    def get_missed_messages(self, session_id: str) -> List[Message]:
        """Return the list of missed messages captured during reconnection."""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return list(session.missed_messages)

    def get_session(self, session_id: str) -> Optional[ReconnectionSession]:
        """Retrieve a reconnection session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[ReconnectionSession]:
        """List sessions, optionally filtered by user and/or state."""
        results: List[ReconnectionSession] = []
        for session in self._sessions.values():
            if user_id and session.user_id != user_id:
                continue
            if state and session.state != state:
                continue
            results.append(session)
        return results

    def expire_sessions(self, timeout_seconds: Optional[int] = None) -> int:
        """Expire stale pending sessions older than *timeout_seconds*.

        Uses the earliest meaningful timestamp to determine session age:
        1. ``last_attempt_at`` if any reconnection attempt has been made.
        2. The timestamp of the oldest buffered message for the connection.
        3. The session ``created_at`` timestamp as a final fallback.

        Returns the number of sessions expired.
        """
        timeout = timeout_seconds or self._config.reconnection_window_seconds
        now = datetime.utcnow()
        expired = 0

        with self._lock:
            for session in list(self._sessions.values()):
                if session.state != "pending":
                    continue

                # Determine reference time for age calculation
                ref_time = session.last_attempt_at
                if ref_time is None:
                    buf = self._message_buffer.get(session.original_connection_id, [])
                    if buf:
                        ref_time = buf[0].timestamp
                    else:
                        ref_time = session.created_at

                age = (now - ref_time).total_seconds()
                if age > timeout:
                    session.state = "expired"
                    self._message_buffer.pop(session.original_connection_id, None)
                    expired += 1
                    logger.info("Expired reconnection session %s", session.session_id)

        return expired

    def can_reconnect(self, session_id: str) -> bool:
        """Check whether a session still has reconnection attempts remaining."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if session.state != "pending":
            return False
        return session.attempt_count < session.max_attempts

    def get_reconnection_stats(self) -> Dict:
        """Aggregate statistics across all sessions."""
        total = len(self._sessions)
        successful = sum(1 for s in self._sessions.values() if s.state == "reconnected")
        failed = sum(
            1 for s in self._sessions.values() if s.state in ("failed", "expired")
        )
        attempts = [s.attempt_count for s in self._sessions.values() if s.attempt_count > 0]
        avg_attempts = sum(attempts) / len(attempts) if attempts else 0.0

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "pending": total - successful - failed,
            "avg_attempts": avg_attempts,
        }

    def reset(self) -> None:
        """Clear all sessions and buffers."""
        with self._lock:
            self._sessions.clear()
            self._message_buffer.clear()
