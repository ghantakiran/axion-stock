"""Feature flag service with boolean, percentage, and user-targeted flags."""

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .config import FeatureFlagType

logger = logging.getLogger(__name__)


class FlagStatus(str, Enum):
    """Lifecycle status of a feature flag."""

    CREATED = "created"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class FlagContext:
    """Context for evaluating feature flags.

    Provides user and environment info for targeted flag evaluation.
    """

    user_id: Optional[str] = None
    environment: Optional[str] = None
    tier: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureFlag:
    """A feature flag definition."""

    name: str
    flag_type: FeatureFlagType = FeatureFlagType.BOOLEAN
    enabled: bool = False
    percentage: float = 0.0
    user_list: List[str] = field(default_factory=list)
    description: str = ""
    status: FlagStatus = FlagStatus.CREATED
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tags: Dict[str, str] = field(default_factory=dict)


class FeatureFlagService:
    """Manages feature flags with support for boolean, percentage, and user-targeted rollouts.

    Percentage rollouts use deterministic hashing so the same user always
    gets the same result for a given flag.
    """

    def __init__(self, default_value: bool = False):
        self._flags: Dict[str, FeatureFlag] = {}
        self._default_value = default_value
        self._lock = threading.RLock()
        self._evaluation_log: List[Dict[str, Any]] = []

    def create_flag(
        self,
        name: str,
        flag_type: FeatureFlagType = FeatureFlagType.BOOLEAN,
        enabled: bool = False,
        percentage: float = 0.0,
        user_list: Optional[List[str]] = None,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> FeatureFlag:
        """Create a new feature flag."""
        with self._lock:
            flag = FeatureFlag(
                name=name,
                flag_type=flag_type,
                enabled=enabled,
                percentage=percentage,
                user_list=user_list or [],
                description=description,
                status=FlagStatus.ACTIVE,
                tags=tags or {},
            )
            self._flags[name] = flag
            logger.info("Feature flag created: %s (%s)", name, flag_type.value)
            return flag

    def evaluate(self, name: str, context: Optional[FlagContext] = None) -> bool:
        """Evaluate a feature flag in the given context.

        For BOOLEAN flags: returns the enabled field.
        For PERCENTAGE flags: deterministic hash of user_id to decide.
        For USER_LIST flags: checks if user_id is in the list.
        """
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return self._default_value

            if flag.status in (FlagStatus.DEPRECATED, FlagStatus.ARCHIVED):
                return self._default_value

            ctx = context or FlagContext()
            result = self._evaluate_flag(flag, ctx)

            self._evaluation_log.append({
                "flag": name,
                "result": result,
                "user_id": ctx.user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            return result

    def _evaluate_flag(self, flag: FeatureFlag, ctx: FlagContext) -> bool:
        """Internal flag evaluation logic."""
        if not flag.enabled:
            return False

        if flag.flag_type == FeatureFlagType.BOOLEAN:
            return flag.enabled

        elif flag.flag_type == FeatureFlagType.PERCENTAGE:
            if ctx.user_id is None:
                return False
            hash_input = f"{flag.name}:{ctx.user_id}"
            hash_value = int(
                hashlib.sha256(hash_input.encode()).hexdigest(), 16
            ) % 100
            return hash_value < flag.percentage

        elif flag.flag_type == FeatureFlagType.USER_LIST:
            if ctx.user_id is None:
                return False
            return ctx.user_id in flag.user_list

        return self._default_value

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a flag."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.enabled = enabled
            flag.updated_at = datetime.now(timezone.utc)
            return True

    def set_percentage(self, name: str, percentage: float) -> bool:
        """Set the rollout percentage for a percentage flag."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.percentage = max(0.0, min(100.0, percentage))
            flag.updated_at = datetime.now(timezone.utc)
            return True

    def add_user(self, name: str, user_id: str) -> bool:
        """Add a user to a user-list flag."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            if user_id not in flag.user_list:
                flag.user_list.append(user_id)
                flag.updated_at = datetime.now(timezone.utc)
            return True

    def remove_user(self, name: str, user_id: str) -> bool:
        """Remove a user from a user-list flag."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            if user_id in flag.user_list:
                flag.user_list.remove(user_id)
                flag.updated_at = datetime.now(timezone.utc)
            return True

    def deprecate(self, name: str) -> bool:
        """Mark a flag as deprecated."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.status = FlagStatus.DEPRECATED
            flag.updated_at = datetime.now(timezone.utc)
            return True

    def archive(self, name: str) -> bool:
        """Archive a flag (removes it from active evaluation)."""
        with self._lock:
            flag = self._flags.get(name)
            if flag is None:
                return False
            flag.status = FlagStatus.ARCHIVED
            flag.enabled = False
            flag.updated_at = datetime.now(timezone.utc)
            return True

    def delete(self, name: str) -> bool:
        """Delete a flag entirely."""
        with self._lock:
            return self._flags.pop(name, None) is not None

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a flag by name."""
        with self._lock:
            return self._flags.get(name)

    def list_flags(
        self, status: Optional[FlagStatus] = None,
        flag_type: Optional[FeatureFlagType] = None,
    ) -> List[FeatureFlag]:
        """List all flags, optionally filtered."""
        with self._lock:
            flags = list(self._flags.values())
            if status is not None:
                flags = [f for f in flags if f.status == status]
            if flag_type is not None:
                flags = [f for f in flags if f.flag_type == flag_type]
            return flags

    def get_evaluation_log(self, flag_name: Optional[str] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent flag evaluations."""
        with self._lock:
            log = self._evaluation_log
            if flag_name:
                log = [e for e in log if e["flag"] == flag_name]
            return list(reversed(log[-limit:]))

    def clear(self) -> None:
        """Clear all flags and evaluation log."""
        with self._lock:
            self._flags.clear()
            self._evaluation_log.clear()
