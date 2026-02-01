"""Correlation Regime Detection.

Detects shifts in correlation regimes (low, normal, high, crisis)
based on average correlation levels and dispersion.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np

from src.correlation.config import (
    RegimeConfig,
    RegimeType,
    DEFAULT_REGIME_CONFIG,
)
from src.correlation.models import CorrelationMatrix, CorrelationRegime

logger = logging.getLogger(__name__)


class CorrelationRegimeDetector:
    """Detects correlation regime changes.

    Classifies the current correlation environment based on
    average pairwise correlation and dispersion metrics.
    """

    def __init__(self, config: Optional[RegimeConfig] = None) -> None:
        self.config = config or DEFAULT_REGIME_CONFIG
        self._prev_regime: Optional[RegimeType] = None
        self._regime_start_date: Optional[date] = None
        self._history: list[CorrelationRegime] = []

    def detect(self, matrix: CorrelationMatrix) -> CorrelationRegime:
        """Detect current correlation regime.

        Args:
            matrix: Current correlation matrix.

        Returns:
            CorrelationRegime assessment.
        """
        avg_corr = matrix.avg_correlation
        regime = self._classify(avg_corr)

        # Compute dispersion (std dev of off-diagonal correlations)
        dispersion = 0.0
        if matrix.values is not None and matrix.n_assets >= 2:
            mask = ~np.eye(matrix.n_assets, dtype=bool)
            dispersion = float(np.std(matrix.values[mask]))

        # Detect regime change
        regime_changed = False
        if self._prev_regime is not None and regime != self._prev_regime:
            regime_changed = True
            self._regime_start_date = matrix.end_date

        # Days in regime
        days_in = 0
        if self._regime_start_date and matrix.end_date:
            days_in = (matrix.end_date - self._regime_start_date).days
        elif not self._regime_start_date:
            self._regime_start_date = matrix.end_date

        result = CorrelationRegime(
            date=matrix.end_date or date.today(),
            regime=regime,
            avg_correlation=round(avg_corr, 4),
            dispersion=round(dispersion, 4),
            prev_regime=self._prev_regime,
            regime_changed=regime_changed,
            days_in_regime=days_in,
        )

        self._prev_regime = regime
        self._history.append(result)

        return result

    def _classify(self, avg_correlation: float) -> RegimeType:
        """Classify average correlation into regime."""
        if avg_correlation >= self.config.high_threshold:
            return RegimeType.CRISIS
        elif avg_correlation >= self.config.normal_threshold:
            return RegimeType.HIGH
        elif avg_correlation >= self.config.low_threshold:
            return RegimeType.NORMAL
        else:
            return RegimeType.LOW

    def has_significant_shift(
        self,
        current: CorrelationMatrix,
        previous: CorrelationMatrix,
    ) -> bool:
        """Check if correlation has shifted significantly.

        Args:
            current: Current correlation matrix.
            previous: Previous correlation matrix.

        Returns:
            True if average correlation changed by more than threshold.
        """
        diff = abs(current.avg_correlation - previous.avg_correlation)
        return diff >= self.config.change_threshold

    @property
    def current_regime(self) -> Optional[RegimeType]:
        return self._prev_regime

    @property
    def history(self) -> list[CorrelationRegime]:
        return list(self._history)

    def reset(self) -> None:
        """Reset detector state."""
        self._prev_regime = None
        self._regime_start_date = None
        self._history.clear()
