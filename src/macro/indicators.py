"""Economic Indicator Tracking.

Ingests economic indicators, computes surprises, momentum,
and builds composite economic indices.
"""

import logging
from typing import Optional

import numpy as np

from src.macro.config import IndicatorConfig, IndicatorType, DEFAULT_INDICATOR_CONFIG
from src.macro.models import EconomicIndicator, IndicatorSummary

logger = logging.getLogger(__name__)


class IndicatorTracker:
    """Tracks and scores economic indicators."""

    def __init__(self, config: Optional[IndicatorConfig] = None) -> None:
        self.config = config or DEFAULT_INDICATOR_CONFIG
        self._history: dict[str, list[EconomicIndicator]] = {}

    def add_indicator(self, indicator: EconomicIndicator) -> None:
        """Record an indicator reading."""
        if indicator.name not in self._history:
            self._history[indicator.name] = []
        self._history[indicator.name].append(indicator)

    def add_indicators(self, indicators: list[EconomicIndicator]) -> None:
        """Record multiple indicator readings."""
        for ind in indicators:
            self.add_indicator(ind)

    def summarize(self) -> IndicatorSummary:
        """Compute composite indicator summary.

        Returns:
            IndicatorSummary with composite index and breadth.
        """
        if not self._history:
            return self._empty_summary()

        improving = 0
        deteriorating = 0
        stable = 0
        leading_scores = []
        coincident_scores = []
        lagging_scores = []

        for name, readings in self._history.items():
            if len(readings) < 2:
                stable += 1
                continue

            latest = readings[-1]
            momentum = self._compute_momentum(readings)

            if momentum > 0.01:
                improving += 1
            elif momentum < -0.01:
                deteriorating += 1
            else:
                stable += 1

            score = self._normalize_score(momentum)
            if latest.indicator_type == IndicatorType.LEADING:
                leading_scores.append(score)
            elif latest.indicator_type == IndicatorType.COINCIDENT:
                coincident_scores.append(score)
            else:
                lagging_scores.append(score)

        # Component scores
        leading = float(np.mean(leading_scores)) if leading_scores else 0.0
        coincident = float(np.mean(coincident_scores)) if coincident_scores else 0.0
        lagging = float(np.mean(lagging_scores)) if lagging_scores else 0.0

        # Weighted composite
        w = self.config.composite_weights
        composite = (
            w.get("leading", 0.5) * leading
            + w.get("coincident", 0.3) * coincident
            + w.get("lagging", 0.2) * lagging
        )

        return IndicatorSummary(
            composite_index=round(composite, 4),
            n_improving=improving,
            n_deteriorating=deteriorating,
            n_stable=stable,
            leading_score=round(leading, 4),
            coincident_score=round(coincident, 4),
            lagging_score=round(lagging, 4),
        )

    def get_surprises(self) -> list[tuple[str, float]]:
        """Get latest surprise for each indicator.

        Returns:
            List of (name, surprise) tuples sorted by absolute surprise.
        """
        surprises = []
        for name, readings in self._history.items():
            if readings:
                latest = readings[-1]
                surprises.append((name, latest.surprise))

        surprises.sort(key=lambda x: abs(x[1]), reverse=True)
        return surprises

    def _compute_momentum(self, readings: list[EconomicIndicator]) -> float:
        """Compute indicator momentum over configured window."""
        window = min(self.config.momentum_window, len(readings))
        recent = readings[-window:]

        if len(recent) < 2:
            return 0.0

        values = np.array([r.value for r in recent])
        # Simple linear regression slope
        x = np.arange(len(values), dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(values)

        num = np.sum((x - x_mean) * (values - y_mean))
        den = np.sum((x - x_mean) ** 2)

        if den == 0:
            return 0.0

        slope = num / den
        # Normalize by mean value
        if y_mean != 0:
            return float(slope / abs(y_mean))
        return float(slope)

    def _normalize_score(self, momentum: float) -> float:
        """Normalize momentum to [-1, 1] range using tanh."""
        return float(np.tanh(momentum * 10))

    def get_history(self, name: str) -> list[EconomicIndicator]:
        return self._history.get(name, [])

    def reset(self) -> None:
        self._history.clear()

    def _empty_summary(self) -> IndicatorSummary:
        return IndicatorSummary(
            composite_index=0.0,
            n_improving=0, n_deteriorating=0, n_stable=0,
            leading_score=0.0, coincident_score=0.0, lagging_score=0.0,
        )
