"""PRD-114: Notification & Alerting System."""

from .config import (
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    ChannelType,
    AlertConfig,
)
from .manager import Alert, AlertManager
from .routing import RoutingRule, RoutingEngine
from .escalation import EscalationLevel, EscalationPolicy, EscalationManager
from .aggregation import AlertDigest, AlertAggregator
from .channels import DeliveryResult, ChannelDispatcher

__all__ = [
    # Config
    "AlertSeverity",
    "AlertStatus",
    "AlertCategory",
    "ChannelType",
    "AlertConfig",
    # Manager
    "Alert",
    "AlertManager",
    # Routing
    "RoutingRule",
    "RoutingEngine",
    # Escalation
    "EscalationLevel",
    "EscalationPolicy",
    "EscalationManager",
    # Aggregation
    "AlertDigest",
    "AlertAggregator",
    # Channels
    "DeliveryResult",
    "ChannelDispatcher",
]
