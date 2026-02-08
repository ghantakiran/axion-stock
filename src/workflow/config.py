"""PRD-127: Workflow Engine & Approval System - Configuration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class WorkflowStatus(Enum):
    """Workflow instance status."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TaskStatus(Enum):
    """Individual task / step status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class ApprovalLevel(Enum):
    """Approval requirement level."""

    SINGLE = "single"
    DUAL = "dual"
    COMMITTEE = "committee"
    AUTO = "auto"


class TriggerType(Enum):
    """Workflow trigger mechanism."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    THRESHOLD = "threshold"


@dataclass
class WorkflowConfig:
    """Configuration for a workflow instance."""

    name: str = "default_workflow"
    states: List[str] = field(default_factory=lambda: ["start", "end"])
    transitions: List[str] = field(default_factory=list)
    timeout_seconds: int = 3600
    auto_escalate: bool = False
    max_retries: int = 3
    trigger_type: TriggerType = TriggerType.MANUAL
    approval_level: ApprovalLevel = ApprovalLevel.SINGLE
    notify_on_transition: bool = True
    require_comment: bool = False
