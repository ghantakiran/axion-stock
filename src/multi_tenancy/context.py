"""Tenant context management for multi-tenancy data isolation."""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set


@dataclass
class TenantContext:
    """Represents the current tenant context for a request or task."""

    workspace_id: str
    user_id: str
    roles: List[str] = field(default_factory=list)
    permissions: Dict[str, str] = field(default_factory=dict)
    context_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    parent_context_id: Optional[str] = None
    is_background: bool = False

    def has_role(self, role: str) -> bool:
        """Check if context has a specific role."""
        return role in self.roles

    def has_permission(self, resource: str, level: str) -> bool:
        """Check if context has a specific permission on a resource."""
        return self.permissions.get(resource) == level

    def highest_role(self) -> Optional[str]:
        """Return the highest-priority role from the hierarchy."""
        from .config import ROLE_HIERARCHY
        best = None
        best_rank = -1
        for role in self.roles:
            rank = ROLE_HIERARCHY.get(role, 0)
            if rank > best_rank:
                best_rank = rank
                best = role
        return best

    def create_child_context(self) -> "TenantContext":
        """Create a child context for background tasks, inheriting workspace and roles."""
        return TenantContext(
            workspace_id=self.workspace_id,
            user_id=self.user_id,
            roles=list(self.roles),
            permissions=dict(self.permissions),
            parent_context_id=self.context_id,
            is_background=True,
            ip_address=self.ip_address,
        )

    def validate(self) -> bool:
        """Validate that the context has required fields."""
        if not self.workspace_id or not self.workspace_id.strip():
            return False
        if not self.user_id or not self.user_id.strip():
            return False
        return True


class TenantContextManager:
    """Thread-local tenant context manager.

    Manages tenant context on a per-thread basis to ensure data isolation.
    Supports context inheritance for spawned background tasks.
    """

    def __init__(self):
        self._local = threading.local()
        self._context_history: Dict[str, TenantContext] = {}

    def set_context(self, context: TenantContext) -> None:
        """Set the current tenant context for this thread.

        Args:
            context: The tenant context to set.

        Raises:
            ValueError: If the context is invalid.
        """
        if not context.validate():
            raise ValueError("Invalid tenant context: workspace_id and user_id are required")
        self._local.context = context
        self._context_history[context.context_id] = context

    def get_context(self) -> Optional[TenantContext]:
        """Get the current tenant context for this thread.

        Returns:
            The current TenantContext or None if not set.
        """
        return getattr(self._local, "context", None)

    def clear_context(self) -> None:
        """Clear the current tenant context for this thread."""
        self._local.context = None

    def require_context(self) -> TenantContext:
        """Get context or raise if not set.

        Returns:
            The current TenantContext.

        Raises:
            RuntimeError: If no context is set.
        """
        ctx = self.get_context()
        if ctx is None:
            raise RuntimeError("No tenant context set. Call set_context() first.")
        return ctx

    def get_context_by_id(self, context_id: str) -> Optional[TenantContext]:
        """Look up a context by its ID.

        Args:
            context_id: The context ID to look up.

        Returns:
            The TenantContext or None if not found.
        """
        return self._context_history.get(context_id)

    def create_background_context(self) -> TenantContext:
        """Create a child context for background task execution.

        Returns:
            A new TenantContext inheriting from the current context.

        Raises:
            RuntimeError: If no current context exists.
        """
        current = self.require_context()
        child = current.create_child_context()
        self._context_history[child.context_id] = child
        return child

    @property
    def active_context_count(self) -> int:
        """Return the number of tracked contexts."""
        return len(self._context_history)


# Global singleton for easy access
_global_context_manager = TenantContextManager()


def get_global_context_manager() -> TenantContextManager:
    """Get the global tenant context manager singleton."""
    return _global_context_manager
