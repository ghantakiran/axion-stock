"""PRD-114: Notification & Alerting System - Alert Routing."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .config import AlertCategory, AlertSeverity, ChannelType

logger = logging.getLogger(__name__)

# Severity ordering for comparison
_SEVERITY_ORDER = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.ERROR: 2,
    AlertSeverity.CRITICAL: 3,
}


@dataclass
class RoutingRule:
    """A rule that maps alert attributes to notification channels."""

    rule_id: str
    name: str
    severity_min: AlertSeverity
    categories: List[AlertCategory] = field(default_factory=list)
    channels: List[ChannelType] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0


class RoutingEngine:
    """Routes alerts to appropriate channels based on configurable rules.

    Rules are evaluated by priority (higher first). The first matching rule
    determines the channels. If no rules match, default channels are used.
    """

    def __init__(self, default_channels: Optional[List[ChannelType]] = None) -> None:
        self._rules: List[RoutingRule] = []
        self._default_channels: List[ChannelType] = default_channels or [ChannelType.IN_APP]

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule.

        Args:
            rule: The RoutingRule to add.
        """
        self._rules.append(rule)
        logger.info("Added routing rule: %s (priority=%d)", rule.name, rule.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule by ID.

        Args:
            rule_id: The rule ID to remove.

        Returns:
            True if the rule was found and removed.
        """
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        removed = len(self._rules) < initial_count
        if removed:
            logger.info("Removed routing rule: %s", rule_id)
        return removed

    def resolve_channels(self, alert) -> List[ChannelType]:
        """Determine which channels an alert should be routed to.

        Evaluates rules sorted by priority (descending). Returns channels
        from the highest-priority matching rule, or default channels.

        Args:
            alert: The Alert to route.

        Returns:
            List of ChannelType for delivery.
        """
        sorted_rules = sorted(self._rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if not rule.enabled:
                continue

            # Check severity: alert severity must be >= rule's minimum
            alert_severity_level = _SEVERITY_ORDER.get(alert.severity, 0)
            rule_min_level = _SEVERITY_ORDER.get(rule.severity_min, 0)
            if alert_severity_level < rule_min_level:
                continue

            # Check category: if rule has categories, alert must match one
            if rule.categories and alert.category not in rule.categories:
                continue

            logger.debug(
                "Alert %s matched rule %s -> channels %s",
                alert.alert_id,
                rule.name,
                [c.value for c in rule.channels],
            )
            return list(rule.channels)

        # No rules matched, use defaults
        return list(self._default_channels)

    def get_rules(self) -> List[RoutingRule]:
        """Get all routing rules.

        Returns:
            List of all RoutingRule entries.
        """
        return list(self._rules)

    def clear_rules(self) -> None:
        """Remove all routing rules."""
        self._rules.clear()
        logger.info("All routing rules cleared")
