"""PRD-124: Secrets Management & API Credential Vaulting - Access Control."""

import fnmatch
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .config import AccessAction


@dataclass
class AccessPolicy:
    """Policy granting access to secrets matching a path pattern."""

    policy_id: str
    subject_id: str
    path_pattern: str
    allowed_actions: List[AccessAction]
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""


@dataclass
class AccessAuditEntry:
    """Audit log entry for secret access attempts."""

    entry_id: str
    secret_id: str
    requester_id: str
    action: AccessAction
    allowed: bool
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: str = ""


class AccessControl:
    """Fine-grained access control with path-based policies and audit logging.

    Implements deny-by-default with explicit grants via glob patterns.
    """

    def __init__(self):
        self._policies: Dict[str, AccessPolicy] = {}
        self._audit_log: List[AccessAuditEntry] = []

    # ── Policy Management ─────────────────────────────────────────────

    def grant(
        self,
        subject_id: str,
        path_pattern: str,
        actions: List[AccessAction],
        expires_at: Optional[datetime] = None,
        description: str = "",
    ) -> AccessPolicy:
        """Grant access to secrets matching a path pattern."""
        policy_id = uuid.uuid4().hex[:16]

        policy = AccessPolicy(
            policy_id=policy_id,
            subject_id=subject_id,
            path_pattern=path_pattern,
            allowed_actions=actions,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            description=description,
        )

        self._policies[policy_id] = policy
        return policy

    def revoke(self, policy_id: str) -> bool:
        """Revoke an access policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def revoke_all(self, subject_id: str) -> int:
        """Revoke all policies for a subject."""
        to_remove = [
            pid for pid, p in self._policies.items() if p.subject_id == subject_id
        ]
        for pid in to_remove:
            del self._policies[pid]
        return len(to_remove)

    # ── Access Checking ───────────────────────────────────────────────

    def check_access(
        self,
        subject_id: str,
        key_path: str,
        action: AccessAction,
        secret_id: str = "",
        ip_address: str = "",
    ) -> bool:
        """Check if a subject has access to perform an action on a secret path.

        Deny-by-default: access is only granted if an active, non-expired
        policy exists with a matching path pattern and action.
        """
        now = datetime.now(timezone.utc)
        allowed = False
        reason = "no matching policy"

        for policy in self._policies.values():
            if policy.subject_id != subject_id:
                continue
            # Check expiration
            if policy.expires_at and policy.expires_at < now:
                continue
            # Check path pattern match
            if not fnmatch.fnmatch(key_path, policy.path_pattern):
                continue
            # Check action
            if action in policy.allowed_actions:
                allowed = True
                reason = f"granted by policy {policy.policy_id}"
                break

        # Log the access attempt
        audit_entry = AccessAuditEntry(
            entry_id=uuid.uuid4().hex[:16],
            secret_id=secret_id,
            requester_id=subject_id,
            action=action,
            allowed=allowed,
            reason=reason,
            timestamp=now,
            ip_address=ip_address,
        )
        self._audit_log.append(audit_entry)

        return allowed

    # ── Policy Queries ────────────────────────────────────────────────

    def list_policies(self, subject_id: Optional[str] = None) -> List[AccessPolicy]:
        """List access policies, optionally filtered by subject."""
        policies = list(self._policies.values())
        if subject_id:
            policies = [p for p in policies if p.subject_id == subject_id]
        return policies

    def get_effective_permissions(
        self, subject_id: str, key_path: str
    ) -> Set[AccessAction]:
        """Get all effective permissions for a subject on a path."""
        now = datetime.now(timezone.utc)
        permissions: Set[AccessAction] = set()

        for policy in self._policies.values():
            if policy.subject_id != subject_id:
                continue
            if policy.expires_at and policy.expires_at < now:
                continue
            if fnmatch.fnmatch(key_path, policy.path_pattern):
                permissions.update(policy.allowed_actions)

        return permissions

    # ── Audit Log ─────────────────────────────────────────────────────

    def get_audit_log(
        self,
        subject_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        action: Optional[AccessAction] = None,
        limit: int = 100,
    ) -> List[AccessAuditEntry]:
        """Get audit log entries with optional filtering."""
        entries = list(self._audit_log)

        if subject_id:
            entries = [e for e in entries if e.requester_id == subject_id]
        if secret_id:
            entries = [e for e in entries if e.secret_id == secret_id]
        if action:
            entries = [e for e in entries if e.action == action]

        return entries[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get access control statistics."""
        total_policies = len(self._policies)
        total_audit = len(self._audit_log)
        allowed_count = sum(1 for e in self._audit_log if e.allowed)
        denied_count = total_audit - allowed_count

        now = datetime.now(timezone.utc)
        expired_policies = sum(
            1
            for p in self._policies.values()
            if p.expires_at and p.expires_at < now
        )

        subjects: Set[str] = {p.subject_id for p in self._policies.values()}

        by_action: Dict[str, int] = {}
        for entry in self._audit_log:
            a = entry.action.value
            by_action[a] = by_action.get(a, 0) + 1

        return {
            "total_policies": total_policies,
            "expired_policies": expired_policies,
            "active_policies": total_policies - expired_policies,
            "unique_subjects": len(subjects),
            "total_audit_entries": total_audit,
            "allowed_requests": allowed_count,
            "denied_requests": denied_count,
            "by_action": by_action,
        }
