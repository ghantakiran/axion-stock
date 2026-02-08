"""Policy engine for role-based access control in multi-tenancy."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .config import (
    AccessLevel,
    PolicyAction,
    ResourceType,
    ROLE_HIERARCHY,
    POLICY_CACHE_TTL_SECONDS,
)
from .context import TenantContext


# Access level hierarchy: higher value = more access
ACCESS_LEVEL_HIERARCHY: Dict[str, int] = {
    AccessLevel.NONE.value: 0,
    AccessLevel.READ.value: 1,
    AccessLevel.WRITE.value: 2,
    AccessLevel.ADMIN.value: 3,
}


@dataclass
class Policy:
    """A data access policy definition."""

    policy_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    workspace_id: str = ""
    resource_type: ResourceType = ResourceType.PORTFOLIO
    role: str = "viewer"
    access_level: AccessLevel = AccessLevel.READ
    conditions: Dict[str, Any] = field(default_factory=dict)
    action: PolicyAction = PolicyAction.ALLOW
    priority: int = 0
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    enabled: bool = True

    def matches(self, workspace_id: str, resource_type: ResourceType, role: str) -> bool:
        """Check if this policy matches the given parameters.

        Args:
            workspace_id: The workspace to match.
            resource_type: The resource type to match.
            role: The role to match.

        Returns:
            True if the policy matches.
        """
        if not self.enabled:
            return False

        # Workspace match: policy applies to specific workspace or global (empty)
        if self.workspace_id and self.workspace_id != workspace_id:
            return False

        # Resource type match
        if self.resource_type != resource_type:
            return False

        # Role match: direct match or role hierarchy (policy role <= request role)
        policy_rank = ROLE_HIERARCHY.get(self.role, 0)
        request_rank = ROLE_HIERARCHY.get(role, 0)

        # If the requesting role is at or above the policy role, it matches
        if request_rank < policy_rank:
            return False

        return True

    def evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """Evaluate policy conditions against a context.

        Args:
            context: Evaluation context with key-value pairs.

        Returns:
            True if all conditions are met.
        """
        if not self.conditions:
            return True

        for key, expected in self.conditions.items():
            actual = context.get(key)
            if actual is None:
                return False
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False

        return True


@dataclass
class PolicyEvaluation:
    """Result of evaluating policies for an access request."""

    allowed: bool = False
    policy_id: str = ""
    reason: str = ""
    access_level: AccessLevel = AccessLevel.NONE
    evaluated_policies: int = 0
    cached: bool = False
    evaluation_time_ms: float = 0.0


class PolicyEngine:
    """Engine for evaluating role-based access control policies.

    Supports:
    - Adding/removing/listing policies
    - Role hierarchy (admin > editor > viewer)
    - Policy evaluation with conditions
    - Caching for performance
    - Workspace-scoped and global policies
    """

    def __init__(self, cache_ttl: int = POLICY_CACHE_TTL_SECONDS):
        self._policies: List[Policy] = []
        self._cache: Dict[str, Tuple[PolicyEvaluation, float]] = {}
        self._cache_ttl = cache_ttl
        self._evaluation_count: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    def add_policy(self, policy: Policy) -> None:
        """Add a policy to the engine.

        Args:
            policy: The policy to add.
        """
        self._policies.append(policy)
        # Invalidate cache when policies change
        self._cache.clear()

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy by ID.

        Args:
            policy_id: The ID of the policy to remove.

        Returns:
            True if the policy was found and removed.
        """
        initial_len = len(self._policies)
        self._policies = [p for p in self._policies if p.policy_id != policy_id]
        if len(self._policies) < initial_len:
            self._cache.clear()
            return True
        return False

    def list_policies(
        self,
        workspace_id: Optional[str] = None,
        resource_type: Optional[ResourceType] = None,
        role: Optional[str] = None,
    ) -> List[Policy]:
        """List policies, optionally filtered.

        Args:
            workspace_id: Filter by workspace ID.
            resource_type: Filter by resource type.
            role: Filter by role.

        Returns:
            List of matching policies.
        """
        result = []
        for p in self._policies:
            if workspace_id and p.workspace_id and p.workspace_id != workspace_id:
                continue
            if resource_type and p.resource_type != resource_type:
                continue
            if role and p.role != role:
                continue
            result.append(p)
        return result

    def evaluate(
        self,
        context: TenantContext,
        resource_type: ResourceType,
        requested_level: AccessLevel = AccessLevel.READ,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> PolicyEvaluation:
        """Evaluate policies to determine if access is allowed.

        Checks all matching policies in priority order. DENY policies
        take precedence over ALLOW policies at the same priority.

        Args:
            context: The tenant context requesting access.
            resource_type: The type of resource being accessed.
            requested_level: The level of access requested.
            conditions: Additional conditions for policy evaluation.

        Returns:
            PolicyEvaluation with the result.
        """
        start_time = time.time()
        self._evaluation_count += 1

        # Check cache
        cache_key = self._build_cache_key(context, resource_type, requested_level)
        cached = self._get_cached(cache_key)
        if cached is not None:
            self._cache_hits += 1
            cached.cached = True
            return cached

        self._cache_misses += 1

        # Find matching policies
        highest_role = context.highest_role() or "viewer"
        matching = []
        for policy in self._policies:
            if policy.matches(context.workspace_id, resource_type, highest_role):
                if conditions is None or policy.evaluate_conditions(conditions):
                    matching.append(policy)

        # Sort by priority (higher = more important), then by action (DENY first at same priority)
        matching.sort(
            key=lambda p: (p.priority, 1 if p.action == PolicyAction.DENY else 0),
            reverse=True,
        )

        elapsed = (time.time() - start_time) * 1000

        if not matching:
            # No matching policies = deny by default
            result = PolicyEvaluation(
                allowed=False,
                reason="No matching policy found",
                evaluated_policies=len(self._policies),
                evaluation_time_ms=elapsed,
            )
            self._set_cached(cache_key, result)
            return result

        # Take the highest priority policy
        top = matching[0]

        if top.action == PolicyAction.DENY:
            result = PolicyEvaluation(
                allowed=False,
                policy_id=top.policy_id,
                reason=f"Denied by policy: {top.description or top.policy_id}",
                access_level=AccessLevel.NONE,
                evaluated_policies=len(matching),
                evaluation_time_ms=elapsed,
            )
            self._set_cached(cache_key, result)
            return result

        # Check if the policy's access level is sufficient
        policy_access_rank = ACCESS_LEVEL_HIERARCHY.get(top.access_level.value, 0)
        requested_rank = ACCESS_LEVEL_HIERARCHY.get(requested_level.value, 0)

        if policy_access_rank >= requested_rank:
            result = PolicyEvaluation(
                allowed=True,
                policy_id=top.policy_id,
                reason=f"Allowed by policy: {top.description or top.policy_id}",
                access_level=top.access_level,
                evaluated_policies=len(matching),
                evaluation_time_ms=elapsed,
            )
        else:
            result = PolicyEvaluation(
                allowed=False,
                policy_id=top.policy_id,
                reason=(
                    f"Insufficient access level: policy grants {top.access_level.value}, "
                    f"requested {requested_level.value}"
                ),
                access_level=top.access_level,
                evaluated_policies=len(matching),
                evaluation_time_ms=elapsed,
            )

        self._set_cached(cache_key, result)
        return result

    def evaluate_batch(
        self,
        context: TenantContext,
        requests: List[Tuple[ResourceType, AccessLevel]],
    ) -> List[PolicyEvaluation]:
        """Evaluate multiple access requests at once.

        Args:
            context: The tenant context.
            requests: List of (resource_type, access_level) tuples.

        Returns:
            List of PolicyEvaluation results.
        """
        return [self.evaluate(context, rt, al) for rt, al in requests]

    def get_effective_access(
        self,
        context: TenantContext,
        resource_type: ResourceType,
    ) -> AccessLevel:
        """Determine the effective access level for a resource.

        Args:
            context: The tenant context.
            resource_type: The resource type.

        Returns:
            The highest AccessLevel granted by matching policies.
        """
        for level in [AccessLevel.ADMIN, AccessLevel.WRITE, AccessLevel.READ]:
            evaluation = self.evaluate(context, resource_type, level)
            if evaluation.allowed:
                return level
        return AccessLevel.NONE

    def clear_cache(self) -> None:
        """Clear the policy evaluation cache."""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics.

        Returns:
            Dictionary with engine stats.
        """
        return {
            "total_policies": len(self._policies),
            "total_evaluations": self._evaluation_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "cache_size": len(self._cache),
        }

    def _build_cache_key(
        self,
        context: TenantContext,
        resource_type: ResourceType,
        access_level: AccessLevel,
    ) -> str:
        """Build a cache key from evaluation parameters."""
        roles_key = ",".join(sorted(context.roles))
        return f"{context.workspace_id}:{roles_key}:{resource_type.value}:{access_level.value}"

    def _get_cached(self, key: str) -> Optional[PolicyEvaluation]:
        """Get a cached evaluation result if still valid."""
        if key not in self._cache:
            return None
        result, cached_at = self._cache[key]
        if time.time() - cached_at > self._cache_ttl:
            del self._cache[key]
            return None
        return PolicyEvaluation(
            allowed=result.allowed,
            policy_id=result.policy_id,
            reason=result.reason,
            access_level=result.access_level,
            evaluated_policies=result.evaluated_policies,
            evaluation_time_ms=result.evaluation_time_ms,
        )

    def _set_cached(self, key: str, result: PolicyEvaluation) -> None:
        """Store an evaluation result in the cache."""
        self._cache[key] = (result, time.time())
