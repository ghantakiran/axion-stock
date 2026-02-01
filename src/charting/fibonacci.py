"""Fibonacci Calculator.

Computes Fibonacci retracement and extension levels from swing
high/low points in price data.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.charting.config import (
    FibConfig,
    DEFAULT_FIB_CONFIG,
)
from src.charting.models import FibonacciLevels

logger = logging.getLogger(__name__)


class FibCalculator:
    """Computes Fibonacci retracement and extension levels."""

    def __init__(self, config: Optional[FibConfig] = None) -> None:
        self.config = config or DEFAULT_FIB_CONFIG

    def compute(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> FibonacciLevels:
        """Auto-detect swing points and compute Fibonacci levels.

        Args:
            high: High prices.
            low: Low prices.
            close: Close prices.
            symbol: Asset symbol.

        Returns:
            FibonacciLevels with retracements and extensions.
        """
        swing_high_idx, swing_high_val = self._find_swing_high(high)
        swing_low_idx, swing_low_val = self._find_swing_low(low)

        if swing_high_val <= swing_low_val:
            return FibonacciLevels(symbol=symbol)

        # Determine trend direction: if swing high is after swing low, uptrend
        is_uptrend = swing_high_idx > swing_low_idx

        retracements = self._compute_retracements(
            swing_high_val, swing_low_val, is_uptrend
        )
        extensions = self._compute_extensions(
            swing_high_val, swing_low_val, is_uptrend
        )

        return FibonacciLevels(
            swing_high=round(swing_high_val, 4),
            swing_low=round(swing_low_val, 4),
            swing_high_idx=swing_high_idx,
            swing_low_idx=swing_low_idx,
            retracements=retracements,
            extensions=extensions,
            is_uptrend=is_uptrend,
            symbol=symbol,
        )

    def compute_from_points(
        self,
        swing_high: float,
        swing_low: float,
        is_uptrend: bool = True,
        symbol: str = "",
    ) -> FibonacciLevels:
        """Compute Fibonacci levels from explicit swing points.

        Args:
            swing_high: Swing high price.
            swing_low: Swing low price.
            is_uptrend: True if current trend is up.
            symbol: Asset symbol.

        Returns:
            FibonacciLevels.
        """
        if swing_high <= swing_low:
            return FibonacciLevels(symbol=symbol)

        retracements = self._compute_retracements(swing_high, swing_low, is_uptrend)
        extensions = self._compute_extensions(swing_high, swing_low, is_uptrend)

        return FibonacciLevels(
            swing_high=round(swing_high, 4),
            swing_low=round(swing_low, 4),
            retracements=retracements,
            extensions=extensions,
            is_uptrend=is_uptrend,
            symbol=symbol,
        )

    def _compute_retracements(
        self,
        swing_high: float,
        swing_low: float,
        is_uptrend: bool,
    ) -> dict[float, float]:
        """Compute retracement price levels.

        In uptrend: retracement from high toward low.
        In downtrend: retracement from low toward high.
        """
        diff = swing_high - swing_low
        result: dict[float, float] = {}

        for level in self.config.retracement_levels:
            if is_uptrend:
                price = swing_high - diff * level
            else:
                price = swing_low + diff * level
            result[level] = round(price, 4)

        return result

    def _compute_extensions(
        self,
        swing_high: float,
        swing_low: float,
        is_uptrend: bool,
    ) -> dict[float, float]:
        """Compute extension price levels."""
        diff = swing_high - swing_low
        result: dict[float, float] = {}

        for level in self.config.extension_levels:
            if is_uptrend:
                price = swing_low + diff * level
            else:
                price = swing_high - diff * level
            result[level] = round(price, 4)

        return result

    def _find_swing_high(self, high: pd.Series) -> tuple[int, float]:
        """Find the most significant swing high.

        Uses the global maximum within the configured window.
        """
        n = len(high)
        if n == 0:
            return 0, 0.0

        window = min(self.config.swing_window * 5, n)
        recent = high.values[-window:]
        idx = int(np.argmax(recent))
        return n - window + idx, float(recent[idx])

    def _find_swing_low(self, low: pd.Series) -> tuple[int, float]:
        """Find the most significant swing low."""
        n = len(low)
        if n == 0:
            return 0, 0.0

        window = min(self.config.swing_window * 5, n)
        recent = low.values[-window:]
        idx = int(np.argmin(recent))
        return n - window + idx, float(recent[idx])

    def find_nearest_level(
        self,
        fib: FibonacciLevels,
        price: float,
    ) -> Optional[tuple[str, float, float]]:
        """Find nearest Fibonacci level to current price.

        Returns:
            (level_type, fib_ratio, fib_price) or None.
        """
        candidates: list[tuple[str, float, float]] = []

        for ratio, fib_price in fib.retracements.items():
            candidates.append(("retracement", ratio, fib_price))
        for ratio, fib_price in fib.extensions.items():
            candidates.append(("extension", ratio, fib_price))

        if not candidates:
            return None

        nearest = min(candidates, key=lambda x: abs(x[2] - price))
        return nearest
