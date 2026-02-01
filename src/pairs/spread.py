"""Spread Analysis for Pairs Trading.

Computes spread z-scores, half-life of mean reversion,
Hurst exponent, and trading signals.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.pairs.config import (
    SpreadConfig,
    SpreadMethod,
    PairSignalType,
    DEFAULT_SPREAD_CONFIG,
)
from src.pairs.models import SpreadAnalysis, PairSignal

logger = logging.getLogger(__name__)


class SpreadAnalyzer:
    """Analyzes spread dynamics for pair trading."""

    def __init__(self, config: Optional[SpreadConfig] = None) -> None:
        self.config = config or DEFAULT_SPREAD_CONFIG

    def compute_spread(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        hedge_ratio: float = 1.0,
        intercept: float = 0.0,
    ) -> pd.Series:
        """Compute the spread between two price series.

        Args:
            prices_a: Price series for asset A (long leg).
            prices_b: Price series for asset B (short leg).
            hedge_ratio: Hedge ratio (beta).
            intercept: Regression intercept.

        Returns:
            Spread series.
        """
        n = min(len(prices_a), len(prices_b))
        a = prices_a.values[-n:].astype(float)
        b = prices_b.values[-n:].astype(float)

        if self.config.method == SpreadMethod.RATIO:
            spread = a / (b * hedge_ratio) if hedge_ratio != 0 else a - b
        else:
            spread = a - hedge_ratio * b - intercept

        return pd.Series(spread, index=prices_a.index[-n:])

    def analyze(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        hedge_ratio: float = 1.0,
        intercept: float = 0.0,
        asset_a: str = "",
        asset_b: str = "",
    ) -> SpreadAnalysis:
        """Full spread analysis.

        Args:
            prices_a: Price series for asset A.
            prices_b: Price series for asset B.
            hedge_ratio: Hedge ratio from cointegration.
            intercept: Regression intercept.
            asset_a: Asset A symbol.
            asset_b: Asset B symbol.

        Returns:
            SpreadAnalysis with z-score, half-life, Hurst, and signal.
        """
        spread = self.compute_spread(prices_a, prices_b, hedge_ratio, intercept)
        spread_values = spread.values

        if len(spread_values) < self.config.zscore_window:
            return SpreadAnalysis(asset_a=asset_a, asset_b=asset_b)

        # Z-score
        window = self.config.zscore_window
        recent = spread_values[-window:]
        spread_mean = float(np.mean(recent))
        spread_std = float(np.std(recent, ddof=1))
        current = float(spread_values[-1])

        zscore = (current - spread_mean) / spread_std if spread_std > 0 else 0.0

        # Half-life
        half_life = self.compute_half_life(spread_values)

        # Hurst exponent
        hurst = self.compute_hurst(spread_values)

        # Signal
        signal = self._generate_signal(zscore)

        return SpreadAnalysis(
            asset_a=asset_a,
            asset_b=asset_b,
            current_spread=round(current, 6),
            spread_mean=round(spread_mean, 6),
            spread_std=round(spread_std, 6),
            zscore=round(zscore, 4),
            half_life=round(half_life, 2),
            hurst_exponent=round(hurst, 4),
            signal=signal,
        )

    def compute_zscore_series(
        self,
        spread: pd.Series,
    ) -> pd.Series:
        """Compute rolling z-score of spread.

        Args:
            spread: Spread time series.

        Returns:
            Z-score series.
        """
        window = self.config.zscore_window
        rolling_mean = spread.rolling(window).mean()
        rolling_std = spread.rolling(window).std(ddof=1)
        zscore = (spread - rolling_mean) / rolling_std.replace(0, np.nan)
        return zscore.fillna(0.0)

    def compute_half_life(self, spread: np.ndarray) -> float:
        """Estimate half-life of mean reversion via Ornstein-Uhlenbeck.

        Regresses delta_spread on lagged spread:
        delta_S = theta * (S_{t-1} - mu) + eps
        half_life = -ln(2) / ln(1 + theta)

        Args:
            spread: Spread values.

        Returns:
            Half-life in periods. Returns max_half_life + 1 if not mean-reverting.
        """
        if len(spread) < 10:
            return float(self.config.max_half_life + 1)

        y = np.diff(spread)
        x = spread[:-1]

        x_mean = x.mean()
        x_demean = x - x_mean

        var_x = np.sum(x_demean ** 2)
        if var_x == 0:
            return float(self.config.max_half_life + 1)

        theta = float(np.sum(x_demean * y) / var_x)

        if theta >= 0:
            return float(self.config.max_half_life + 1)

        half_life = -np.log(2) / np.log(1 + theta)
        return max(float(half_life), 0.1)

    def compute_hurst(self, spread: np.ndarray, max_lag: int = 20) -> float:
        """Estimate Hurst exponent via rescaled range (R/S) method.

        H < 0.5: mean-reverting, H = 0.5: random walk, H > 0.5: trending.

        Args:
            spread: Spread values.
            max_lag: Maximum lag for R/S calculation.

        Returns:
            Hurst exponent estimate.
        """
        n = len(spread)
        if n < 20:
            return 0.5

        lags = range(2, min(max_lag + 1, n // 2))
        rs_values = []
        lag_values = []

        for lag in lags:
            rs = self._rescaled_range(spread, lag)
            if rs > 0:
                rs_values.append(np.log(rs))
                lag_values.append(np.log(lag))

        if len(lag_values) < 2:
            return 0.5

        # Linear regression of log(R/S) on log(lag)
        x = np.array(lag_values)
        y = np.array(rs_values)
        n_pts = len(x)

        x_mean = x.mean()
        y_mean = y.mean()
        cov = np.sum((x - x_mean) * (y - y_mean))
        var = np.sum((x - x_mean) ** 2)

        if var == 0:
            return 0.5

        hurst = float(cov / var)
        return max(0.0, min(1.0, hurst))

    def generate_signal(
        self,
        zscore: float,
        hedge_ratio: float = 1.0,
        spread: float = 0.0,
        asset_a: str = "",
        asset_b: str = "",
    ) -> PairSignal:
        """Generate a trading signal from current z-score.

        Args:
            zscore: Current z-score of spread.
            hedge_ratio: Hedge ratio for position sizing.
            spread: Current spread value.
            asset_a: Asset A symbol.
            asset_b: Asset B symbol.

        Returns:
            PairSignal with direction and confidence.
        """
        signal_type = self._generate_signal(zscore)
        confidence = self._signal_confidence(zscore)

        return PairSignal(
            asset_a=asset_a,
            asset_b=asset_b,
            signal=signal_type,
            zscore=round(zscore, 4),
            hedge_ratio=round(hedge_ratio, 6),
            spread=round(spread, 6),
            confidence=round(confidence, 2),
        )

    def _generate_signal(self, zscore: float) -> PairSignalType:
        """Generate signal from z-score thresholds."""
        if zscore >= self.config.entry_zscore:
            return PairSignalType.SHORT_SPREAD
        elif zscore <= -self.config.entry_zscore:
            return PairSignalType.LONG_SPREAD
        elif abs(zscore) <= self.config.exit_zscore:
            return PairSignalType.EXIT
        return PairSignalType.NO_SIGNAL

    def _signal_confidence(self, zscore: float) -> float:
        """Compute signal confidence from z-score magnitude."""
        abs_z = abs(zscore)
        if abs_z >= self.config.stop_zscore:
            return 0.3  # Low confidence at extreme — may be breakdown
        elif abs_z >= self.config.entry_zscore:
            # Scale from 0.5 to 1.0 between entry and stop
            frac = (abs_z - self.config.entry_zscore) / (self.config.stop_zscore - self.config.entry_zscore)
            return 0.9 - frac * 0.4
        elif abs_z <= self.config.exit_zscore:
            return 0.8  # Good confidence for exit
        return 0.0

    def _rescaled_range(self, data: np.ndarray, lag: int) -> float:
        """Compute rescaled range for a given lag."""
        n = len(data)
        n_segments = n // lag
        if n_segments == 0:
            return 0.0

        rs_sum = 0.0
        count = 0

        for i in range(n_segments):
            segment = data[i * lag: (i + 1) * lag]
            mean_seg = segment.mean()
            devs = np.cumsum(segment - mean_seg)
            r = devs.max() - devs.min()
            s = segment.std(ddof=1)
            if s > 0:
                rs_sum += r / s
                count += 1

        return rs_sum / count if count > 0 else 0.0
