"""Bid-Ask Spread Analysis.

Computes quoted, effective, and realized spreads with
decomposition into adverse selection and inventory components.
"""

import logging
import math
from typing import Optional

import numpy as np

from src.microstructure.config import SpreadConfig, DEFAULT_SPREAD_CONFIG
from src.microstructure.models import SpreadMetrics, Trade

logger = logging.getLogger(__name__)


class SpreadAnalyzer:
    """Analyzes bid-ask spreads and their components."""

    def __init__(self, config: Optional[SpreadConfig] = None) -> None:
        self.config = config or DEFAULT_SPREAD_CONFIG

    def analyze(
        self,
        trades: list[Trade],
        bids: np.ndarray,
        asks: np.ndarray,
        symbol: str = "",
    ) -> SpreadMetrics:
        """Full spread analysis from trade and quote data.

        Args:
            trades: List of trades with price, size, timestamp.
            bids: Array of best bid prices aligned with trades.
            asks: Array of best ask prices aligned with trades.
            symbol: Ticker symbol.

        Returns:
            SpreadMetrics with all spread components.
        """
        n = len(trades)
        if n < self.config.min_trades:
            return self._empty_metrics(symbol)

        bids = np.asarray(bids, dtype=float)
        asks = np.asarray(asks, dtype=float)
        prices = np.array([t.price for t in trades], dtype=float)
        sizes = np.array([t.size for t in trades], dtype=float)

        midpoints = (bids + asks) / 2
        avg_mid = np.mean(midpoints)

        # Quoted spread (volume-weighted)
        quoted_spreads = asks - bids
        total_vol = np.sum(sizes)
        if total_vol > 0:
            quoted_spread = np.sum(quoted_spreads * sizes) / total_vol
        else:
            quoted_spread = np.mean(quoted_spreads)

        # Effective spread: 2 * |price - midpoint|
        directions = self._classify_trades(trades, midpoints)
        eff_spreads = 2.0 * np.abs(prices - midpoints)
        if total_vol > 0:
            effective_spread = np.sum(eff_spreads * sizes) / total_vol
        else:
            effective_spread = np.mean(eff_spreads)

        # Realized spread: 2 * direction * (price - future_midpoint)
        delay = self.config.realized_spread_delay
        if n > delay:
            future_mids = np.roll(midpoints, -delay)
            valid = n - delay
            realized_components = 2.0 * directions[:valid] * (prices[:valid] - future_mids[:valid])
            valid_sizes = sizes[:valid]
            if np.sum(valid_sizes) > 0:
                realized_spread = np.sum(realized_components * valid_sizes) / np.sum(valid_sizes)
            else:
                realized_spread = np.mean(realized_components)
        else:
            realized_spread = effective_spread * 0.5

        # Roll's implied spread
        roll_spread = self.roll_estimator(prices)

        # Adverse selection = effective - realized
        adverse_selection = effective_spread - realized_spread

        # Convert to basis points
        if avg_mid > 0:
            quoted_bps = quoted_spread / avg_mid * 10000
            effective_bps = effective_spread / avg_mid * 10000
            realized_bps = realized_spread / avg_mid * 10000
            adverse_bps = adverse_selection / avg_mid * 10000
        else:
            quoted_bps = effective_bps = realized_bps = adverse_bps = 0.0

        return SpreadMetrics(
            symbol=symbol,
            quoted_spread=round(quoted_spread, 6),
            quoted_spread_bps=round(quoted_bps, 2),
            effective_spread=round(effective_spread, 6),
            effective_spread_bps=round(effective_bps, 2),
            realized_spread=round(realized_spread, 6),
            realized_spread_bps=round(realized_bps, 2),
            roll_spread=round(roll_spread, 6),
            adverse_selection=round(adverse_selection, 6),
            adverse_selection_bps=round(adverse_bps, 2),
            midpoint=round(avg_mid, 4),
        )

    def _classify_trades(
        self, trades: list[Trade], midpoints: np.ndarray
    ) -> np.ndarray:
        """Lee-Ready trade classification.

        Trades above midpoint are buys (+1), below are sells (-1).
        At midpoint, use tick test (compare to previous trade).
        """
        prices = np.array([t.price for t in trades], dtype=float)
        directions = np.zeros(len(trades))

        for i in range(len(trades)):
            if trades[i].side != 0:
                directions[i] = trades[i].side
            elif prices[i] > midpoints[i]:
                directions[i] = 1.0
            elif prices[i] < midpoints[i]:
                directions[i] = -1.0
            else:
                # Tick test: compare to previous price
                if i > 0:
                    if prices[i] > prices[i - 1]:
                        directions[i] = 1.0
                    elif prices[i] < prices[i - 1]:
                        directions[i] = -1.0
                    else:
                        directions[i] = directions[i - 1] if i > 0 else 1.0
                else:
                    directions[i] = 1.0

        return directions

    def roll_estimator(self, prices: np.ndarray) -> float:
        """Roll's implied spread from serial covariance.

        Spread = 2 * sqrt(-cov) if cov < 0, else 0.
        """
        if len(prices) < 3:
            return 0.0

        returns = np.diff(prices)
        if len(returns) < 2:
            return 0.0

        # Use rolling window if configured
        window = min(self.config.roll_window, len(returns) - 1)
        r1 = returns[-window:]
        r2 = returns[-window - 1:-1] if len(returns) > window else returns[:-1]

        # Trim to same length
        n = min(len(r1), len(r2))
        r1 = r1[:n]
        r2 = r2[:n]

        cov = np.mean(r1 * r2) - np.mean(r1) * np.mean(r2)

        if cov < 0:
            return 2.0 * math.sqrt(-cov)
        return 0.0

    def _empty_metrics(self, symbol: str) -> SpreadMetrics:
        return SpreadMetrics(
            symbol=symbol,
            quoted_spread=0.0, quoted_spread_bps=0.0,
            effective_spread=0.0, effective_spread_bps=0.0,
            realized_spread=0.0, realized_spread_bps=0.0,
            roll_spread=0.0,
            adverse_selection=0.0, adverse_selection_bps=0.0,
            midpoint=0.0,
        )
