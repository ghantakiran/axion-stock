"""Configuration for PRD-130: Capacity Planning & Auto-Scaling."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class ResourceType(str, Enum):
    """Types of monitored resources."""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"
    QUEUE_DEPTH = "queue_depth"
    API_CALLS = "api_calls"


class ScalingDirection(str, Enum):
    """Possible scaling directions."""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_ACTION = "no_action"


class ScalingPolicy(str, Enum):
    """Scaling policy types."""

    THRESHOLD = "threshold"
    PREDICTIVE = "predictive"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class CapacityStatus(str, Enum):
    """Overall capacity health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OVER_PROVISIONED = "over_provisioned"
    UNDER_PROVISIONED = "under_provisioned"


# Default thresholds
DEFAULT_WARNING_PCT = 70.0
DEFAULT_CRITICAL_PCT = 90.0
DEFAULT_SCALE_UP_PCT = 80.0
DEFAULT_SCALE_DOWN_PCT = 30.0
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_FORECAST_HORIZON_HOURS = 24
DEFAULT_CHECK_INTERVAL_SECONDS = 60


@dataclass
class ResourceThreshold:
    """Threshold configuration for a resource type."""

    warning_pct: float = DEFAULT_WARNING_PCT
    critical_pct: float = DEFAULT_CRITICAL_PCT
    scale_up_pct: float = DEFAULT_SCALE_UP_PCT
    scale_down_pct: float = DEFAULT_SCALE_DOWN_PCT
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS


@dataclass
class CapacityConfig:
    """Master capacity planning configuration."""

    thresholds: Dict[ResourceType, ResourceThreshold] = field(
        default_factory=lambda: {rt: ResourceThreshold() for rt in ResourceType}
    )
    forecast_horizon_hours: int = DEFAULT_FORECAST_HORIZON_HOURS
    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS
    enable_auto_scaling: bool = False
    max_scaling_actions_per_hour: int = 5
    min_data_points_for_forecast: int = 10
