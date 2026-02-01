"""Volatility Regime Detection.

Classifies current volatility environment into regimes (LOW, NORMAL,
HIGH, EXTREME) based on z-score relative to historical distribution.
Tracks regime persistence and transition signals.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.volatility.config import (
    RegimeConfig,
    VolRegime,
    DEFAULT_REGIME_CONFIG,
)
from src.volatility.models import VolRegimeState

logger = logging.getLogger(__name__)


class VolRegimeDetector:
    """Detects and tracks volatility regime changes."""

    def __init__(self, config: Optional[RegimeConfig] = None) -> None:
        self.config = config or DEFAULT_REGIME_CONFIG
        self._prev_regime: Optional[VolRegime] = None
        self._days_in_regime: int = 0
        self._history: list[VolRegimeState] = []

    def detect(
        self,
        returns: pd.Series,
        window: int = 21,
        as_of_date: Optional[date] = None,
    ) -> VolRegimeState:
        """Detect current volatility regime.

        Args:
            returns: Returns series.
            window: Window for current vol estimation.
            as_of_date: Date for the assessment.

        Returns:
            VolRegimeState with classification.
        """
        lookback = self.config.lookback_window
        if len(returns) < window:
            return VolRegimeState(date=as_of_date)

        # Current vol (annualized)
        ann_factor = 252.0
        current_vol = float(returns.iloc[-window:].std(ddof=1) * np.sqrt(ann_factor))

        # Historical vol distribution
        if len(returns) >= lookback:
            rolling_vol = returns.rolling(window).std(ddof=1) * np.sqrt(ann_factor)
            rolling_vol = rolling_vol.dropna()
        else:
            rolling_vol = returns.rolling(window).std(ddof=1) * np.sqrt(ann_factor)
            rolling_vol = rolling_vol.dropna()

        if len(rolling_vol) == 0:
            return VolRegimeState(current_vol=current_vol, date=as_of_date)

        avg_vol = float(rolling_vol.mean())
        std_vol = float(rolling_vol.std(ddof=1))

        # Z-score
        z_score = (current_vol - avg_vol) / std_vol if std_vol > 0 else 0.0

        # Percentile
        pct = float((rolling_vol < current_vol).sum() / len(rolling_vol) * 100)

        # Classify
        regime = self._classify(z_score)

        # Track regime persistence
        regime_changed = False
        if self._prev_regime is not None and regime != self._prev_regime:
            regime_changed = True
            self._days_in_regime = 1
        else:
            self._days_in_regime += 1

        prev = self._prev_regime
        self._prev_regime = regime

        state = VolRegimeState(
            regime=regime,
            current_vol=round(current_vol, 6),
            avg_vol=round(avg_vol, 6),
            z_score=round(z_score, 2),
            percentile=round(pct, 1),
            days_in_regime=self._days_in_regime,
            date=as_of_date or date.today(),
            prev_regime=prev,
            regime_changed=regime_changed,
        )

        self._history.append(state)
        return state

    def _classify(self, z_score: float) -> VolRegime:
        """Classify z-score into regime."""
        if z_score >= self.config.extreme_threshold:
            return VolRegime.EXTREME
        elif z_score >= self.config.high_threshold:
            return VolRegime.HIGH
        elif z_score <= self.config.low_threshold:
            return VolRegime.LOW
        else:
            return VolRegime.NORMAL

    def get_history(self) -> list[VolRegimeState]:
        """Return regime history."""
        return list(self._history)

    def reset(self) -> None:
        """Reset detector state."""
        self._prev_regime = None
        self._days_in_regime = 0
        self._history.clear()

    def regime_distribution(
        self,
        returns: pd.Series,
        window: int = 21,
    ) -> dict[VolRegime, float]:
        """Compute fraction of time spent in each regime.

        Args:
            returns: Full returns history.
            window: Vol estimation window.

        Returns:
            Dict mapping regime to fraction (0-1).
        """
        ann_factor = 252.0
        rolling_vol = returns.rolling(window).std(ddof=1) * np.sqrt(ann_factor)
        rolling_vol = rolling_vol.dropna()

        if len(rolling_vol) == 0:
            return {r: 0.0 for r in VolRegime}

        avg_vol = float(rolling_vol.mean())
        std_vol = float(rolling_vol.std(ddof=1))

        counts: dict[VolRegime, int] = {r: 0 for r in VolRegime}
        for v in rolling_vol:
            z = (v - avg_vol) / std_vol if std_vol > 0 else 0.0
            regime = self._classify(z)
            counts[regime] += 1

        total = len(rolling_vol)
        return {r: round(c / total, 4) for r, c in counts.items()}
