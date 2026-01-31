"""Simulated Market Data Feed.

Provides price updates for paper trading sessions via simulated
random walk, historical replay, or external data sources.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.paper_trading.config import DataFeedConfig, DataFeedType

logger = logging.getLogger(__name__)


class DataFeed:
    """Market data feed for paper trading.

    Generates price updates via simulation or historical replay.
    """

    def __init__(self, config: Optional[DataFeedConfig] = None) -> None:
        self.config = config or DataFeedConfig()
        self._rng = np.random.default_rng(self.config.seed)
        self._prices: dict[str, float] = {}
        self._history: dict[str, list[tuple[datetime, float]]] = {}
        self._replay_data: Optional[pd.DataFrame] = None
        self._replay_idx = 0
        self._bar_count = 0

    def initialize(self, symbols: list[str], initial_prices: Optional[dict[str, float]] = None) -> None:
        """Initialize feed with symbols and optional starting prices.

        Args:
            symbols: List of symbols to track.
            initial_prices: Optional starting prices. Defaults to 100.0.
        """
        for symbol in symbols:
            price = (initial_prices or {}).get(symbol, 100.0)
            self._prices[symbol] = price
            self._history[symbol] = [(datetime.now(timezone.utc), price)]

    def load_replay_data(self, data: pd.DataFrame) -> None:
        """Load historical data for replay mode.

        Args:
            data: DataFrame with DatetimeIndex, columns are symbols with prices.
        """
        self._replay_data = data
        self._replay_idx = 1  # Start from second row; first row used for init

        # Initialize prices from first row
        for symbol in data.columns:
            if pd.notna(data.iloc[0][symbol]):
                self._prices[symbol] = float(data.iloc[0][symbol])
                self._history[symbol] = [
                    (data.index[0].to_pydatetime(), self._prices[symbol])
                ]

    def get_prices(self) -> dict[str, float]:
        """Get current prices for all symbols."""
        return self._prices.copy()

    def get_price(self, symbol: str) -> float:
        """Get current price for a single symbol."""
        return self._prices.get(symbol, 0.0)

    def get_price_history(self, symbol: str) -> list[tuple[datetime, float]]:
        """Get price history for a symbol."""
        return self._history.get(symbol, [])

    def next_tick(self) -> dict[str, float]:
        """Generate next price update.

        Returns:
            Updated prices for all symbols.
        """
        self._bar_count += 1

        if self.config.feed_type == DataFeedType.HISTORICAL_REPLAY:
            return self._replay_next()
        elif self.config.feed_type == DataFeedType.RANDOM_WALK:
            return self._random_walk_next()
        else:  # SIMULATED
            return self._simulated_next()

    def _simulated_next(self) -> dict[str, float]:
        """Generate simulated price movement with drift and volatility."""
        now = datetime.now(timezone.utc)

        for symbol in list(self._prices.keys()):
            ret = self._rng.normal(self.config.drift, self.config.volatility)
            new_price = self._prices[symbol] * (1 + ret)
            new_price = max(new_price, 0.01)  # Price floor
            self._prices[symbol] = round(new_price, 2)
            self._history.setdefault(symbol, []).append((now, new_price))

        return self._prices.copy()

    def _random_walk_next(self) -> dict[str, float]:
        """Generate pure random walk (zero drift)."""
        now = datetime.now(timezone.utc)

        for symbol in list(self._prices.keys()):
            ret = self._rng.normal(0, self.config.volatility)
            new_price = self._prices[symbol] * (1 + ret)
            new_price = max(new_price, 0.01)
            self._prices[symbol] = round(new_price, 2)
            self._history.setdefault(symbol, []).append((now, new_price))

        return self._prices.copy()

    def _replay_next(self) -> dict[str, float]:
        """Replay next bar from historical data."""
        if self._replay_data is None or self._replay_idx >= len(self._replay_data):
            return self._prices.copy()

        row = self._replay_data.iloc[self._replay_idx]
        ts = self._replay_data.index[self._replay_idx]

        if hasattr(ts, 'to_pydatetime'):
            ts = ts.to_pydatetime()

        for symbol in self._replay_data.columns:
            val = row.get(symbol)
            if pd.notna(val) and float(val) > 0:
                self._prices[symbol] = round(float(val), 2)
                self._history.setdefault(symbol, []).append((ts, float(val)))

        self._replay_idx += 1
        return self._prices.copy()

    @property
    def bar_count(self) -> int:
        """Number of bars processed."""
        return self._bar_count

    @property
    def has_more_data(self) -> bool:
        """Check if replay has more data."""
        if self.config.feed_type != DataFeedType.HISTORICAL_REPLAY:
            return True  # Simulated feeds are infinite
        if self._replay_data is None:
            return False
        return self._replay_idx < len(self._replay_data)

    def reset(self) -> None:
        """Reset feed to initial state."""
        self._prices.clear()
        self._history.clear()
        self._replay_idx = 0
        self._bar_count = 0
