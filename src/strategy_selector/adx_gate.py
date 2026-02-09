"""ADX Gate — determines trend strength to route between strategies.

Uses Average Directional Index (ADX) to decide whether the market
is trending (use EMA Cloud) or ranging (use mean-reversion).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TrendStrength(str, Enum):
    """Classification of trend strength from ADX."""

    STRONG_TREND = "strong_trend"      # ADX > 40: strong directional movement
    MODERATE_TREND = "moderate_trend"   # ADX 25-40: moderate trend
    WEAK_TREND = "weak_trend"          # ADX 15-25: weak/starting trend
    NO_TREND = "no_trend"              # ADX < 15: ranging/choppy


@dataclass
class ADXConfig:
    """Configuration for the ADX gate.

    Attributes:
        period: ADX calculation period.
        strong_threshold: ADX above this = strong trend.
        moderate_threshold: ADX above this = moderate trend.
        weak_threshold: ADX above this = weak trend.
        trend_strategy: Strategy to use in trending conditions.
        range_strategy: Strategy to use in ranging conditions.
    """

    period: int = 14
    strong_threshold: float = 40.0
    moderate_threshold: float = 25.0
    weak_threshold: float = 15.0
    trend_strategy: str = "ema_cloud"
    range_strategy: str = "mean_reversion"


class ADXGate:
    """ADX-based strategy gate.

    Computes ADX from price data and classifies trend strength.
    Routes to trend-following or mean-reversion strategy accordingly.

    Args:
        config: ADXConfig with thresholds.

    Example:
        gate = ADXGate()
        strength = gate.compute(highs, lows, closes)
        strategy = gate.select_strategy(strength)
    """

    def __init__(self, config: ADXConfig | None = None) -> None:
        self.config = config or ADXConfig()

    def compute(
        self, highs: list[float], lows: list[float], closes: list[float]
    ) -> TrendStrength:
        """Compute ADX and classify trend strength.

        Args:
            highs: High prices (oldest first).
            lows: Low prices.
            closes: Close prices.

        Returns:
            TrendStrength classification.
        """
        adx = self.compute_adx(highs, lows, closes)
        return self.classify(adx)

    def compute_adx(
        self, highs: list[float], lows: list[float], closes: list[float]
    ) -> float:
        """Compute the ADX value from OHLC data.

        Uses Wilder's smoothing for directional movement calculation.
        """
        period = self.config.period
        min_len = period * 2 + 1
        if len(highs) < min_len or len(lows) < min_len or len(closes) < min_len:
            return 0.0

        n = len(closes)

        # Calculate True Range and Directional Movement
        plus_dm = []
        minus_dm = []
        true_ranges = []

        for i in range(1, n):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]

            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return 0.0

        # Wilder's smoothing
        atr = sum(true_ranges[:period]) / period
        smooth_plus = sum(plus_dm[:period]) / period
        smooth_minus = sum(minus_dm[:period]) / period

        dx_values = []

        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period
            smooth_plus = (smooth_plus * (period - 1) + plus_dm[i]) / period
            smooth_minus = (smooth_minus * (period - 1) + minus_dm[i]) / period

            if atr > 0:
                plus_di = smooth_plus / atr * 100
                minus_di = smooth_minus / atr * 100
            else:
                plus_di = 0.0
                minus_di = 0.0

            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx = abs(plus_di - minus_di) / di_sum * 100
            else:
                dx = 0.0
            dx_values.append(dx)

        if len(dx_values) < period:
            return sum(dx_values) / max(len(dx_values), 1)

        # Smooth DX to get ADX
        adx = sum(dx_values[:period]) / period
        for i in range(period, len(dx_values)):
            adx = (adx * (period - 1) + dx_values[i]) / period

        return adx

    def classify(self, adx: float) -> TrendStrength:
        """Classify ADX value into trend strength."""
        if adx >= self.config.strong_threshold:
            return TrendStrength.STRONG_TREND
        elif adx >= self.config.moderate_threshold:
            return TrendStrength.MODERATE_TREND
        elif adx >= self.config.weak_threshold:
            return TrendStrength.WEAK_TREND
        return TrendStrength.NO_TREND

    def select_strategy(self, strength: TrendStrength) -> str:
        """Select strategy name based on trend strength.

        Strong/moderate trend → trend-following (EMA Cloud)
        Weak/no trend → mean-reversion
        """
        if strength in (TrendStrength.STRONG_TREND, TrendStrength.MODERATE_TREND):
            return self.config.trend_strategy
        return self.config.range_strategy

    def analyze_and_select(
        self, highs: list[float], lows: list[float], closes: list[float]
    ) -> tuple[str, TrendStrength, float]:
        """Compute ADX, classify, and select strategy in one call.

        Returns:
            (strategy_name, trend_strength, adx_value)
        """
        adx = self.compute_adx(highs, lows, closes)
        strength = self.classify(adx)
        strategy = self.select_strategy(strength)
        return strategy, strength, adx
