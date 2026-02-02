"""Position Crowding Detection.

Scores crowding from ownership concentration, tracks
crowding momentum, and classifies risk levels.
"""

import logging
from typing import Optional

import numpy as np

from src.crowding.config import DetectorConfig, CrowdingLevel, DEFAULT_DETECTOR_CONFIG
from src.crowding.models import CrowdingScore

logger = logging.getLogger(__name__)


class CrowdingDetector:
    """Detects position crowding from ownership data."""

    def __init__(self, config: Optional[DetectorConfig] = None) -> None:
        self.config = config or DEFAULT_DETECTOR_CONFIG
        self._history: dict[str, list[CrowdingScore]] = {}

    def score(
        self,
        symbol: str,
        ownership_pcts: list[float],
        n_holders: int = 0,
        previous_scores: Optional[list[float]] = None,
    ) -> CrowdingScore:
        """Compute crowding score for a symbol.

        Args:
            symbol: Stock symbol.
            ownership_pcts: List of holder ownership percentages.
            n_holders: Total number of institutional holders.
            previous_scores: Historical crowding scores for momentum.

        Returns:
            CrowdingScore with level and metrics.
        """
        if not ownership_pcts:
            return self._empty_score(symbol)

        # HHI concentration
        total = sum(ownership_pcts)
        if total == 0:
            return self._empty_score(symbol)

        shares = [p / total for p in ownership_pcts]
        hhi = sum(s * s for s in shares)

        # Crowding score: blend of concentration and breadth
        # High HHI + many holders = crowded
        breadth = min(n_holders / 100, 1.0) if n_holders > 0 else len(ownership_pcts) / 50
        breadth = min(breadth, 1.0)

        # Total institutional ownership as factor
        ownership_factor = min(total / 100, 1.0)

        score = 0.4 * hhi + 0.3 * breadth + 0.3 * ownership_factor
        score = min(max(score, 0.0), 1.0)

        # Classify level
        level = self._classify(score)

        # Momentum from historical scores
        momentum = 0.0
        is_decrowding = False
        if previous_scores and len(previous_scores) >= 2:
            momentum = previous_scores[-1] - previous_scores[0]
            is_decrowding = momentum < -0.05  # declining crowding

        # Historical percentile
        percentile = self._compute_percentile(symbol, score)

        result = CrowdingScore(
            symbol=symbol,
            score=round(score, 4),
            level=level,
            n_holders=n_holders or len(ownership_pcts),
            concentration=round(hhi, 4),
            momentum=round(momentum, 4),
            percentile=round(percentile, 4),
            is_decrowding=is_decrowding,
        )

        if symbol not in self._history:
            self._history[symbol] = []
        self._history[symbol].append(result)

        return result

    def _classify(self, score: float) -> CrowdingLevel:
        """Classify crowding level from score."""
        if score >= self.config.extreme_threshold:
            return CrowdingLevel.EXTREME
        elif score >= self.config.high_threshold:
            return CrowdingLevel.HIGH
        elif score >= self.config.medium_threshold:
            return CrowdingLevel.MEDIUM
        return CrowdingLevel.LOW

    def _compute_percentile(self, symbol: str, score: float) -> float:
        """Compute historical percentile of current score."""
        history = self._history.get(symbol, [])
        if not history:
            return 50.0

        scores = [s.score for s in history]
        below = sum(1 for s in scores if s < score)
        return below / len(scores) * 100

    def get_history(self, symbol: str) -> list[CrowdingScore]:
        return self._history.get(symbol, [])

    def reset(self) -> None:
        self._history.clear()

    def _empty_score(self, symbol: str) -> CrowdingScore:
        return CrowdingScore(symbol=symbol, score=0.0)
