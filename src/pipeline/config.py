"""PRD-112: Data Pipeline Orchestration — Configuration."""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """Status of an entire pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class NodeStatus(Enum):
    """Status of an individual pipeline node."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ScheduleType(Enum):
    """Schedule type for pipeline execution."""

    ONCE = "once"
    RECURRING = "recurring"
    CRON = "cron"
    MARKET_HOURS = "market_hours"


@dataclass
class PipelineConfig:
    """Configuration for the pipeline execution engine."""

    max_parallel_nodes: int = 4
    default_timeout_seconds: int = 300
    default_retries: int = 3
    retry_backoff_base: float = 2.0
    enable_lineage: bool = True
    enable_monitoring: bool = True


@dataclass
class SLAConfig:
    """Service-level agreement configuration for a pipeline."""

    max_duration_seconds: float = 600.0
    max_failure_rate: float = 0.1
    min_data_freshness_seconds: float = 3600.0
