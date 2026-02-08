"""Audit event models for event sourcing."""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import EventCategory, EventOutcome


@dataclass
class Actor:
    """Represents the entity that performed an action."""

    actor_id: str
    actor_type: str = "user"
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
        }


@dataclass
class Resource:
    """Represents the resource that was acted upon."""

    resource_type: str
    resource_id: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "name": self.name,
        }


@dataclass
class AuditEvent:
    """Immutable audit event representing a significant action."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    actor: Optional[Actor] = None
    action: str = ""
    resource: Optional[Resource] = None
    category: EventCategory = EventCategory.SYSTEM
    details: Dict[str, Any] = field(default_factory=dict)
    outcome: EventOutcome = EventOutcome.SUCCESS
    event_hash: str = ""
    previous_hash: str = ""

    def compute_hash(self, previous_hash: str) -> str:
        """Compute SHA-256 hash for this event in the hash chain.

        hash = SHA-256(previous_hash + event_id + timestamp + action)
        """
        ts_str = self.timestamp.isoformat()
        payload = f"{previous_hash}{self.event_id}{ts_str}{self.action}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor.to_dict() if self.actor else None,
            "action": self.action,
            "resource": self.resource.to_dict() if self.resource else None,
            "category": self.category.value,
            "details": self.details,
            "outcome": self.outcome.value,
            "event_hash": self.event_hash,
            "previous_hash": self.previous_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Deserialize event from dictionary."""
        actor = None
        if data.get("actor"):
            actor = Actor(
                actor_id=data["actor"]["actor_id"],
                actor_type=data["actor"].get("actor_type", "user"),
                ip_address=data["actor"].get("ip_address"),
                session_id=data["actor"].get("session_id"),
            )
        resource = None
        if data.get("resource"):
            resource = Resource(
                resource_type=data["resource"]["resource_type"],
                resource_id=data["resource"]["resource_id"],
                name=data["resource"].get("name"),
            )
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actor=actor,
            action=data["action"],
            resource=resource,
            category=EventCategory(data.get("category", "system")),
            details=data.get("details", {}),
            outcome=EventOutcome(data.get("outcome", "success")),
            event_hash=data.get("event_hash", ""),
            previous_hash=data.get("previous_hash", ""),
        )
