"""Retention policy management for data lifecycle."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .config import StorageTier

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """Defines a retention policy for a specific table."""

    policy_id: str = field(default_factory=lambda: str(uuid4()))
    table_name: str = ""
    hot_days: int = 90
    warm_days: int = 365
    cold_days: int = 2555
    delete_after_days: Optional[int] = None
    legal_hold: bool = False
    description: str = ""

    def get_tier_for_age(self, age_days: int) -> StorageTier:
        """Determine which storage tier data of a given age belongs to."""
        if self.legal_hold:
            return StorageTier.COLD  # legal hold prevents deletion
        if self.delete_after_days is not None and age_days > self.delete_after_days:
            return StorageTier.DELETED
        if age_days > self.cold_days:
            return StorageTier.ARCHIVE
        if age_days > self.warm_days:
            return StorageTier.COLD
        if age_days > self.hot_days:
            return StorageTier.WARM
        return StorageTier.HOT


class RetentionManager:
    """Manages retention policies across all tables."""

    def __init__(self):
        self._policies: Dict[str, RetentionPolicy] = {}
        self._holds: Dict[str, str] = {}  # table_name -> reason
        self._lock = threading.Lock()

    def add_policy(
        self,
        table_name: str,
        hot_days: int = 90,
        warm_days: int = 365,
        cold_days: int = 2555,
        delete_after: Optional[int] = None,
        description: str = "",
    ) -> RetentionPolicy:
        """Create and register a retention policy for a table."""
        with self._lock:
            policy = RetentionPolicy(
                table_name=table_name,
                hot_days=hot_days,
                warm_days=warm_days,
                cold_days=cold_days,
                delete_after_days=delete_after,
                description=description,
            )
            self._policies[table_name] = policy
            logger.info("Added retention policy for table %s", table_name)
            return policy

    def get_policy(self, table_name: str) -> Optional[RetentionPolicy]:
        """Retrieve the retention policy for a table."""
        return self._policies.get(table_name)

    def evaluate_table(self, table_name: str, data_age_days: int) -> dict:
        """Evaluate the current tier and next action for a table's data."""
        policy = self._policies.get(table_name)
        if not policy:
            return {
                "table_name": table_name,
                "current_tier": StorageTier.HOT.value,
                "action_needed": "no_policy",
                "next_transition": None,
            }

        current_tier = policy.get_tier_for_age(data_age_days)

        # Determine next transition
        next_transition = None
        action_needed = "none"
        if current_tier == StorageTier.HOT:
            days_until = policy.hot_days - data_age_days
            next_transition = {"to_tier": StorageTier.WARM.value, "in_days": max(0, days_until)}
            if days_until <= 0:
                action_needed = "migrate_to_warm"
        elif current_tier == StorageTier.WARM:
            days_until = policy.warm_days - data_age_days
            next_transition = {"to_tier": StorageTier.COLD.value, "in_days": max(0, days_until)}
            if days_until <= 0:
                action_needed = "migrate_to_cold"
        elif current_tier == StorageTier.COLD:
            days_until = policy.cold_days - data_age_days
            next_transition = {"to_tier": StorageTier.ARCHIVE.value, "in_days": max(0, days_until)}
            if days_until <= 0:
                action_needed = "archive"
        elif current_tier == StorageTier.DELETED:
            action_needed = "delete"

        return {
            "table_name": table_name,
            "current_tier": current_tier.value,
            "action_needed": action_needed,
            "next_transition": next_transition,
        }

    def set_legal_hold(self, table_name: str, reason: str) -> bool:
        """Place a legal hold on a table, preventing deletion."""
        with self._lock:
            policy = self._policies.get(table_name)
            if not policy:
                logger.warning("Cannot set legal hold: no policy for table %s", table_name)
                return False
            policy.legal_hold = True
            self._holds[table_name] = reason
            logger.info("Legal hold set on table %s: %s", table_name, reason)
            return True

    def release_legal_hold(self, table_name: str) -> bool:
        """Release a legal hold from a table."""
        with self._lock:
            policy = self._policies.get(table_name)
            if not policy or not policy.legal_hold:
                return False
            policy.legal_hold = False
            self._holds.pop(table_name, None)
            logger.info("Legal hold released on table %s", table_name)
            return True

    def get_policies(self) -> List[RetentionPolicy]:
        """Return all registered retention policies."""
        return list(self._policies.values())

    def get_holds(self) -> List[str]:
        """Return list of tables currently under legal hold."""
        return list(self._holds.keys())

    def get_expiring_data(self, within_days: int = 30) -> List[dict]:
        """Identify tables with data approaching its deletion threshold."""
        expiring = []
        for table_name, policy in self._policies.items():
            if policy.delete_after_days is not None and not policy.legal_hold:
                remaining = policy.delete_after_days  # Simplified: compare against policy threshold
                if remaining <= within_days:
                    expiring.append({
                        "table_name": table_name,
                        "delete_after_days": policy.delete_after_days,
                        "legal_hold": policy.legal_hold,
                        "description": policy.description,
                    })
        return expiring

    def reset(self) -> None:
        """Reset all manager state."""
        with self._lock:
            self._policies.clear()
            self._holds.clear()
