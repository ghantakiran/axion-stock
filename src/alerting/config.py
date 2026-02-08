"""PRD-114: Notification & Alerting System - Configuration."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert lifecycle status."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCategory(Enum):
    """Alert category classification."""

    SYSTEM = "system"
    TRADING = "trading"
    DATA = "data"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class ChannelType(Enum):
    """Notification delivery channel types."""

    EMAIL = "email"
    SLACK = "slack"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class AlertConfig:
    """Global alerting configuration."""

    default_channels: List[ChannelType] = field(
        default_factory=lambda: [ChannelType.IN_APP]
    )
    aggregation_window_seconds: int = 60
    max_alerts_per_window: int = 100
    enable_escalation: bool = True
    enable_aggregation: bool = True
    dedup_window_seconds: int = 300
