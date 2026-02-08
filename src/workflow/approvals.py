"""PRD-127: Workflow Engine & Approval System - Approval Manager."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import ApprovalLevel, TaskStatus


@dataclass
class ApprovalRequest:
    """A request that needs one or more approvals."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    workflow_id: str = ""
    requester: str = ""
    approvers: List[str] = field(default_factory=list)
    level: ApprovalLevel = ApprovalLevel.SINGLE
    status: TaskStatus = TaskStatus.PENDING
    title: str = ""
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None
    decisions: List["ApprovalDecision"] = field(default_factory=list)
    quorum_size: int = 1


@dataclass
class ApprovalDecision:
    """A single approval or rejection decision."""

    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    request_id: str = ""
    approver: str = ""
    action: str = "approve"  # "approve" or "reject"
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalManager:
    """Manages approval workflows with multi-level sign-off."""

    def __init__(self):
        self.requests: Dict[str, ApprovalRequest] = {}
        self.decisions: List[ApprovalDecision] = []

    def create_request(
        self,
        workflow_id: str,
        requester: str,
        level: ApprovalLevel,
        approvers: Optional[List[str]] = None,
        title: str = "",
        description: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        approvers = approvers or []
        context = context or {}

        # Determine quorum based on level
        if level == ApprovalLevel.AUTO:
            quorum = 0
        elif level == ApprovalLevel.SINGLE:
            quorum = 1
        elif level == ApprovalLevel.DUAL:
            quorum = 2
        elif level == ApprovalLevel.COMMITTEE:
            quorum = max(3, (len(approvers) // 2) + 1)
        else:
            quorum = 1

        req = ApprovalRequest(
            workflow_id=workflow_id,
            requester=requester,
            approvers=approvers,
            level=level,
            title=title,
            description=description,
            context=context,
            quorum_size=quorum,
        )

        # Auto-approve if AUTO level
        if level == ApprovalLevel.AUTO:
            req.status = TaskStatus.APPROVED
            req.decided_at = datetime.now(timezone.utc)

        self.requests[req.request_id] = req
        return req

    def approve(self, request_id: str, approver: str, reason: str = "") -> ApprovalDecision:
        """Record an approval decision."""
        req = self.requests.get(request_id)
        if req is None:
            raise ValueError(f"Unknown request: {request_id}")

        if req.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            raise ValueError(f"Request {request_id} is already resolved ({req.status.value})")

        decision = ApprovalDecision(
            request_id=request_id,
            approver=approver,
            action="approve",
            reason=reason,
        )
        req.decisions.append(decision)
        req.status = TaskStatus.IN_PROGRESS
        self.decisions.append(decision)

        # Check quorum
        if self.check_quorum(request_id):
            req.status = TaskStatus.APPROVED
            req.decided_at = datetime.now(timezone.utc)

        return decision

    def reject(self, request_id: str, approver: str, reason: str = "") -> ApprovalDecision:
        """Record a rejection decision."""
        req = self.requests.get(request_id)
        if req is None:
            raise ValueError(f"Unknown request: {request_id}")

        if req.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            raise ValueError(f"Request {request_id} is already resolved ({req.status.value})")

        decision = ApprovalDecision(
            request_id=request_id,
            approver=approver,
            action="reject",
            reason=reason,
        )
        req.decisions.append(decision)
        req.status = TaskStatus.REJECTED
        req.decided_at = datetime.now(timezone.utc)
        self.decisions.append(decision)

        return decision

    def escalate(self, request_id: str, new_approvers: List[str]) -> ApprovalRequest:
        """Escalate a request to additional approvers."""
        req = self.requests.get(request_id)
        if req is None:
            raise ValueError(f"Unknown request: {request_id}")

        for approver in new_approvers:
            if approver not in req.approvers:
                req.approvers.append(approver)

        # Reset to pending if it was in progress
        if req.status == TaskStatus.IN_PROGRESS:
            req.status = TaskStatus.PENDING

        return req

    def check_quorum(self, request_id: str) -> bool:
        """Check if enough approvals have been collected."""
        req = self.requests.get(request_id)
        if req is None:
            return False

        if req.level == ApprovalLevel.AUTO:
            return True

        approval_count = sum(1 for d in req.decisions if d.action == "approve")
        return approval_count >= req.quorum_size

    def get_pending_approvals(self, approver: Optional[str] = None) -> List[ApprovalRequest]:
        """Return pending approval requests, optionally filtered by approver."""
        pending = [
            r for r in self.requests.values()
            if r.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ]
        if approver:
            pending = [r for r in pending if approver in r.approvers]
        return pending

    def get_decision_history(self, request_id: Optional[str] = None) -> List[ApprovalDecision]:
        """Return decision history, optionally filtered by request."""
        if request_id:
            return [d for d in self.decisions if d.request_id == request_id]
        return list(self.decisions)
