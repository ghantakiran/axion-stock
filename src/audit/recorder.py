"""Audit event recorder with hash chain integrity."""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import AuditConfig, EventCategory, EventOutcome
from .events import Actor, AuditEvent, Resource

logger = logging.getLogger(__name__)

_recorder_instance: Optional["AuditRecorder"] = None
_recorder_lock = threading.Lock()


class AuditRecorder:
    """Thread-safe audit event recorder with hash chain integrity.

    Uses singleton pattern for global access. Events are buffered
    in memory and flushed based on buffer size configuration.
    """

    def __init__(self, config: Optional[AuditConfig] = None) -> None:
        self._config = config or AuditConfig()
        self._events: List[AuditEvent] = []
        self._buffer: List[AuditEvent] = []
        self._last_hash: str = self._config.genesis_hash
        self._lock = threading.Lock()
        self._event_count: int = 0

    @classmethod
    def get_instance(cls, config: Optional[AuditConfig] = None) -> "AuditRecorder":
        """Get or create the singleton recorder instance."""
        global _recorder_instance
        with _recorder_lock:
            if _recorder_instance is None:
                _recorder_instance = cls(config)
            return _recorder_instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        global _recorder_instance
        with _recorder_lock:
            _recorder_instance = None

    @property
    def config(self) -> AuditConfig:
        return self._config

    @property
    def events(self) -> List[AuditEvent]:
        """Return all committed events."""
        with self._lock:
            return list(self._events)

    @property
    def buffer(self) -> List[AuditEvent]:
        """Return current buffer contents."""
        with self._lock:
            return list(self._buffer)

    @property
    def event_count(self) -> int:
        """Total number of events (committed + buffered)."""
        with self._lock:
            return len(self._events) + len(self._buffer)

    @property
    def last_hash(self) -> str:
        """Return the most recent hash in the chain."""
        with self._lock:
            return self._last_hash

    def record(
        self,
        action: str,
        actor: Optional[Actor] = None,
        resource: Optional[Resource] = None,
        category: EventCategory = EventCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        outcome: EventOutcome = EventOutcome.SUCCESS,
        event_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEvent:
        """Record a new audit event with hash chain integrity.

        Args:
            action: The action performed (e.g., "order.create").
            actor: The entity that performed the action.
            resource: The resource acted upon.
            category: Event category for classification.
            details: Additional event details.
            outcome: The outcome of the action.
            event_id: Optional custom event ID.
            timestamp: Optional custom timestamp.

        Returns:
            The recorded AuditEvent with computed hash.
        """
        if not self._config.enabled:
            logger.debug("Audit recording disabled, skipping event")
            return AuditEvent(action=action)

        with self._lock:
            event = AuditEvent(
                action=action,
                actor=actor,
                resource=resource,
                category=category,
                details=details or {},
                outcome=outcome,
            )
            if event_id:
                event.event_id = event_id
            if timestamp:
                event.timestamp = timestamp

            # Compute hash chain
            event.previous_hash = self._last_hash
            event.event_hash = event.compute_hash(self._last_hash)
            self._last_hash = event.event_hash

            # Add to buffer
            self._buffer.append(event)
            self._event_count += 1

            logger.debug(
                "Recorded audit event: %s [%s] hash=%s",
                event.action,
                event.category.value,
                event.event_hash[:12],
            )

            # Auto-flush if buffer is full
            if len(self._buffer) >= self._config.buffer_size:
                self._flush_unlocked()

            return event

    def flush(self) -> int:
        """Flush the buffer, moving events to committed storage.

        Returns:
            Number of events flushed.
        """
        with self._lock:
            return self._flush_unlocked()

    def _flush_unlocked(self) -> int:
        """Internal flush without acquiring lock (caller must hold lock)."""
        count = len(self._buffer)
        if count > 0:
            self._events.extend(self._buffer)
            self._buffer.clear()
            logger.debug("Flushed %d audit events to storage", count)
        return count

    def get_all_events(self) -> List[AuditEvent]:
        """Return all events (committed + buffered)."""
        with self._lock:
            return list(self._events) + list(self._buffer)

    def verify_integrity(self) -> bool:
        """Verify the hash chain integrity of all events.

        Returns:
            True if the chain is intact, False if tampered.
        """
        all_events = self.get_all_events()
        if not all_events:
            return True

        previous_hash = self._config.genesis_hash
        for event in all_events:
            expected_hash = event.compute_hash(previous_hash)
            if event.event_hash != expected_hash:
                logger.error(
                    "Hash chain broken at event %s: expected=%s, got=%s",
                    event.event_id,
                    expected_hash[:12],
                    event.event_hash[:12],
                )
                return False
            if event.previous_hash != previous_hash:
                logger.error(
                    "Previous hash mismatch at event %s",
                    event.event_id,
                )
                return False
            previous_hash = event.event_hash

        return True

    def find_tampering(self) -> List[Dict[str, Any]]:
        """Find specific events where the hash chain is broken.

        Returns:
            List of dicts describing each broken link.
        """
        all_events = self.get_all_events()
        issues: List[Dict[str, Any]] = []

        if not all_events:
            return issues

        previous_hash = self._config.genesis_hash
        for idx, event in enumerate(all_events):
            expected_hash = event.compute_hash(previous_hash)
            if event.event_hash != expected_hash:
                issues.append({
                    "index": idx,
                    "event_id": event.event_id,
                    "expected_hash": expected_hash,
                    "actual_hash": event.event_hash,
                    "type": "hash_mismatch",
                })
            if event.previous_hash != previous_hash:
                issues.append({
                    "index": idx,
                    "event_id": event.event_id,
                    "expected_previous": previous_hash,
                    "actual_previous": event.previous_hash,
                    "type": "chain_break",
                })
            previous_hash = event.event_hash

        return issues

    def clear(self) -> None:
        """Clear all events (for testing)."""
        with self._lock:
            self._events.clear()
            self._buffer.clear()
            self._last_hash = self._config.genesis_hash
            self._event_count = 0
