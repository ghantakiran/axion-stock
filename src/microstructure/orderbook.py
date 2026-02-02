"""Order Book Analysis.

Computes imbalance, depth, pressure, slope, and resilience
metrics from order book snapshots.
"""

import logging
from typing import Optional

import numpy as np

from src.microstructure.config import OrderBookConfig, DEFAULT_ORDERBOOK_CONFIG
from src.microstructure.models import BookLevel, OrderBookSnapshot

logger = logging.getLogger(__name__)


class OrderBookAnalyzer:
    """Analyzes order book state and dynamics."""

    def __init__(self, config: Optional[OrderBookConfig] = None) -> None:
        self.config = config or DEFAULT_ORDERBOOK_CONFIG
        self._history: list[OrderBookSnapshot] = []

    def analyze(
        self,
        bids: list[BookLevel],
        asks: list[BookLevel],
        symbol: str = "",
    ) -> OrderBookSnapshot:
        """Analyze order book state.

        Args:
            bids: Bid levels sorted by price descending.
            asks: Ask levels sorted by price ascending.
            symbol: Ticker symbol.

        Returns:
            OrderBookSnapshot with computed metrics.
        """
        levels = self.config.imbalance_levels

        # Trim to configured depth
        bids = bids[: self.config.depth_levels]
        asks = asks[: self.config.depth_levels]

        # Depth
        bid_depth = sum(b.size for b in bids)
        ask_depth = sum(a.size for a in asks)

        # Imbalance at top N levels
        bid_top = sum(b.size for b in bids[:levels])
        ask_top = sum(a.size for a in asks[:levels])
        total_top = bid_top + ask_top
        imbalance = (bid_top - ask_top) / total_top if total_top > 0 else 0.0

        # Weighted midpoint (size-weighted)
        weighted_mid = self._weighted_midpoint(bids, asks)

        # Book pressure: cumulative depth differential
        pressure = self._book_pressure(bids, asks)

        # Slope: how quickly depth falls off with price
        bid_slope = self._compute_slope(bids, side="bid")
        ask_slope = self._compute_slope(asks, side="ask")

        # Resilience: compare current depth to recent history
        current_depth = bid_depth + ask_depth
        resilience = self._compute_resilience(current_depth)

        snapshot = OrderBookSnapshot(
            symbol=symbol,
            bids=bids,
            asks=asks,
            imbalance=round(imbalance, 4),
            bid_depth=round(bid_depth, 2),
            ask_depth=round(ask_depth, 2),
            weighted_midpoint=round(weighted_mid, 4),
            book_pressure=round(pressure, 4),
            bid_slope=round(bid_slope, 4),
            ask_slope=round(ask_slope, 4),
            resilience=round(resilience, 4),
        )

        self._history.append(snapshot)
        return snapshot

    def _weighted_midpoint(
        self, bids: list[BookLevel], asks: list[BookLevel]
    ) -> float:
        """Size-weighted midpoint from best bid/ask."""
        if not bids or not asks:
            return 0.0
        bid_size = bids[0].size
        ask_size = asks[0].size
        total = bid_size + ask_size
        if total == 0:
            return (bids[0].price + asks[0].price) / 2
        return (bids[0].price * ask_size + asks[0].price * bid_size) / total

    def _book_pressure(
        self, bids: list[BookLevel], asks: list[BookLevel]
    ) -> float:
        """Net book pressure: normalized cumulative depth difference.

        Positive = bid pressure (bullish), negative = ask pressure (bearish).
        """
        bid_cum = np.cumsum([b.size for b in bids]) if bids else np.array([0])
        ask_cum = np.cumsum([a.size for a in asks]) if asks else np.array([0])

        n = min(len(bid_cum), len(ask_cum))
        if n == 0:
            return 0.0

        diff = bid_cum[:n] - ask_cum[:n]
        total = bid_cum[:n] + ask_cum[:n]
        # Avoid division by zero
        valid = total > 0
        if not np.any(valid):
            return 0.0
        return float(np.mean(diff[valid] / total[valid]))

    def _compute_slope(
        self, levels: list[BookLevel], side: str
    ) -> float:
        """Compute price-depth slope via linear regression.

        Higher slope = depth drops quickly with price distance (thin book).
        """
        if len(levels) < 2:
            return 0.0

        prices = np.array([l.price for l in levels])
        sizes = np.array([l.size for l in levels])

        # Distance from best price
        if side == "bid":
            distances = prices[0] - prices  # positive for lower bids
        else:
            distances = prices - prices[0]  # positive for higher asks

        # Avoid zero-distance
        if np.max(distances) == 0:
            return 0.0

        # Normalize
        distances = distances / np.max(distances)
        sizes_norm = sizes / np.max(sizes) if np.max(sizes) > 0 else sizes

        # Simple linear regression slope
        n = len(distances)
        if n < 2:
            return 0.0
        x_mean = np.mean(distances)
        y_mean = np.mean(sizes_norm)
        num = np.sum((distances - x_mean) * (sizes_norm - y_mean))
        den = np.sum((distances - x_mean) ** 2)
        if den == 0:
            return 0.0

        return float(-num / den)  # negate: steeper decline = higher slope

    def _compute_resilience(self, current_depth: float) -> float:
        """Measure book resilience from depth recovery.

        Compares current depth to previous snapshots.
        Resilience = average depth ratio (current vs historical).
        """
        if len(self._history) < 1:
            return 0.0

        recent = self._history[-10:]
        recoveries = []

        # Compare current to last snapshot
        if recent[-1].total_depth > 0:
            ratio = current_depth / recent[-1].total_depth
            recoveries.append(min(ratio, 2.0))

        # Also compare sequential history
        for i in range(1, len(recent)):
            prev_depth = recent[i - 1].total_depth
            curr_depth = recent[i].total_depth
            if prev_depth > 0:
                ratio = curr_depth / prev_depth
                recoveries.append(min(ratio, 2.0))

        if not recoveries:
            return 0.0
        return float(np.mean(recoveries))

    def reset_history(self) -> None:
        """Clear snapshot history."""
        self._history.clear()
