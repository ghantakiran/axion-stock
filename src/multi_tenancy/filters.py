"""Query filtering for multi-tenancy data isolation."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .config import SHARED_RESOURCE_TABLES, TenancyConfig
from .context import TenantContext, TenantContextManager


@dataclass
class QueryAuditEntry:
    """Audit log entry for a filtered query."""

    audit_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    workspace_id: str = ""
    user_id: str = ""
    table_name: str = ""
    operation: str = "SELECT"
    filters_applied: List[str] = field(default_factory=list)
    cross_workspace_attempted: bool = False
    blocked: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class QueryFilter:
    """Applies workspace-based query filtering for data isolation.

    Ensures all queries are scoped to the current workspace unless
    accessing shared resources (e.g., market data tables).
    """

    def __init__(self, config: Optional[TenancyConfig] = None,
                 context_manager: Optional[TenantContextManager] = None):
        self.config = config or TenancyConfig()
        self.context_manager = context_manager or TenantContextManager()
        self._audit_log: List[QueryAuditEntry] = []
        self._shared_tables: Set[str] = set(self.config.shared_tables)

    def filter_query(
        self,
        table_name: str,
        query_params: Optional[Dict[str, Any]] = None,
        context: Optional[TenantContext] = None,
    ) -> Dict[str, Any]:
        """Apply workspace_id filtering to a query.

        Args:
            table_name: The table being queried.
            query_params: Existing query parameters / WHERE clauses.
            context: Optional explicit context; uses thread-local if None.

        Returns:
            Updated query parameters with workspace_id filter injected.

        Raises:
            PermissionError: If cross-workspace access is detected and blocked.
        """
        if query_params is None:
            query_params = {}

        result = dict(query_params)

        # Shared resources skip tenant filtering
        if self.is_shared_resource(table_name):
            self._log_audit(
                context=context,
                table_name=table_name,
                filters_applied=["shared_resource_bypass"],
                reason="Shared resource - no tenant filter applied",
            )
            return result

        # Get context
        ctx = context or self.context_manager.get_context()
        if ctx is None:
            if self.config.enforce_rls:
                self._log_audit(
                    context=None,
                    table_name=table_name,
                    blocked=True,
                    reason="No tenant context - query blocked",
                )
                raise PermissionError(
                    "No tenant context available. Cannot execute query without workspace scope."
                )
            return result

        # Detect cross-workspace attempt
        if "workspace_id" in result and result["workspace_id"] != ctx.workspace_id:
            cross_attempt = True
            if self.config.block_cross_tenant_requests:
                # Check if user has cross-workspace role
                if not self._has_cross_workspace_permission(ctx):
                    self._log_audit(
                        context=ctx,
                        table_name=table_name,
                        cross_workspace_attempted=True,
                        blocked=True,
                        reason=f"Cross-workspace access denied: "
                               f"requested {result['workspace_id']}, "
                               f"context is {ctx.workspace_id}",
                    )
                    raise PermissionError(
                        f"Cross-workspace access denied. "
                        f"Your workspace is '{ctx.workspace_id}', "
                        f"but query targets '{result['workspace_id']}'."
                    )
        else:
            cross_attempt = False

        # Inject workspace_id filter
        result["workspace_id"] = ctx.workspace_id

        self._log_audit(
            context=ctx,
            table_name=table_name,
            filters_applied=[f"workspace_id={ctx.workspace_id}"],
            cross_workspace_attempted=cross_attempt,
            reason="Workspace filter applied",
        )

        return result

    def is_shared_resource(self, table_name: str) -> bool:
        """Check if a table is a shared resource that skips tenant filtering.

        Args:
            table_name: The table name to check.

        Returns:
            True if the table is shared across all workspaces.
        """
        return table_name in self._shared_tables

    def add_shared_table(self, table_name: str) -> None:
        """Add a table to the shared resource list.

        Args:
            table_name: The table name to add.
        """
        self._shared_tables.add(table_name)

    def remove_shared_table(self, table_name: str) -> None:
        """Remove a table from the shared resource list.

        Args:
            table_name: The table name to remove.
        """
        self._shared_tables.discard(table_name)

    def detect_cross_workspace(
        self,
        target_workspace_id: str,
        context: Optional[TenantContext] = None,
    ) -> bool:
        """Check if a query would access a different workspace.

        Args:
            target_workspace_id: The workspace the query targets.
            context: Optional explicit context.

        Returns:
            True if the target workspace differs from the current context.
        """
        ctx = context or self.context_manager.get_context()
        if ctx is None:
            return False
        return target_workspace_id != ctx.workspace_id

    def get_audit_log(self) -> List[QueryAuditEntry]:
        """Return the query audit log.

        Returns:
            List of audit log entries.
        """
        return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """Clear the audit log."""
        self._audit_log.clear()

    def get_audit_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics from the audit log.

        Returns:
            Dictionary with audit statistics.
        """
        total = len(self._audit_log)
        blocked = sum(1 for e in self._audit_log if e.blocked)
        cross_attempts = sum(1 for e in self._audit_log if e.cross_workspace_attempted)
        tables = {}
        for entry in self._audit_log:
            tables[entry.table_name] = tables.get(entry.table_name, 0) + 1

        return {
            "total_queries": total,
            "blocked_queries": blocked,
            "cross_workspace_attempts": cross_attempts,
            "queries_by_table": tables,
            "block_rate": blocked / total if total > 0 else 0.0,
        }

    def _has_cross_workspace_permission(self, ctx: TenantContext) -> bool:
        """Check if context allows cross-workspace access."""
        for role in ctx.roles:
            if role in self.config.allowed_cross_workspace_roles:
                return True
        return False

    def _log_audit(
        self,
        context: Optional[TenantContext],
        table_name: str,
        filters_applied: Optional[List[str]] = None,
        cross_workspace_attempted: bool = False,
        blocked: bool = False,
        reason: str = "",
    ) -> None:
        """Record a query audit entry."""
        if not self.config.audit_logging:
            return

        entry = QueryAuditEntry(
            workspace_id=context.workspace_id if context else "",
            user_id=context.user_id if context else "",
            table_name=table_name,
            filters_applied=filters_applied or [],
            cross_workspace_attempted=cross_workspace_attempted,
            blocked=blocked,
            reason=reason,
        )
        self._audit_log.append(entry)
