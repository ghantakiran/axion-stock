"""Tick-Level Trade Metrics.

Trade classification (Lee-Ready), VWAP/TWAP, tick-to-trade
ratio, size distribution, and Kyle's lambda estimation.
"""

import logging
from typing import Optional

import numpy as np

from src.microstructure.config import TickConfig, DEFAULT_TICK_CONFIG
from src.microstructure.models import Trade, TickMetrics

logger = logging.getLogger(__name__)


class TickAnalyzer:
    """Computes tick-level trading metrics."""

    def __init__(self, config: Optional[TickConfig] = None) -> None:
        self.config = config or DEFAULT_TICK_CONFIG

    def analyze(
        self,
        trades: list[Trade],
        midpoints: Optional[np.ndarray] = None,
        symbol: str = "",
    ) -> TickMetrics:
        """Compute tick metrics from trade list.

        Args:
            trades: List of trades with price, size, timestamp.
            midpoints: Optional midpoint prices aligned with trades.
            symbol: Ticker symbol.

        Returns:
            TickMetrics with aggregated stats.
        """
        if len(trades) < self.config.min_ticks:
            return self._empty_metrics(symbol)

        prices = np.array([t.price for t in trades], dtype=float)
        sizes = np.array([t.size for t in trades], dtype=float)
        timestamps = np.array([t.timestamp for t in trades], dtype=float)

        # Classify trades
        if midpoints is not None:
            directions = self._lee_ready(prices, midpoints)
        else:
            directions = self._tick_test(prices)

        # Apply classifications back to trades
        for i, t in enumerate(trades):
            if t.side == 0:
                t.side = int(directions[i])

        # Volume split
        buy_mask = directions > 0
        sell_mask = directions < 0
        total_volume = float(np.sum(sizes))
        buy_volume = float(np.sum(sizes[buy_mask]))
        sell_volume = float(np.sum(sizes[sell_mask]))

        # VWAP
        vwap = self._compute_vwap(prices, sizes)

        # TWAP
        twap = self._compute_twap(prices, timestamps)

        # Tick-to-trade ratio
        ttr = self._tick_to_trade_ratio(prices)

        # Kyle's lambda
        kyle_lambda = self._kyle_lambda(prices, sizes, directions)

        # Size distribution
        size_dist = self._size_distribution(sizes)

        return TickMetrics(
            symbol=symbol,
            total_trades=len(trades),
            total_volume=round(total_volume, 2),
            buy_volume=round(buy_volume, 2),
            sell_volume=round(sell_volume, 2),
            vwap=round(vwap, 4),
            twap=round(twap, 4),
            tick_to_trade_ratio=round(ttr, 4),
            kyle_lambda=round(kyle_lambda, 8),
            size_distribution=size_dist,
        )

    def _lee_ready(
        self, prices: np.ndarray, midpoints: np.ndarray
    ) -> np.ndarray:
        """Lee-Ready algorithm: quote test + tick test fallback."""
        directions = np.zeros(len(prices))

        for i in range(len(prices)):
            if prices[i] > midpoints[i]:
                directions[i] = 1.0
            elif prices[i] < midpoints[i]:
                directions[i] = -1.0
            else:
                # Tick test fallback
                if i > 0:
                    if prices[i] > prices[i - 1]:
                        directions[i] = 1.0
                    elif prices[i] < prices[i - 1]:
                        directions[i] = -1.0
                    else:
                        directions[i] = directions[i - 1]
                else:
                    directions[i] = 1.0

        return directions

    def _tick_test(self, prices: np.ndarray) -> np.ndarray:
        """Pure tick test: classify by price movement."""
        directions = np.ones(len(prices))

        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                directions[i] = 1.0
            elif prices[i] < prices[i - 1]:
                directions[i] = -1.0
            else:
                directions[i] = directions[i - 1]

        return directions

    def _compute_vwap(
        self, prices: np.ndarray, sizes: np.ndarray
    ) -> float:
        """Volume-Weighted Average Price."""
        total = np.sum(sizes)
        if total == 0:
            return float(np.mean(prices))
        return float(np.sum(prices * sizes) / total)

    def _compute_twap(
        self, prices: np.ndarray, timestamps: np.ndarray
    ) -> float:
        """Time-Weighted Average Price."""
        if len(prices) < 2:
            return float(prices[0]) if len(prices) == 1 else 0.0

        # Weight by time between trades
        dt = np.diff(timestamps)
        if np.sum(dt) == 0:
            return float(np.mean(prices))

        # Each price is weighted by time until next trade
        weights = np.append(dt, dt[-1])  # repeat last interval
        return float(np.sum(prices * weights) / np.sum(weights))

    def _tick_to_trade_ratio(self, prices: np.ndarray) -> float:
        """Ratio of price changes to total trades.

        Higher ratio = more informative trading.
        """
        if len(prices) < 2:
            return 0.0
        ticks = np.sum(np.diff(prices) != 0)
        return float(ticks / (len(prices) - 1))

    def _kyle_lambda(
        self,
        prices: np.ndarray,
        sizes: np.ndarray,
        directions: np.ndarray,
    ) -> float:
        """Estimate Kyle's lambda (price impact coefficient).

        lambda = Cov(delta_P, signed_volume) / Var(signed_volume)
        """
        if len(prices) < 3:
            return 0.0

        returns = np.diff(prices)
        signed_vol = (directions[1:] * sizes[1:])

        if len(returns) < 2 or np.var(signed_vol) == 0:
            return 0.0

        cov = np.cov(returns, signed_vol)[0, 1]
        var = np.var(signed_vol)

        return float(cov / var) if var > 0 else 0.0

    def _size_distribution(self, sizes: np.ndarray) -> dict:
        """Bucket trades by size."""
        buckets = self.config.size_buckets
        dist = {}
        prev = 0
        for bucket in buckets:
            label = f"{prev}-{bucket}"
            dist[label] = int(np.sum((sizes > prev) & (sizes <= bucket)))
            prev = bucket
        dist[f"{prev}+"] = int(np.sum(sizes > prev))
        return dist

    def _empty_metrics(self, symbol: str) -> TickMetrics:
        return TickMetrics(
            symbol=symbol,
            total_trades=0,
            total_volume=0.0,
            buy_volume=0.0,
            sell_volume=0.0,
            vwap=0.0,
            twap=0.0,
            tick_to_trade_ratio=0.0,
            kyle_lambda=0.0,
        )
