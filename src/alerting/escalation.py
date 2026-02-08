"""PRD-114: Notification & Alerting System - Escalation Management."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import ChannelType

logger = logging.getLogger(__name__)


@dataclass
class EscalationLevel:
    """A single level in an escalation policy."""

    level: int
    timeout_seconds: int
    channels: List[ChannelType] = field(default_factory=list)
    notify_targets: List[str] = field(default_factory=list)


@dataclass
class EscalationPolicy:
    """An escalation policy with multiple levels."""

    policy_id: str
    name: str
    levels: List[EscalationLevel] = field(default_factory=list)
    enabled: bool = True


@dataclass
class _EscalationState:
    """Internal state for an active escalation."""

    policy_id: str
    current_level: int
    escalated_at: datetime
    started_at: datetime


class EscalationManager:
    """Manages alert escalation policies and their execution.

    Tracks which alerts have active escalations, checks for timeout-based
    level promotions, and provides escalation state inspection.
    """

    def __init__(self) -> None:
        self._policies: Dict[str, EscalationPolicy] = {}
        self._escalation_state: Dict[str, _EscalationState] = {}

    def add_policy(self, policy: EscalationPolicy) -> None:
        """Register an escalation policy.

        Args:
            policy: The EscalationPolicy to register.
        """
        self._policies[policy.policy_id] = policy
        logger.info("Added escalation policy: %s (%s)", policy.policy_id, policy.name)

    def remove_policy(self, policy_id: str) -> bool:
        """Remove an escalation policy by ID.

        Args:
            policy_id: The policy ID to remove.

        Returns:
            True if the policy was found and removed.
        """
        if policy_id in self._policies:
            del self._policies[policy_id]
            logger.info("Removed escalation policy: %s", policy_id)
            return True
        return False

    def start_escalation(self, alert_id: str, policy_id: str) -> bool:
        """Start escalation for an alert using a specified policy.

        Args:
            alert_id: The alert to escalate.
            policy_id: The policy to apply.

        Returns:
            True if escalation was started successfully.
        """
        policy = self._policies.get(policy_id)
        if policy is None:
            logger.warning("Escalation policy %s not found", policy_id)
            return False

        if not policy.enabled:
            logger.warning("Escalation policy %s is disabled", policy_id)
            return False

        if not policy.levels:
            logger.warning("Escalation policy %s has no levels", policy_id)
            return False

        now = datetime.utcnow()
        self._escalation_state[alert_id] = _EscalationState(
            policy_id=policy_id,
            current_level=0,
            escalated_at=now,
            started_at=now,
        )
        logger.info(
            "Started escalation for alert %s with policy %s",
            alert_id,
            policy_id,
        )
        return True

    def check_escalations(self, now: Optional[datetime] = None) -> List[Tuple[str, EscalationLevel]]:
        """Check all active escalations for timeout-based promotions.

        Args:
            now: Current time (defaults to utcnow).

        Returns:
            List of (alert_id, EscalationLevel) tuples for alerts
            that need escalation to the next level.
        """
        if now is None:
            now = datetime.utcnow()

        escalations_needed: List[Tuple[str, EscalationLevel]] = []

        for alert_id, state in list(self._escalation_state.items()):
            policy = self._policies.get(state.policy_id)
            if policy is None or not policy.enabled:
                continue

            current_level_idx = state.current_level
            if current_level_idx >= len(policy.levels):
                continue

            current_level = policy.levels[current_level_idx]
            elapsed = (now - state.escalated_at).total_seconds()

            if elapsed >= current_level.timeout_seconds:
                # Move to next level
                next_level_idx = current_level_idx + 1
                if next_level_idx < len(policy.levels):
                    next_level = policy.levels[next_level_idx]
                    state.current_level = next_level_idx
                    state.escalated_at = now
                    escalations_needed.append((alert_id, next_level))
                    logger.info(
                        "Alert %s escalated to level %d",
                        alert_id,
                        next_level_idx,
                    )
                else:
                    # Already at max level, still report it
                    escalations_needed.append((alert_id, current_level))
                    logger.info(
                        "Alert %s at max escalation level %d",
                        alert_id,
                        current_level_idx,
                    )

        return escalations_needed

    def cancel_escalation(self, alert_id: str) -> bool:
        """Cancel an active escalation for an alert.

        Args:
            alert_id: The alert whose escalation to cancel.

        Returns:
            True if an escalation was found and cancelled.
        """
        if alert_id in self._escalation_state:
            del self._escalation_state[alert_id]
            logger.info("Cancelled escalation for alert %s", alert_id)
            return True
        return False

    def get_escalation_state(self, alert_id: str) -> Optional[Dict]:
        """Get the current escalation state for an alert.

        Args:
            alert_id: The alert to inspect.

        Returns:
            Dict with current_level, policy_id, escalated_at, and
            time_remaining_seconds, or None if no active escalation.
        """
        state = self._escalation_state.get(alert_id)
        if state is None:
            return None

        policy = self._policies.get(state.policy_id)
        time_remaining = 0.0
        if policy and state.current_level < len(policy.levels):
            current_level = policy.levels[state.current_level]
            elapsed = (datetime.utcnow() - state.escalated_at).total_seconds()
            time_remaining = max(0.0, current_level.timeout_seconds - elapsed)

        return {
            "policy_id": state.policy_id,
            "current_level": state.current_level,
            "escalated_at": state.escalated_at,
            "started_at": state.started_at,
            "time_remaining_seconds": time_remaining,
        }

    def get_policies(self) -> List[EscalationPolicy]:
        """Get all registered escalation policies.

        Returns:
            List of all EscalationPolicy entries.
        """
        return list(self._policies.values())
