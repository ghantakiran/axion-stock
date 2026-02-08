"""Configuration for audit trail & event sourcing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EventCategory(str, Enum):
    """Categories for audit events."""

    TRADING = "trading"
    CONFIG = "config"
    AUTH = "auth"
    SYSTEM = "system"
    COMPLIANCE = "compliance"


class EventOutcome(str, Enum):
    """Possible outcomes for audited actions."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class RetentionPolicy:
    """Defines how long audit events are retained."""

    category: EventCategory
    retention_days: int = 365
    archive_after_days: int = 90
    compress_after_days: int = 30
    require_approval_to_delete: bool = True

    def is_archivable(self, age_days: int) -> bool:
        """Check if an event of this category should be archived."""
        return age_days >= self.archive_after_days

    def is_expired(self, age_days: int) -> bool:
        """Check if an event of this category has exceeded retention."""
        return age_days >= self.retention_days


@dataclass
class AuditConfig:
    """Master configuration for the audit trail system."""

    enabled: bool = True
    buffer_size: int = 100
    flush_interval_seconds: float = 5.0
    hash_algorithm: str = "sha256"
    genesis_hash: str = "genesis"
    default_retention_days: int = 365
    enable_integrity_checks: bool = True
    log_to_console: bool = False
    categories: List[EventCategory] = field(
        default_factory=lambda: list(EventCategory),
    )
    retention_policies: Dict[str, RetentionPolicy] = field(
        default_factory=dict,
    )

    def get_retention_policy(self, category: EventCategory) -> RetentionPolicy:
        """Get retention policy for a given category."""
        key = category.value
        if key in self.retention_policies:
            return self.retention_policies[key]
        return RetentionPolicy(
            category=category,
            retention_days=self.default_retention_days,
        )
