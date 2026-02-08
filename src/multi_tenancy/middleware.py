"""Data isolation middleware for multi-tenancy."""

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .config import TenancyConfig
from .context import TenantContext, TenantContextManager


@dataclass
class RateLimitState:
    """Tracks rate limiting state for a workspace."""

    workspace_id: str = ""
    request_timestamps: List[float] = field(default_factory=list)
    total_requests: int = 0
    total_blocked: int = 0

    def record_request(self) -> None:
        """Record a new request timestamp."""
        self.request_timestamps.append(time.time())
        self.total_requests += 1

    def count_in_window(self, window_seconds: int) -> int:
        """Count requests within the rate limit window."""
        now = time.time()
        cutoff = now - window_seconds
        # Prune old entries
        self.request_timestamps = [t for t in self.request_timestamps if t > cutoff]
        return len(self.request_timestamps)


@dataclass
class MiddlewareAuditEntry:
    """Audit entry for middleware actions."""

    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    workspace_id: str = ""
    user_id: str = ""
    action: str = ""
    ip_address: str = ""
    allowed: bool = True
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DataIsolationMiddleware:
    """Middleware for establishing tenant context and enforcing data isolation.

    This middleware:
    - Extracts workspace_id, user_id, and roles from JWT claims
    - Establishes a TenantContext for the request
    - Detects and blocks cross-tenant requests
    - Enforces IP-based workspace restrictions
    - Applies per-workspace rate limiting
    """

    def __init__(
        self,
        config: Optional[TenancyConfig] = None,
        context_manager: Optional[TenantContextManager] = None,
    ):
        self.config = config or TenancyConfig()
        self.context_manager = context_manager or TenantContextManager()
        self._rate_limits: Dict[str, RateLimitState] = {}
        self._ip_workspace_map: Dict[str, Set[str]] = defaultdict(set)
        self._audit_log: List[MiddlewareAuditEntry] = []
        self._workspace_ip_whitelist: Dict[str, Set[str]] = {}

    def process_request(
        self,
        headers: Dict[str, str],
        ip_address: str = "127.0.0.1",
    ) -> Tuple[bool, Optional[TenantContext], str]:
        """Process an incoming request to establish tenant context.

        Extracts JWT claims, validates workspace access, applies rate limiting
        and IP restrictions.

        Args:
            headers: Request headers containing JWT claims.
            ip_address: Client IP address.

        Returns:
            Tuple of (allowed, context_or_none, reason_message).
        """
        if not self.config.enabled:
            return True, None, "Multi-tenancy disabled"

        # Extract claims from headers (simulating JWT extraction)
        workspace_id = headers.get("X-Workspace-ID", "")
        user_id = headers.get("X-User-ID", "")
        roles_str = headers.get("X-User-Roles", "")
        roles = [r.strip() for r in roles_str.split(",") if r.strip()] if roles_str else []

        # Validate required claims
        if not workspace_id:
            self._log_audit("", "", "missing_workspace", ip_address, False, "Missing workspace ID")
            return False, None, "Missing X-Workspace-ID header"

        if not user_id:
            self._log_audit(workspace_id, "", "missing_user", ip_address, False, "Missing user ID")
            return False, None, "Missing X-User-ID header"

        # IP-based workspace restrictions
        if self.config.ip_restriction_enabled:
            allowed, reason = self._check_ip_restriction(workspace_id, ip_address)
            if not allowed:
                self._log_audit(workspace_id, user_id, "ip_blocked", ip_address, False, reason)
                return False, None, reason

        # Track IP-to-workspace mapping
        self._ip_workspace_map[ip_address].add(workspace_id)
        if len(self._ip_workspace_map[ip_address]) > self.config.max_workspaces_per_ip:
            reason = (
                f"IP {ip_address} accessing too many workspaces "
                f"({len(self._ip_workspace_map[ip_address])} > {self.config.max_workspaces_per_ip})"
            )
            self._log_audit(workspace_id, user_id, "ip_workspace_limit", ip_address, False, reason)
            return False, None, reason

        # Rate limiting
        allowed, reason = self._check_rate_limit(workspace_id)
        if not allowed:
            self._log_audit(workspace_id, user_id, "rate_limited", ip_address, False, reason)
            return False, None, reason

        # Cross-tenant detection: check if thread already has a different workspace
        existing_ctx = self.context_manager.get_context()
        if existing_ctx and existing_ctx.workspace_id != workspace_id:
            if self.config.block_cross_tenant_requests:
                reason = (
                    f"Cross-tenant request detected: existing context workspace "
                    f"'{existing_ctx.workspace_id}', request workspace '{workspace_id}'"
                )
                self._log_audit(workspace_id, user_id, "cross_tenant_blocked", ip_address, False, reason)
                return False, None, reason

        # Build and set context
        context = TenantContext(
            workspace_id=workspace_id,
            user_id=user_id,
            roles=roles,
            ip_address=ip_address,
        )
        self.context_manager.set_context(context)

        self._log_audit(workspace_id, user_id, "context_established", ip_address, True, "OK")
        return True, context, "OK"

    def cleanup_request(self) -> None:
        """Clean up tenant context after request processing."""
        self.context_manager.clear_context()

    def set_workspace_ip_whitelist(self, workspace_id: str, allowed_ips: Set[str]) -> None:
        """Set allowed IPs for a workspace.

        Args:
            workspace_id: The workspace to restrict.
            allowed_ips: Set of allowed IP addresses.
        """
        self._workspace_ip_whitelist[workspace_id] = set(allowed_ips)

    def get_rate_limit_state(self, workspace_id: str) -> Optional[RateLimitState]:
        """Get the current rate limit state for a workspace.

        Args:
            workspace_id: The workspace to check.

        Returns:
            RateLimitState or None.
        """
        return self._rate_limits.get(workspace_id)

    def get_audit_log(self) -> List[MiddlewareAuditEntry]:
        """Return the middleware audit log."""
        return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """Clear the middleware audit log."""
        self._audit_log.clear()

    def get_ip_workspace_count(self, ip_address: str) -> int:
        """Get the number of workspaces accessed from an IP.

        Args:
            ip_address: The IP address to check.

        Returns:
            Number of distinct workspaces accessed from this IP.
        """
        return len(self._ip_workspace_map.get(ip_address, set()))

    def get_stats(self) -> Dict[str, Any]:
        """Get middleware statistics.

        Returns:
            Dictionary with middleware stats.
        """
        total = len(self._audit_log)
        allowed = sum(1 for e in self._audit_log if e.allowed)
        blocked = total - allowed
        actions = {}
        for entry in self._audit_log:
            actions[entry.action] = actions.get(entry.action, 0) + 1

        return {
            "total_requests": total,
            "allowed_requests": allowed,
            "blocked_requests": blocked,
            "unique_workspaces": len(self._rate_limits),
            "actions": actions,
        }

    def _check_rate_limit(self, workspace_id: str) -> Tuple[bool, str]:
        """Check per-workspace rate limit.

        Returns:
            Tuple of (allowed, reason).
        """
        if workspace_id not in self._rate_limits:
            self._rate_limits[workspace_id] = RateLimitState(workspace_id=workspace_id)

        state = self._rate_limits[workspace_id]
        count = state.count_in_window(self.config.rate_limit_window_seconds)

        if count >= self.config.rate_limit_per_workspace:
            state.total_blocked += 1
            return False, (
                f"Rate limit exceeded for workspace '{workspace_id}': "
                f"{count}/{self.config.rate_limit_per_workspace} requests "
                f"in {self.config.rate_limit_window_seconds}s window"
            )

        state.record_request()
        return True, "OK"

    def _check_ip_restriction(self, workspace_id: str, ip_address: str) -> Tuple[bool, str]:
        """Check IP-based workspace restriction.

        Returns:
            Tuple of (allowed, reason).
        """
        if workspace_id not in self._workspace_ip_whitelist:
            # No whitelist configured = all IPs allowed
            return True, "OK"

        allowed_ips = self._workspace_ip_whitelist[workspace_id]
        if ip_address not in allowed_ips:
            return False, (
                f"IP {ip_address} not in whitelist for workspace '{workspace_id}'"
            )
        return True, "OK"

    def _log_audit(
        self,
        workspace_id: str,
        user_id: str,
        action: str,
        ip_address: str,
        allowed: bool,
        reason: str,
    ) -> None:
        """Record a middleware audit entry."""
        entry = MiddlewareAuditEntry(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            allowed=allowed,
            reason=reason,
        )
        self._audit_log.append(entry)
