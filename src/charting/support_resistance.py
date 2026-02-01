"""Support & Resistance Detection.

Identifies significant price levels from historical pivot points,
counts touches, and scores level strength.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.charting.config import (
    SRConfig,
    SRType,
    DEFAULT_SR_CONFIG,
)
from src.charting.models import SRLevel

logger = logging.getLogger(__name__)


class SRDetector:
    """Detects support and resistance levels."""

    def __init__(self, config: Optional[SRConfig] = None) -> None:
        self.config = config or DEFAULT_SR_CONFIG

    def find_levels(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[SRLevel]:
        """Find both support and resistance levels.

        Args:
            high: High prices.
            low: Low prices.
            close: Close prices.
            symbol: Asset symbol.

        Returns:
            Combined list sorted by strength (descending).
        """
        support = self.find_support(low, close, symbol=symbol)
        resistance = self.find_resistance(high, close, symbol=symbol)
        combined = support + resistance
        combined.sort(key=lambda lv: lv.strength, reverse=True)
        return combined[:self.config.max_levels]

    def find_support(
        self,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[SRLevel]:
        """Find support levels from local minima.

        Args:
            low: Low prices.
            close: Close prices.
            symbol: Asset symbol.

        Returns:
            List of SRLevel (support).
        """
        n = len(low)
        lookback = min(self.config.lookback, n)
        if lookback < self.config.pivot_window * 2 + 1:
            return []

        lows = low.values[-lookback:]
        closes = close.values[-lookback:]
        offset = n - lookback

        # Find pivot lows
        pivots = self._find_pivot_lows(lows, self.config.pivot_window)
        if not pivots:
            return []

        # Cluster nearby pivots into levels
        pivot_prices = [float(lows[p]) for p in pivots]
        levels = self._cluster_levels(pivot_prices, pivots, self.config.zone_tolerance)

        results: list[SRLevel] = []
        current_price = float(closes[-1])

        for price, touches, last_idx in levels:
            if touches < self.config.min_touches:
                continue
            # Only levels below current price are support
            if price > current_price:
                continue

            # Strength: touches weighted by recency
            recency = 1.0 - (lookback - last_idx) / lookback
            strength = round(min(1.0, (touches / 5.0) * 0.6 + recency * 0.4), 3)

            results.append(SRLevel(
                level_type=SRType.SUPPORT,
                price=round(price, 4),
                touches=touches,
                strength=strength,
                last_tested_idx=offset + last_idx,
                symbol=symbol,
            ))

        results.sort(key=lambda lv: lv.strength, reverse=True)
        return results[:self.config.max_levels // 2]

    def find_resistance(
        self,
        high: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[SRLevel]:
        """Find resistance levels from local maxima.

        Args:
            high: High prices.
            close: Close prices.
            symbol: Asset symbol.

        Returns:
            List of SRLevel (resistance).
        """
        n = len(high)
        lookback = min(self.config.lookback, n)
        if lookback < self.config.pivot_window * 2 + 1:
            return []

        highs = high.values[-lookback:]
        closes = close.values[-lookback:]
        offset = n - lookback

        pivots = self._find_pivot_highs(highs, self.config.pivot_window)
        if not pivots:
            return []

        pivot_prices = [float(highs[p]) for p in pivots]
        levels = self._cluster_levels(pivot_prices, pivots, self.config.zone_tolerance)

        results: list[SRLevel] = []
        current_price = float(closes[-1])

        for price, touches, last_idx in levels:
            if touches < self.config.min_touches:
                continue
            if price < current_price:
                continue

            recency = 1.0 - (lookback - last_idx) / lookback
            strength = round(min(1.0, (touches / 5.0) * 0.6 + recency * 0.4), 3)

            results.append(SRLevel(
                level_type=SRType.RESISTANCE,
                price=round(price, 4),
                touches=touches,
                strength=strength,
                last_tested_idx=offset + last_idx,
                symbol=symbol,
            ))

        results.sort(key=lambda lv: lv.strength, reverse=True)
        return results[:self.config.max_levels // 2]

    def test_level(
        self,
        level: SRLevel,
        current_price: float,
    ) -> dict[str, float]:
        """Test distance of current price to a level.

        Returns:
            Dict with distance, distance_pct, and proximity score.
        """
        distance = current_price - level.price
        distance_pct = distance / level.price if level.price > 0 else 0.0
        proximity = max(0.0, 1.0 - abs(distance_pct) / 0.05)

        return {
            "distance": round(distance, 4),
            "distance_pct": round(distance_pct * 100, 3),
            "proximity": round(proximity, 3),
        }

    def _find_pivot_highs(self, data: np.ndarray, window: int) -> list[int]:
        """Find local maxima with given window."""
        pivots = []
        for i in range(window, len(data) - window):
            if all(data[i] >= data[i - j] for j in range(1, window + 1)) and \
               all(data[i] >= data[i + j] for j in range(1, window + 1)):
                pivots.append(i)
        return pivots

    def _find_pivot_lows(self, data: np.ndarray, window: int) -> list[int]:
        """Find local minima with given window."""
        pivots = []
        for i in range(window, len(data) - window):
            if all(data[i] <= data[i - j] for j in range(1, window + 1)) and \
               all(data[i] <= data[i + j] for j in range(1, window + 1)):
                pivots.append(i)
        return pivots

    def _cluster_levels(
        self,
        prices: list[float],
        indices: list[int],
        tolerance: float,
    ) -> list[tuple[float, int, int]]:
        """Cluster nearby prices into levels.

        Returns:
            List of (avg_price, touch_count, last_index).
        """
        if not prices:
            return []

        sorted_pairs = sorted(zip(prices, indices), key=lambda x: x[0])
        clusters: list[list[tuple[float, int]]] = []
        current_cluster: list[tuple[float, int]] = [sorted_pairs[0]]

        for i in range(1, len(sorted_pairs)):
            price, idx = sorted_pairs[i]
            cluster_avg = np.mean([p for p, _ in current_cluster])
            if abs(price - cluster_avg) / cluster_avg <= tolerance:
                current_cluster.append((price, idx))
            else:
                clusters.append(current_cluster)
                current_cluster = [(price, idx)]
        clusters.append(current_cluster)

        results: list[tuple[float, int, int]] = []
        for cluster in clusters:
            avg_price = float(np.mean([p for p, _ in cluster]))
            touches = len(cluster)
            last_idx = max(idx for _, idx in cluster)
            results.append((avg_price, touches, last_idx))

        return results
