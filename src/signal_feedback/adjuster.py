"""Weight Adjuster — adaptive signal source weighting based on performance.

Uses rolling Sharpe ratios from PerformanceTracker to adjust
signal fusion weights, giving more influence to profitable sources
and decaying underperformers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.signal_feedback.tracker import PerformanceTracker, SourcePerformance


@dataclass
class AdjusterConfig:
    """Configuration for the weight adjuster.

    Attributes:
        learning_rate: How fast weights adapt (0-1). Higher = faster.
        min_weight: Minimum weight for any source (prevents total exclusion).
        max_weight: Maximum weight for any source (prevents over-reliance).
        sharpe_target: Sharpe ratio target for full weight.
        decay_rate: Per-period decay for underperforming sources.
        min_trades_to_adjust: Minimum trades before adjusting weights.
        normalize: Whether to normalize weights to sum to 1.0.
    """

    learning_rate: float = 0.1
    min_weight: float = 0.02
    max_weight: float = 0.40
    sharpe_target: float = 1.5
    decay_rate: float = 0.95
    min_trades_to_adjust: int = 20
    normalize: bool = True


@dataclass
class WeightUpdate:
    """Result of a weight adjustment cycle.

    Attributes:
        old_weights: Previous weights.
        new_weights: Adjusted weights.
        adjustments: Per-source adjustment details.
        timestamp: When the update was computed.
    """

    old_weights: dict[str, float] = field(default_factory=dict)
    new_weights: dict[str, float] = field(default_factory=dict)
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_weights": {k: round(v, 4) for k, v in self.old_weights.items()},
            "new_weights": {k: round(v, 4) for k, v in self.new_weights.items()},
            "adjustments": self.adjustments,
            "timestamp": self.timestamp.isoformat(),
        }


class WeightAdjuster:
    """Adjusts signal fusion weights based on source performance.

    Uses a Sharpe ratio-based scoring system:
    - Sources with Sharpe > target get increased weight
    - Sources with Sharpe < 0 get decayed weight
    - Weights are clamped to [min_weight, max_weight] and normalized

    Args:
        config: AdjusterConfig with learning rate and bounds.
        tracker: PerformanceTracker with source metrics.

    Example:
        adjuster = WeightAdjuster(tracker=tracker)
        update = adjuster.compute_weights(current_weights)
        fusion_config.source_weights = update.new_weights
    """

    def __init__(
        self,
        config: AdjusterConfig | None = None,
        tracker: PerformanceTracker | None = None,
    ) -> None:
        self.config = config or AdjusterConfig()
        self.tracker = tracker or PerformanceTracker()
        self._history: list[WeightUpdate] = []

    def compute_weights(
        self, current_weights: dict[str, float]
    ) -> WeightUpdate:
        """Compute adjusted weights based on current performance.

        Args:
            current_weights: Current fusion weights by source name.

        Returns:
            WeightUpdate with old and new weights.
        """
        new_weights = dict(current_weights)
        adjustments = []

        performances = self.tracker.get_all_performance()

        for source, weight in current_weights.items():
            perf = performances.get(source)
            if perf is None or perf.trade_count < self.config.min_trades_to_adjust:
                adjustments.append({
                    "source": source,
                    "action": "no_change",
                    "reason": f"Insufficient trades ({perf.trade_count if perf else 0} < {self.config.min_trades_to_adjust})",
                    "old_weight": weight,
                    "new_weight": weight,
                })
                continue

            # Compute adjustment based on Sharpe ratio
            sharpe = perf.sharpe_ratio
            target = self.config.sharpe_target

            if sharpe >= target:
                # Outperforming: increase weight
                factor = 1.0 + self.config.learning_rate * (sharpe / target - 1.0)
                action = "increase"
            elif sharpe > 0:
                # Positive but below target: slight increase
                factor = 1.0 + self.config.learning_rate * 0.5 * (sharpe / target)
                action = "slight_increase"
            elif sharpe > -0.5:
                # Slightly negative: decay
                factor = self.config.decay_rate
                action = "decay"
            else:
                # Significantly negative: stronger decay
                factor = self.config.decay_rate ** 2
                action = "strong_decay"

            new_w = weight * factor
            new_w = max(self.config.min_weight, min(self.config.max_weight, new_w))
            new_weights[source] = new_w

            adjustments.append({
                "source": source,
                "action": action,
                "sharpe": round(sharpe, 2),
                "factor": round(factor, 3),
                "old_weight": round(weight, 4),
                "new_weight": round(new_w, 4),
                "win_rate": round(perf.win_rate, 3),
                "trade_count": perf.trade_count,
            })

        # Normalize
        if self.config.normalize and new_weights:
            total = sum(new_weights.values())
            if total > 0:
                new_weights = {k: v / total for k, v in new_weights.items()}

        update = WeightUpdate(
            old_weights=dict(current_weights),
            new_weights=new_weights,
            adjustments=adjustments,
        )
        self._history.append(update)
        return update

    def get_weight_history(self, limit: int = 20) -> list[dict]:
        """Get recent weight adjustment history."""
        return [u.to_dict() for u in self._history[-limit:]]

    def get_recommended_weights(
        self, sources: list[str]
    ) -> dict[str, float]:
        """Generate recommended weights from scratch based on performance.

        Uses Sharpe-proportional allocation for sources with enough data,
        and equal weighting for sources without sufficient history.
        """
        performances = self.tracker.get_all_performance()
        weights = {}
        has_data = []
        no_data = []

        for source in sources:
            perf = performances.get(source)
            if perf and perf.trade_count >= self.config.min_trades_to_adjust:
                has_data.append((source, perf))
            else:
                no_data.append(source)

        if has_data:
            # Sharpe-proportional allocation
            min_sharpe = min(p.sharpe_ratio for _, p in has_data)
            shifted = [(s, max(0.01, p.sharpe_ratio - min_sharpe + 0.5)) for s, p in has_data]
            total_sharpe = sum(v for _, v in shifted)
            data_budget = 1.0 - len(no_data) * self.config.min_weight

            for source, sharpe_adj in shifted:
                w = (sharpe_adj / total_sharpe) * data_budget
                weights[source] = max(self.config.min_weight, min(self.config.max_weight, w))
        else:
            data_budget = 1.0

        # Equal weight for sources without data
        equal_w = data_budget / max(len(no_data), 1) if not has_data else self.config.min_weight
        for source in no_data:
            weights[source] = equal_w

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights
