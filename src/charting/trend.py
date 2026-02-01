"""Trend Analysis.

Computes trend direction, strength, moving averages, and crossover
signals from price data.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.charting.config import (
    TrendConfig,
    TrendDirection,
    CrossoverType,
    DEFAULT_TREND_CONFIG,
)
from src.charting.models import TrendAnalysis, MACrossover

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyzes price trends using regression and moving averages."""

    def __init__(self, config: Optional[TrendConfig] = None) -> None:
        self.config = config or DEFAULT_TREND_CONFIG

    def analyze(
        self,
        close: pd.Series,
        symbol: str = "",
    ) -> TrendAnalysis:
        """Compute full trend analysis.

        Args:
            close: Close price series.
            symbol: Asset symbol.

        Returns:
            TrendAnalysis with direction, strength, and MA values.
        """
        n = len(close)
        if n < self.config.short_window:
            return TrendAnalysis(symbol=symbol)

        prices = close.values.astype(float)

        # Linear regression on recent data
        window = min(self.config.medium_window, n)
        recent = prices[-window:]
        x = np.arange(window, dtype=float)
        slope, intercept, r_squared = self._linreg(x, recent)

        # Normalize slope as fraction of price per bar
        avg_price = float(np.mean(recent))
        norm_slope = slope / avg_price if avg_price > 0 else 0.0

        # Direction
        if norm_slope > self.config.sideways_threshold:
            direction = TrendDirection.UP
        elif norm_slope < -self.config.sideways_threshold:
            direction = TrendDirection.DOWN
        else:
            direction = TrendDirection.SIDEWAYS

        # Strength: R-squared scaled to 0-100
        strength = round(r_squared * 100, 2) if r_squared > self.config.min_r_squared else 0.0

        # Moving averages
        ma_short = float(np.mean(prices[-self.config.short_window:])) if n >= self.config.short_window else 0.0
        ma_medium = float(np.mean(prices[-self.config.medium_window:])) if n >= self.config.medium_window else 0.0
        ma_long = float(np.mean(prices[-self.config.long_window:])) if n >= self.config.long_window else 0.0

        return TrendAnalysis(
            direction=direction,
            strength=strength,
            slope=round(norm_slope, 6),
            r_squared=round(r_squared, 4),
            ma_short=round(ma_short, 4),
            ma_medium=round(ma_medium, 4),
            ma_long=round(ma_long, 4),
            symbol=symbol,
        )

    def detect_crossovers(
        self,
        close: pd.Series,
        fast_window: Optional[int] = None,
        slow_window: Optional[int] = None,
        symbol: str = "",
    ) -> list[MACrossover]:
        """Detect moving average crossovers.

        Args:
            close: Close price series.
            fast_window: Fast MA window (default: short_window).
            slow_window: Slow MA window (default: long_window).
            symbol: Asset symbol.

        Returns:
            List of MACrossover events.
        """
        fast = fast_window or self.config.short_window
        slow = slow_window or self.config.long_window
        n = len(close)
        if n < slow + 1:
            return []

        prices = close.values.astype(float)
        crossovers: list[MACrossover] = []

        # Compute rolling MAs
        fast_ma = pd.Series(prices).rolling(fast).mean().values
        slow_ma = pd.Series(prices).rolling(slow).mean().values

        for i in range(slow + 1, n):
            if np.isnan(fast_ma[i]) or np.isnan(slow_ma[i]):
                continue
            if np.isnan(fast_ma[i - 1]) or np.isnan(slow_ma[i - 1]):
                continue

            prev_diff = fast_ma[i - 1] - slow_ma[i - 1]
            curr_diff = fast_ma[i] - slow_ma[i]

            if prev_diff <= 0 and curr_diff > 0:
                crossovers.append(MACrossover(
                    crossover_type=CrossoverType.GOLDEN_CROSS,
                    fast_window=fast,
                    slow_window=slow,
                    price_at_cross=round(float(prices[i]), 4),
                    idx=i,
                    symbol=symbol,
                ))
            elif prev_diff >= 0 and curr_diff < 0:
                crossovers.append(MACrossover(
                    crossover_type=CrossoverType.DEATH_CROSS,
                    fast_window=fast,
                    slow_window=slow,
                    price_at_cross=round(float(prices[i]), 4),
                    idx=i,
                    symbol=symbol,
                ))

        return crossovers

    def compute_moving_averages(
        self,
        close: pd.Series,
        windows: Optional[list[int]] = None,
    ) -> dict[int, float]:
        """Compute current MA values for multiple windows.

        Returns:
            Dict mapping window -> current MA value.
        """
        if windows is None:
            windows = [self.config.short_window, self.config.medium_window, self.config.long_window]

        prices = close.values.astype(float)
        n = len(prices)
        result: dict[int, float] = {}

        for w in windows:
            if n >= w:
                result[w] = round(float(np.mean(prices[-w:])), 4)

        return result

    def _linreg(self, x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
        """Simple linear regression.

        Returns:
            (slope, intercept, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, 0.0, 0.0

        x_mean = np.mean(x)
        y_mean = np.mean(y)
        ss_xy = np.sum((x - x_mean) * (y - y_mean))
        ss_xx = np.sum((x - x_mean) ** 2)
        ss_yy = np.sum((y - y_mean) ** 2)

        if ss_xx == 0:
            return 0.0, float(y_mean), 0.0

        slope = float(ss_xy / ss_xx)
        intercept = float(y_mean - slope * x_mean)
        r_squared = float((ss_xy ** 2) / (ss_xx * ss_yy)) if ss_yy > 0 else 0.0

        return slope, intercept, r_squared
