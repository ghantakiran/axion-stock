"""Short Interest Analysis.

Tracks short interest ratios, days-to-cover, momentum,
and short squeeze risk scoring.
"""

import logging
from typing import Optional

import numpy as np

from src.crowding.config import ShortInterestConfig, SqueezeRisk, DEFAULT_SHORT_INTEREST_CONFIG
from src.crowding.models import ShortInterestData, ShortSqueezeScore

logger = logging.getLogger(__name__)


class ShortInterestAnalyzer:
    """Analyzes short interest and squeeze risk."""

    def __init__(self, config: Optional[ShortInterestConfig] = None) -> None:
        self.config = config or DEFAULT_SHORT_INTEREST_CONFIG
        self._history: dict[str, list[ShortInterestData]] = {}

    def add_data(self, data: ShortInterestData) -> None:
        """Record short interest data point."""
        if data.symbol not in self._history:
            self._history[data.symbol] = []
        self._history[data.symbol].append(data)

    def add_data_list(self, data_list: list[ShortInterestData]) -> None:
        """Record multiple data points."""
        for d in data_list:
            self.add_data(d)

    def analyze(self, symbol: str) -> ShortSqueezeScore:
        """Compute short squeeze risk score.

        Args:
            symbol: Stock symbol.

        Returns:
            ShortSqueezeScore with risk assessment.
        """
        history = self._history.get(symbol, [])
        if not history:
            return self._empty_score(symbol)

        latest = history[-1]
        si_ratio = latest.si_ratio
        dtc = latest.days_to_cover
        ctb = latest.cost_to_borrow

        # SI momentum
        momentum = self._compute_momentum(history)

        # Squeeze score components
        si_component = min(si_ratio / self.config.squeeze_si_threshold, 1.0)
        dtc_component = min(dtc / (self.config.squeeze_dtc_threshold * 2), 1.0)
        ctb_component = min(ctb / 0.50, 1.0)  # normalize to 50% CTB
        momentum_component = max(0, min(momentum, 1.0))  # only positive momentum

        # Weighted squeeze score
        squeeze_score = (
            0.35 * si_component
            + 0.25 * dtc_component
            + 0.20 * ctb_component
            + 0.20 * momentum_component
        )
        squeeze_score = min(max(squeeze_score, 0.0), 1.0)

        risk = self._classify_risk(squeeze_score)

        return ShortSqueezeScore(
            symbol=symbol,
            squeeze_score=round(squeeze_score, 4),
            risk=risk,
            si_ratio=round(si_ratio, 4),
            days_to_cover=round(dtc, 2),
            si_momentum=round(momentum, 4),
            cost_to_borrow=round(ctb, 4),
        )

    def _compute_momentum(self, history: list[ShortInterestData]) -> float:
        """Compute SI momentum (rate of change in SI ratio)."""
        window = min(self.config.momentum_window, len(history))
        if window < 2:
            return 0.0

        recent = history[-window:]
        ratios = [d.si_ratio for d in recent]

        if ratios[0] == 0:
            return 1.0 if ratios[-1] > 0 else 0.0
        return (ratios[-1] - ratios[0]) / ratios[0]

    def _classify_risk(self, score: float) -> SqueezeRisk:
        """Classify squeeze risk from score."""
        if score >= 0.75:
            return SqueezeRisk.HIGH
        elif score >= 0.50:
            return SqueezeRisk.ELEVATED
        elif score >= 0.25:
            return SqueezeRisk.MODERATE
        return SqueezeRisk.LOW

    def get_history(self, symbol: str) -> list[ShortInterestData]:
        return self._history.get(symbol, [])

    def reset(self) -> None:
        self._history.clear()

    def _empty_score(self, symbol: str) -> ShortSqueezeScore:
        return ShortSqueezeScore(symbol=symbol, squeeze_score=0.0)
