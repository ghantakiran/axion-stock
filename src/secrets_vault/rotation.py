"""PRD-124: Secrets Management & API Credential Vaulting - Credential Rotation."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

from .config import RotationStrategy, SecretType
from .vault import SecretsVault


@dataclass
class RotationPolicy:
    """Policy defining how and when a secret should be rotated."""

    policy_id: str
    key_path: str
    strategy: RotationStrategy
    interval_hours: int = 24
    grace_period_hours: int = 1
    last_rotated: Optional[datetime] = None
    next_rotation: Optional[datetime] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RotationResult:
    """Result of a credential rotation attempt."""

    success: bool
    old_version: int
    new_version: int
    duration_seconds: float
    error: Optional[str] = None
    key_path: str = ""
    rotated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CredentialRotation:
    """Manages automatic credential rotation with configurable policies.

    Supports pre/post rotation hooks and multiple rotation strategies.
    """

    def __init__(self, vault: SecretsVault):
        self.vault = vault
        self._policies: Dict[str, RotationPolicy] = {}
        self._history: List[RotationResult] = []
        self._pre_hooks: Dict[str, List[Callable]] = {}
        self._post_hooks: Dict[str, List[Callable]] = {}
        self._generators: Dict[str, Callable[[], str]] = {}

    def add_policy(
        self,
        key_path: str,
        strategy: RotationStrategy = RotationStrategy.CREATE_THEN_DELETE,
        interval_hours: int = 24,
        grace_period_hours: int = 1,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RotationPolicy:
        """Add a rotation policy for a secret path."""
        policy_id = uuid.uuid4().hex[:16]
        now = datetime.now(timezone.utc)

        policy = RotationPolicy(
            policy_id=policy_id,
            key_path=key_path,
            strategy=strategy,
            interval_hours=interval_hours,
            grace_period_hours=grace_period_hours,
            last_rotated=None,
            next_rotation=now + timedelta(hours=interval_hours),
            enabled=enabled,
            metadata=metadata or {},
        )

        self._policies[policy_id] = policy
        return policy

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a rotation policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[RotationPolicy]:
        """Get a rotation policy by ID."""
        return self._policies.get(policy_id)

    def register_generator(self, key_path: str, generator: Callable[[], str]) -> None:
        """Register a credential generator for a key path."""
        self._generators[key_path] = generator

    def register_pre_hook(self, key_path: str, hook: Callable) -> None:
        """Register a pre-rotation hook."""
        if key_path not in self._pre_hooks:
            self._pre_hooks[key_path] = []
        self._pre_hooks[key_path].append(hook)

    def register_post_hook(self, key_path: str, hook: Callable) -> None:
        """Register a post-rotation hook."""
        if key_path not in self._post_hooks:
            self._post_hooks[key_path] = []
        self._post_hooks[key_path].append(hook)

    def execute_rotation(self, policy_id: str, new_value: Optional[str] = None) -> RotationResult:
        """Execute credential rotation for a policy."""
        policy = self._policies.get(policy_id)
        if policy is None:
            return RotationResult(
                success=False,
                old_version=0,
                new_version=0,
                duration_seconds=0.0,
                error=f"Policy {policy_id} not found",
            )

        start_time = time.time()

        # Get current version
        current = self.vault.get(policy.key_path)
        old_version = current.version if current else 0

        try:
            # Execute pre-rotation hooks
            for hook in self._pre_hooks.get(policy.key_path, []):
                hook(policy.key_path, old_version)

            # Determine new value
            if new_value is None:
                generator = self._generators.get(policy.key_path)
                if generator:
                    new_value = generator()
                else:
                    new_value = uuid.uuid4().hex

            # Store new version
            secret_type = current.secret_type if current else SecretType.GENERIC
            owner = current.owner_service if current else ""
            entry = self.vault.put(
                key_path=policy.key_path,
                value=new_value,
                secret_type=secret_type,
                owner_service=owner,
                metadata={"rotated": True, "strategy": policy.strategy.value},
            )

            # Execute post-rotation hooks
            for hook in self._post_hooks.get(policy.key_path, []):
                hook(policy.key_path, entry.version)

            # Update policy
            now = datetime.now(timezone.utc)
            policy.last_rotated = now
            policy.next_rotation = now + timedelta(hours=policy.interval_hours)

            duration = time.time() - start_time
            result = RotationResult(
                success=True,
                old_version=old_version,
                new_version=entry.version,
                duration_seconds=round(duration, 4),
                key_path=policy.key_path,
                rotated_at=now,
            )

        except Exception as e:
            duration = time.time() - start_time
            result = RotationResult(
                success=False,
                old_version=old_version,
                new_version=old_version,
                duration_seconds=round(duration, 4),
                error=str(e),
                key_path=policy.key_path,
            )

        self._history.append(result)
        return result

    def get_due_rotations(self) -> List[RotationPolicy]:
        """Get all policies due for rotation."""
        now = datetime.now(timezone.utc)
        due = []
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if policy.next_rotation and policy.next_rotation <= now:
                due.append(policy)
            elif policy.next_rotation is None:
                due.append(policy)
        return due

    def get_rotation_history(
        self, key_path: Optional[str] = None, limit: int = 100
    ) -> List[RotationResult]:
        """Get rotation history, optionally filtered by key path."""
        if key_path:
            filtered = [r for r in self._history if r.key_path == key_path]
        else:
            filtered = list(self._history)
        return filtered[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get rotation statistics."""
        total_policies = len(self._policies)
        enabled = sum(1 for p in self._policies.values() if p.enabled)
        total_rotations = len(self._history)
        successful = sum(1 for r in self._history if r.success)
        failed = total_rotations - successful

        due = self.get_due_rotations()

        avg_duration = 0.0
        if total_rotations > 0:
            avg_duration = sum(r.duration_seconds for r in self._history) / total_rotations

        by_strategy: Dict[str, int] = {}
        for policy in self._policies.values():
            s = policy.strategy.value
            by_strategy[s] = by_strategy.get(s, 0) + 1

        return {
            "total_policies": total_policies,
            "enabled_policies": enabled,
            "disabled_policies": total_policies - enabled,
            "due_rotations": len(due),
            "total_rotations": total_rotations,
            "successful_rotations": successful,
            "failed_rotations": failed,
            "avg_duration_seconds": round(avg_duration, 4),
            "by_strategy": by_strategy,
        }
