"""PRD-120: Deployment Strategies & Rollback Automation — Configuration."""

import enum
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class DeploymentStrategy(enum.Enum):
    """Deployment strategy types."""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class DeploymentStatus(enum.Enum):
    """Lifecycle status of a deployment."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    VALIDATING = "validating"
    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ValidationStatus(enum.Enum):
    """Status of a validation check."""

    PENDING = "pending"
    PASSING = "passing"
    FAILING = "failing"
    SKIPPED = "skipped"


@dataclass
class DeploymentConfig:
    """Global deployment configuration with sensible defaults."""

    default_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    canary_initial_percent: float = 5.0
    canary_increment_percent: float = 10.0
    validation_timeout_seconds: int = 300
    error_rate_threshold: float = 0.05
    latency_threshold_ms: float = 500.0
    auto_rollback: bool = True
    smoke_test_timeout_seconds: int = 60
    min_healthy_percent: float = 0.9
