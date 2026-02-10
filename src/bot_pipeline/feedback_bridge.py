"""PRD-176: Feedback Bridge — connects weight adjuster to the bot pipeline.

Periodically runs the WeightAdjuster to compute new fusion weights
based on source performance, then updates the FusionBridge and
records the change in the WeightStore.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.signal_feedback.adjuster import AdjusterConfig, WeightAdjuster, WeightUpdate
from src.signal_feedback.tracker import PerformanceTracker
from src.signal_feedback.weight_store import WeightStore

logger = logging.getLogger(__name__)


@dataclass
class FeedbackConfig:
    """Configuration for the feedback bridge.

    Attributes:
        adjust_every_n_trades: Run weight adjustment every N trades.
        adjuster_config: Config for the WeightAdjuster.
        auto_apply: Whether to auto-apply weight updates.
    """

    adjust_every_n_trades: int = 50
    adjuster_config: AdjusterConfig = field(default_factory=AdjusterConfig)
    auto_apply: bool = True


class FeedbackBridge:
    """Bridge between the weight adjuster and the bot pipeline.

    Tracks trade count and triggers weight adjustment at configured
    intervals. Records all weight changes in the WeightStore.

    Args:
        config: FeedbackConfig with adjustment interval.
        tracker: PerformanceTracker for source metrics.
        weight_store: WeightStore for persistence.
    """

    def __init__(
        self,
        config: FeedbackConfig | None = None,
        tracker: PerformanceTracker | None = None,
        weight_store: WeightStore | None = None,
    ) -> None:
        self.config = config or FeedbackConfig()
        self._tracker = tracker or PerformanceTracker()
        self._weight_store = weight_store or WeightStore()
        self._adjuster = WeightAdjuster(
            config=self.config.adjuster_config,
            tracker=self._tracker,
        )
        self._trade_count = 0
        self._last_update: Optional[WeightUpdate] = None
        self._current_weights: dict[str, float] = {}
        self._pending_update: Optional[WeightUpdate] = None

    def on_trade_closed(
        self, source: str, pnl: float, conviction: float = 50.0,
    ) -> Optional[WeightUpdate]:
        """Called when a trade is closed.

        Records the outcome and checks if it's time to recompute weights.

        Args:
            source: Signal source name.
            pnl: Realized P&L.
            conviction: Signal conviction score.

        Returns:
            WeightUpdate if weights were recomputed, None otherwise.
        """
        self._tracker.record_outcome(source, pnl, conviction)
        self._trade_count += 1

        if self._trade_count % self.config.adjust_every_n_trades == 0:
            return self._run_adjustment()
        return None

    def force_adjustment(self) -> WeightUpdate:
        """Force an immediate weight adjustment.

        Returns:
            The WeightUpdate result.
        """
        return self._run_adjustment()

    def get_current_weights(self) -> dict[str, float]:
        """Get the current fusion weights."""
        return dict(self._current_weights)

    def set_initial_weights(self, weights: dict[str, float]) -> None:
        """Set initial weights (before any adjustment).

        Args:
            weights: Source → weight mapping.
        """
        self._current_weights = dict(weights)
        self._weight_store.record(
            weights=weights,
            trigger="initial",
            trade_count=self._trade_count,
        )

    def get_last_update(self) -> Optional[dict]:
        """Get the last weight update details."""
        if self._last_update:
            return self._last_update.to_dict()
        return None

    def get_weight_history(self, limit: int = 50) -> list[dict]:
        """Get weight update history."""
        return self._weight_store.get_history(limit)

    def get_source_performance(self) -> dict[str, dict]:
        """Get current source performance metrics."""
        perfs = self._tracker.get_all_performance()
        return {source: p.to_dict() for source, p in perfs.items()}

    def get_trade_count(self) -> int:
        """Get total trades processed."""
        return self._trade_count

    def _run_adjustment(self) -> WeightUpdate:
        """Run the weight adjuster and record the result."""
        if not self._current_weights:
            # Initialize from recommended weights
            sources = list(self._tracker.get_all_performance().keys())
            if sources:
                self._current_weights = self._adjuster.get_recommended_weights(sources)
            else:
                self._current_weights = {"ema_cloud": 0.5, "mean_reversion": 0.5}

        update = self._adjuster.compute_weights(self._current_weights)

        if self.config.auto_apply:
            self._current_weights = dict(update.new_weights)
        else:
            self._pending_update = update

        self._last_update = update
        self._weight_store.record(
            weights=update.new_weights,
            trigger="auto",
            trade_count=self._trade_count,
        )

        logger.info(
            "Feedback loop: weights adjusted after %d trades — %s",
            self._trade_count,
            {k: round(v, 3) for k, v in update.new_weights.items()},
        )
        return update
