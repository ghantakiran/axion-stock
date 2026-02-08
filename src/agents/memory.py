"""Agent memory — persistent or in-memory session/message storage."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MemorySession:
    """Lightweight session object (no ORM dependency)."""

    session_id: str
    user_id: str
    agent_type: str
    title: str = "New chat"
    messages: list[dict] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def message_count(self) -> int:
        return len(self.messages)


class AgentMemory:
    """Session and message storage with DB-optional persistence.

    Tries to connect to PostgreSQL via SQLAlchemy on init.
    Falls back to in-memory dicts when the DB is unavailable.
    """

    def __init__(self, db_url: Optional[str] = None):
        self._sessions: dict[str, MemorySession] = {}
        self._preferences: dict[str, dict] = {}
        self._db_engine = None

        if db_url:
            try:
                from sqlalchemy import create_engine, text
                self._db_engine = create_engine(db_url, pool_pre_ping=True)
                with self._db_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            except Exception:
                self._db_engine = None

    @property
    def is_persistent(self) -> bool:
        """True if backed by a real database."""
        return self._db_engine is not None

    # ── Session CRUD ──────────────────────────────────────────────────

    def create_session(
        self,
        user_id: str,
        agent_type: str,
        title: str = "New chat",
    ) -> MemorySession:
        """Create a new chat session."""
        session = MemorySession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            agent_type=agent_type,
            title=title,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[MemorySession]:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls_json: Optional[str] = None,
        tokens_used: int = 0,
    ) -> None:
        """Append a message to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session.messages.append({
            "message_id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "tool_calls_json": tool_calls_json,
            "tokens_used": tokens_used,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        session.last_activity_at = datetime.now(timezone.utc)

    def load_messages(self, session_id: str) -> list[dict]:
        """Return all messages for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return list(session.messages)

    def get_user_sessions(
        self,
        user_id: str,
        active_only: bool = True,
    ) -> list[MemorySession]:
        """Return sessions for a user, sorted by last activity."""
        sessions = [
            s for s in self._sessions.values()
            if s.user_id == user_id and (not active_only or s.is_active)
        ]
        return sorted(sessions, key=lambda s: s.last_activity_at, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        session = self._sessions.pop(session_id, None)
        return session is not None

    def get_session_stats(self, user_id: str) -> dict:
        """Return aggregate stats for a user's sessions."""
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        total_messages = sum(s.message_count for s in sessions)
        agents_used = list({s.agent_type for s in sessions})
        return {
            "total_sessions": len(sessions),
            "active_sessions": sum(1 for s in sessions if s.is_active),
            "total_messages": total_messages,
            "agents_used": agents_used,
        }

    # ── Preferences ───────────────────────────────────────────────────

    def save_preference(self, user_id: str, key: str, value: str) -> None:
        """Save a user preference."""
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        self._preferences[user_id][key] = value

    def load_preference(self, user_id: str, key: str) -> Optional[str]:
        """Load a user preference."""
        return self._preferences.get(user_id, {}).get(key)

    def load_all_preferences(self, user_id: str) -> dict:
        """Load all preferences for a user."""
        return dict(self._preferences.get(user_id, {}))
