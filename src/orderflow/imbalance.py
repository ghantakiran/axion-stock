"""Order Book Imbalance Analyzer.

Computes bid/ask volume imbalance ratios, classifies imbalance type,
and generates directional signals from order book data.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from src.orderflow.config import (
    ImbalanceConfig,
    ImbalanceType,
    FlowSignal,
    DEFAULT_IMBALANCE_CONFIG,
)
from src.orderflow.models import OrderBookSnapshot

logger = logging.getLogger(__name__)


class ImbalanceAnalyzer:
    """Analyzes order book imbalance."""

    def __init__(self, config: Optional[ImbalanceConfig] = None) -> None:
        self.config = config or DEFAULT_IMBALANCE_CONFIG
        self._history: list[OrderBookSnapshot] = []

    def compute_imbalance(
        self,
        bid_volume: float,
        ask_volume: float,
        symbol: str = "",
    ) -> OrderBookSnapshot:
        """Compute order book imbalance from bid/ask volumes.

        Args:
            bid_volume: Total bid-side volume.
            ask_volume: Total ask-side volume.
            symbol: Asset symbol.

        Returns:
            OrderBookSnapshot with imbalance metrics.
        """
        if ask_volume > 0:
            ratio = bid_volume / ask_volume
        elif bid_volume > 0:
            ratio = float("inf")
        else:
            ratio = 1.0

        imbalance_type = self._classify(ratio)
        signal = self._signal(ratio)

        snapshot = OrderBookSnapshot(
            symbol=symbol,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            imbalance_ratio=round(ratio, 3) if ratio != float("inf") else 999.0,
            imbalance_type=imbalance_type,
            signal=signal,
            timestamp=datetime.now(),
        )

        self._history.append(snapshot)
        return snapshot

    def rolling_imbalance(
        self,
        bid_volumes: pd.Series,
        ask_volumes: pd.Series,
        symbol: str = "",
    ) -> list[OrderBookSnapshot]:
        """Compute rolling imbalance over a series.

        Args:
            bid_volumes: Bid volume series.
            ask_volumes: Ask volume series.
            symbol: Asset symbol.

        Returns:
            List of OrderBookSnapshot.
        """
        n = min(len(bid_volumes), len(ask_volumes))
        window = self.config.smoothing_window
        results: list[OrderBookSnapshot] = []

        bids = bid_volumes.values[:n].astype(float)
        asks = ask_volumes.values[:n].astype(float)

        for i in range(n):
            start = max(0, i - window + 1)
            avg_bid = float(np.mean(bids[start:i + 1]))
            avg_ask = float(np.mean(asks[start:i + 1]))
            snapshot = self.compute_imbalance(avg_bid, avg_ask, symbol=symbol)
            results.append(snapshot)

        return results

    def _classify(self, ratio: float) -> ImbalanceType:
        """Classify imbalance ratio."""
        if ratio >= self.config.bid_heavy_threshold:
            return ImbalanceType.BID_HEAVY
        elif ratio <= self.config.ask_heavy_threshold:
            return ImbalanceType.ASK_HEAVY
        else:
            return ImbalanceType.BALANCED

    def _signal(self, ratio: float) -> FlowSignal:
        """Generate signal from imbalance ratio."""
        if ratio >= self.config.strong_signal_threshold:
            return FlowSignal.STRONG_BUY
        elif ratio >= self.config.signal_threshold:
            return FlowSignal.BUY
        elif ratio <= 1.0 / self.config.strong_signal_threshold:
            return FlowSignal.STRONG_SELL
        elif ratio <= 1.0 / self.config.signal_threshold:
            return FlowSignal.SELL
        else:
            return FlowSignal.NEUTRAL

    def get_history(self) -> list[OrderBookSnapshot]:
        return list(self._history)

    def reset(self) -> None:
        self._history.clear()
