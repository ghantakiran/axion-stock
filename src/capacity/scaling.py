"""Scaling management for PRD-130: Capacity Planning & Auto-Scaling."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from .config import (
    CapacityConfig,
    ResourceThreshold,
    ResourceType,
    ScalingDirection,
    ScalingPolicy,
)
from .monitor import ResourceMetric, ResourceMonitor


@dataclass
class ScalingRule:
    """A rule that determines when and how to scale."""

    rule_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource_type: ResourceType = ResourceType.CPU
    service: str = "default"
    policy: ScalingPolicy = ScalingPolicy.THRESHOLD
    thresholds: ResourceThreshold = field(default_factory=ResourceThreshold)
    min_instances: int = 1
    max_instances: int = 10
    current_instances: int = 1
    enabled: bool = True
    last_action_time: Optional[datetime] = None


@dataclass
class ScalingAction:
    """A scaling action (executed or proposed)."""

    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    rule_id: str = ""
    direction: ScalingDirection = ScalingDirection.NO_ACTION
    from_value: int = 0
    to_value: int = 0
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed: bool = False
    success: bool = False


class ScalingManager:
    """Manages auto-scaling rules and actions."""

    def __init__(
        self,
        monitor: Optional[ResourceMonitor] = None,
        config: Optional[CapacityConfig] = None,
    ):
        self.monitor = monitor or ResourceMonitor()
        self.config = config or CapacityConfig()
        self._rules: Dict[str, ScalingRule] = {}
        self._actions: List[ScalingAction] = []
        self._cooldowns: Dict[str, int] = {}

    def add_rule(self, rule: ScalingRule) -> str:
        """Add a scaling rule. Returns rule_id."""
        self._rules[rule.rule_id] = rule
        return rule.rule_id

    def evaluate_rules(self) -> List[ScalingAction]:
        """Evaluate all active rules and return recommended actions."""
        actions = []
        now = datetime.now(timezone.utc)

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            # Check cooldown
            cooldown = self._cooldowns.get(
                rule.rule_id, rule.thresholds.cooldown_seconds
            )
            if rule.last_action_time:
                elapsed = (now - rule.last_action_time).total_seconds()
                if elapsed < cooldown:
                    continue

            metric = self.monitor.get_current_utilization(
                rule.resource_type, rule.service
            )
            if not metric:
                continue

            action = self._evaluate_single_rule(rule, metric)
            if action and action.direction != ScalingDirection.NO_ACTION:
                actions.append(action)

        return actions

    def execute_action(self, action: ScalingAction) -> bool:
        """Execute a scaling action."""
        if not self.config.enable_auto_scaling:
            action.executed = False
            action.success = False
            return False

        rule = self._rules.get(action.rule_id)
        if not rule:
            action.executed = True
            action.success = False
            return False

        # Validate bounds
        if action.to_value < rule.min_instances or action.to_value > rule.max_instances:
            action.executed = True
            action.success = False
            return False

        # Check hourly action limit
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_actions = [
            a for a in self._actions
            if a.executed and a.success and a.timestamp >= one_hour_ago
        ]
        if len(recent_actions) >= self.config.max_scaling_actions_per_hour:
            action.executed = True
            action.success = False
            return False

        # Execute
        rule.current_instances = action.to_value
        rule.last_action_time = datetime.now(timezone.utc)
        action.executed = True
        action.success = True
        action.timestamp = datetime.now(timezone.utc)
        self._actions.append(action)
        return True

    def get_scaling_history(
        self, service: Optional[str] = None, hours: int = 24
    ) -> List[ScalingAction]:
        """Get scaling action history."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = [a for a in self._actions if a.timestamp >= cutoff]
        if service:
            rule_ids = {
                rid for rid, r in self._rules.items() if r.service == service
            }
            result = [a for a in result if a.rule_id in rule_ids]
        return result

    def set_cooldown(self, rule_id: str, seconds: int) -> None:
        """Set cooldown period for a rule."""
        self._cooldowns[rule_id] = seconds

    def get_active_rules(self) -> List[ScalingRule]:
        """Get all enabled rules."""
        return [r for r in self._rules.values() if r.enabled]

    def simulate_scaling(
        self, rule: ScalingRule, metrics: List[ResourceMetric]
    ) -> ScalingAction:
        """Simulate what scaling action would be taken for given metrics."""
        if not metrics:
            return ScalingAction(
                rule_id=rule.rule_id,
                direction=ScalingDirection.NO_ACTION,
                from_value=rule.current_instances,
                to_value=rule.current_instances,
                reason="No metrics provided",
            )

        # Use the latest metric
        latest = max(metrics, key=lambda m: m.timestamp)
        action = self._evaluate_single_rule(rule, latest)
        return action or ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.NO_ACTION,
            from_value=rule.current_instances,
            to_value=rule.current_instances,
            reason="No scaling needed",
        )

    def _evaluate_single_rule(
        self, rule: ScalingRule, metric: ResourceMetric
    ) -> Optional[ScalingAction]:
        """Evaluate a single rule against a metric."""
        threshold = rule.thresholds
        util = metric.utilization_pct

        if util >= threshold.scale_up_pct:
            new_instances = min(rule.current_instances + 1, rule.max_instances)
            if new_instances == rule.current_instances:
                return ScalingAction(
                    rule_id=rule.rule_id,
                    direction=ScalingDirection.NO_ACTION,
                    from_value=rule.current_instances,
                    to_value=rule.current_instances,
                    reason=f"Already at max instances ({rule.max_instances})",
                )
            return ScalingAction(
                rule_id=rule.rule_id,
                direction=ScalingDirection.SCALE_OUT,
                from_value=rule.current_instances,
                to_value=new_instances,
                reason=f"Utilization {util:.1f}% >= scale_up threshold {threshold.scale_up_pct:.1f}%",
            )

        if util <= threshold.scale_down_pct:
            new_instances = max(rule.current_instances - 1, rule.min_instances)
            if new_instances == rule.current_instances:
                return ScalingAction(
                    rule_id=rule.rule_id,
                    direction=ScalingDirection.NO_ACTION,
                    from_value=rule.current_instances,
                    to_value=rule.current_instances,
                    reason=f"Already at min instances ({rule.min_instances})",
                )
            return ScalingAction(
                rule_id=rule.rule_id,
                direction=ScalingDirection.SCALE_IN,
                from_value=rule.current_instances,
                to_value=new_instances,
                reason=f"Utilization {util:.1f}% <= scale_down threshold {threshold.scale_down_pct:.1f}%",
            )

        return ScalingAction(
            rule_id=rule.rule_id,
            direction=ScalingDirection.NO_ACTION,
            from_value=rule.current_instances,
            to_value=rule.current_instances,
            reason=f"Utilization {util:.1f}% within normal range",
        )
