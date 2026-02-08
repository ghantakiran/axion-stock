"""PRD-121: Event-Driven Architecture — Event Schema.

Versioned event definitions with validation and schema registry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import EventCategory, EventPriority


@dataclass
class EventEnvelope:
    """Standard event envelope wrapping all events."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: str = ""
    category: EventCategory = EventCategory.SYSTEM
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    data: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaDefinition:
    """Schema definition for event validation."""

    schema_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: str = ""
    version: int = 1
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    description: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class SchemaRegistry:
    """Registry for event schemas with version management."""

    def __init__(self) -> None:
        self._schemas: dict[str, dict[int, SchemaDefinition]] = {}

    def register(self, schema: SchemaDefinition) -> SchemaDefinition:
        """Register a schema definition."""
        if schema.event_type not in self._schemas:
            self._schemas[schema.event_type] = {}
        self._schemas[schema.event_type][schema.version] = schema
        return schema

    def get_schema(
        self, event_type: str, version: Optional[int] = None,
    ) -> Optional[SchemaDefinition]:
        """Get a schema by type and optional version (latest if None)."""
        versions = self._schemas.get(event_type)
        if not versions:
            return None
        if version is not None:
            return versions.get(version)
        latest_ver = max(versions.keys())
        return versions[latest_ver]

    def validate_event(self, event: EventEnvelope) -> dict[str, Any]:
        """Validate an event against its registered schema."""
        schema = self.get_schema(event.event_type, event.version)
        if schema is None:
            return {"valid": True, "schema": None, "errors": []}

        errors: list[str] = []
        for req_field in schema.required_fields:
            if req_field not in event.data:
                errors.append(f"Missing required field: {req_field}")

        return {
            "valid": len(errors) == 0,
            "schema": schema.schema_id,
            "errors": errors,
        }

    def list_schemas(self) -> list[SchemaDefinition]:
        """List all registered schemas (latest version of each)."""
        result: list[SchemaDefinition] = []
        for versions in self._schemas.values():
            latest_ver = max(versions.keys())
            result.append(versions[latest_ver])
        return result

    def get_versions(self, event_type: str) -> list[int]:
        """Get all versions for an event type."""
        versions = self._schemas.get(event_type, {})
        return sorted(versions.keys())

    def is_compatible(
        self, event_type: str, old_version: int, new_version: int,
    ) -> bool:
        """Check if new version is backward compatible (all old required fields present)."""
        old_schema = self.get_schema(event_type, old_version)
        new_schema = self.get_schema(event_type, new_version)
        if old_schema is None or new_schema is None:
            return False
        old_required = set(old_schema.required_fields)
        new_required = set(new_schema.required_fields)
        # Backward compatible if new version has all old required fields
        return old_required.issubset(new_required | set(new_schema.optional_fields))


# ── Built-in Event Factories ──────────────────────────────────────


def order_executed_event(
    order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    source: str = "execution_engine",
    **extra: Any,
) -> EventEnvelope:
    """Create an OrderExecuted event."""
    return EventEnvelope(
        event_type="OrderExecuted",
        category=EventCategory.ORDER,
        source=source,
        priority=EventPriority.HIGH,
        data={
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            **extra,
        },
    )


def alert_triggered_event(
    alert_id: str,
    severity: str,
    message: str,
    source: str = "alerting",
    **extra: Any,
) -> EventEnvelope:
    """Create an AlertTriggered event."""
    return EventEnvelope(
        event_type="AlertTriggered",
        category=EventCategory.ALERT,
        source=source,
        priority=EventPriority.HIGH if severity == "critical" else EventPriority.NORMAL,
        data={
            "alert_id": alert_id,
            "severity": severity,
            "message": message,
            **extra,
        },
    )


def model_updated_event(
    model_id: str,
    model_name: str,
    new_version: str,
    source: str = "model_registry",
    **extra: Any,
) -> EventEnvelope:
    """Create a ModelUpdated event."""
    return EventEnvelope(
        event_type="ModelUpdated",
        category=EventCategory.MODEL,
        source=source,
        priority=EventPriority.NORMAL,
        data={
            "model_id": model_id,
            "model_name": model_name,
            "new_version": new_version,
            **extra,
        },
    )


def compliance_violation_event(
    violation_id: str,
    rule: str,
    details: str,
    source: str = "compliance_engine",
    **extra: Any,
) -> EventEnvelope:
    """Create a ComplianceViolation event."""
    return EventEnvelope(
        event_type="ComplianceViolation",
        category=EventCategory.COMPLIANCE,
        source=source,
        priority=EventPriority.CRITICAL,
        data={
            "violation_id": violation_id,
            "rule": rule,
            "details": details,
            **extra,
        },
    )
