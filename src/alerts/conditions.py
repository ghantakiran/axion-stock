"""Condition evaluation engine.

Builds and evaluates alert conditions from templates and user definitions.
"""

import logging
from typing import Optional

from src.alerts.config import (
    AlertType,
    ComparisonOperator,
    LogicalOperator,
    ALERT_TEMPLATES,
)
from src.alerts.models import AlertCondition, CompoundCondition

logger = logging.getLogger(__name__)


class ConditionBuilder:
    """Builder for alert conditions.

    Constructs AlertCondition and CompoundCondition objects from
    user input or pre-built templates.
    """

    @staticmethod
    def from_template(
        template_name: str,
        threshold_override: Optional[float] = None,
    ) -> CompoundCondition:
        """Create a condition from a pre-built template.

        Args:
            template_name: Template key from ALERT_TEMPLATES.
            threshold_override: Override the default threshold.

        Returns:
            CompoundCondition.

        Raises:
            ValueError: If template not found.
        """
        template = ALERT_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")

        metric = template.get("metric", "price")
        operator = template.get("operator", ComparisonOperator.GT)
        threshold = threshold_override if threshold_override is not None else template.get("threshold", 0.0)

        condition = AlertCondition(
            metric=metric,
            operator=operator,
            threshold=threshold,
        )

        return CompoundCondition(
            conditions=[condition],
            logical_operator=LogicalOperator.AND,
        )

    @staticmethod
    def simple(
        metric: str,
        operator: ComparisonOperator,
        threshold: float,
    ) -> CompoundCondition:
        """Create a simple single-condition.

        Args:
            metric: Metric name.
            operator: Comparison operator.
            threshold: Threshold value.

        Returns:
            CompoundCondition with one condition.
        """
        condition = AlertCondition(
            metric=metric,
            operator=operator,
            threshold=threshold,
        )
        return CompoundCondition(
            conditions=[condition],
            logical_operator=LogicalOperator.AND,
        )

    @staticmethod
    def compound(
        conditions: list[tuple[str, ComparisonOperator, float]],
        logical_operator: LogicalOperator = LogicalOperator.AND,
    ) -> CompoundCondition:
        """Create a compound condition from multiple specs.

        Args:
            conditions: List of (metric, operator, threshold) tuples.
            logical_operator: AND or OR.

        Returns:
            CompoundCondition.
        """
        alert_conditions = [
            AlertCondition(metric=m, operator=op, threshold=t)
            for m, op, t in conditions
        ]
        return CompoundCondition(
            conditions=alert_conditions,
            logical_operator=logical_operator,
        )

    @staticmethod
    def price_above(threshold: float) -> CompoundCondition:
        """Price > threshold."""
        return ConditionBuilder.simple("price", ComparisonOperator.GT, threshold)

    @staticmethod
    def price_below(threshold: float) -> CompoundCondition:
        """Price < threshold."""
        return ConditionBuilder.simple("price", ComparisonOperator.LT, threshold)

    @staticmethod
    def price_crosses_above(threshold: float) -> CompoundCondition:
        """Price crosses above threshold."""
        return ConditionBuilder.simple(
            "price", ComparisonOperator.CROSSES_ABOVE, threshold,
        )

    @staticmethod
    def price_crosses_below(threshold: float) -> CompoundCondition:
        """Price crosses below threshold."""
        return ConditionBuilder.simple(
            "price", ComparisonOperator.CROSSES_BELOW, threshold,
        )

    @staticmethod
    def pct_change(threshold: float, direction: str = "up") -> CompoundCondition:
        """Percentage change condition.

        Args:
            threshold: Percentage threshold (e.g., 5.0 for 5%).
            direction: 'up' for positive change, 'down' for negative.

        Returns:
            CompoundCondition.
        """
        if direction == "up":
            op = ComparisonOperator.PCT_CHANGE_GT
        else:
            op = ComparisonOperator.PCT_CHANGE_LT
            threshold = -abs(threshold)

        return ConditionBuilder.simple("price", op, threshold)


class ConditionEvaluator:
    """Evaluates conditions against market data.

    Maintains state for cross-detection and provides batch evaluation.
    """

    def __init__(self) -> None:
        self._state: dict[str, dict[str, float]] = {}

    def evaluate(
        self,
        alert_id: str,
        conditions: CompoundCondition,
        values: dict[str, float],
    ) -> bool:
        """Evaluate conditions for an alert.

        Args:
            alert_id: Alert identifier (for state tracking).
            conditions: Compound condition to evaluate.
            values: Current metric values.

        Returns:
            True if conditions are met.
        """
        # Restore previous values for cross detection
        prev_state = self._state.get(alert_id, {})
        for cond in conditions.conditions:
            if cond.previous_value is None and cond.metric in prev_state:
                cond.previous_value = prev_state[cond.metric]

        result = conditions.evaluate(values)

        # Save current state
        self._state[alert_id] = dict(values)

        return result

    def clear_state(self, alert_id: str) -> None:
        """Clear stored state for an alert.

        Args:
            alert_id: Alert to clear state for.
        """
        self._state.pop(alert_id, None)

    def clear_all(self) -> None:
        """Clear all stored state."""
        self._state.clear()
