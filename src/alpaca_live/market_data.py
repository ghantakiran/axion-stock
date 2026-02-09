"""Alpaca Market Data Provider (PRD-139).

Historical and real-time market data access through Alpaca's Data API.
Provides OHLCV bars, snapshots, quotes, and trade data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from typing import Any, Optional
import logging

import pandas as pd
import numpy as np

from src.alpaca_live.client import (
    AlpacaClient,
    AlpacaConfig,
    AlpacaBar,
    AlpacaQuote,
    AlpacaSnapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class BarRequest:
    """Request for historical bars."""
    symbol: str
    timeframe: str = "1Day"  # 1Min, 5Min, 15Min, 1Hour, 1Day, 1Week, 1Month
    start: Optional[str] = None
    end: Optional[str] = None
    limit: int = 100


@dataclass
class MarketDataCache:
    """In-memory cache for market data."""
    bars: dict[str, list[AlpacaBar]] = field(default_factory=dict)  # symbol -> bars
    snapshots: dict[str, AlpacaSnapshot] = field(default_factory=dict)
    quotes: dict[str, AlpacaQuote] = field(default_factory=dict)
    last_refresh: dict[str, datetime] = field(default_factory=dict)
    cache_ttl: float = 60.0  # seconds

    def is_stale(self, key: str) -> bool:
        """Check if cached data is stale."""
        last = self.last_refresh.get(key)
        if not last:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed > self.cache_ttl

    def set_bars(self, symbol: str, bars: list[AlpacaBar]) -> None:
        self.bars[symbol] = bars
        self.last_refresh[f"bars:{symbol}"] = datetime.now(timezone.utc)

    def set_snapshot(self, symbol: str, snapshot: AlpacaSnapshot) -> None:
        self.snapshots[symbol] = snapshot
        self.last_refresh[f"snap:{symbol}"] = datetime.now(timezone.utc)

    def set_quote(self, symbol: str, quote: AlpacaQuote) -> None:
        self.quotes[symbol] = quote
        self.last_refresh[f"quote:{symbol}"] = datetime.now(timezone.utc)


class MarketDataProvider:
    """Provides historical and real-time market data from Alpaca.

    Features:
    - Historical OHLCV bars at multiple timeframes
    - Real-time snapshots and quotes
    - OHLCV DataFrame generation for EMA signal engine
    - In-memory caching with TTL

    Example:
        provider = MarketDataProvider(client)
        df = await provider.get_ohlcv_df("AAPL", days=252)
        snapshot = await provider.get_snapshot("AAPL")
    """

    def __init__(self, client: AlpacaClient, cache_ttl: float = 60.0):
        self._client = client
        self._cache = MarketDataCache(cache_ttl=cache_ttl)

    @property
    def cache(self) -> MarketDataCache:
        return self._cache

    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
        use_cache: bool = True,
    ) -> list[AlpacaBar]:
        """Get historical bars."""
        cache_key = f"bars:{symbol}"
        if use_cache and not self._cache.is_stale(cache_key):
            cached = self._cache.bars.get(symbol)
            if cached:
                return cached

        bars = await self._client.get_bars(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        if use_cache:
            self._cache.set_bars(symbol, bars)

        return bars

    async def get_ohlcv_df(
        self,
        symbol: str,
        timeframe: str = "1Day",
        days: int = 252,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Get OHLCV data as a pandas DataFrame.

        Returns DataFrame with columns: open, high, low, close, volume
        Suitable for feeding directly into EMACloudCalculator.
        """
        start_date = (date.today() - timedelta(days=days)).isoformat()
        bars = await self.get_bars(
            symbol=symbol,
            timeframe=timeframe,
            start=start_date,
            limit=limit,
            use_cache=False,
        )

        if not bars:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        data = {
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }

        if bars[0].timestamp:
            try:
                index = pd.to_datetime([b.timestamp for b in bars])
                return pd.DataFrame(data, index=index)
            except Exception:
                pass

        return pd.DataFrame(data)

    async def get_multi_ohlcv(
        self,
        symbols: list[str],
        timeframe: str = "1Day",
        days: int = 252,
    ) -> dict[str, pd.DataFrame]:
        """Get OHLCV DataFrames for multiple symbols.

        Returns dict of symbol -> DataFrame.
        """
        result = {}
        for symbol in symbols:
            try:
                df = await self.get_ohlcv_df(
                    symbol=symbol,
                    timeframe=timeframe,
                    days=days,
                )
                if not df.empty:
                    result[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to get OHLCV for {symbol}: {e}")

        return result

    async def get_snapshot(
        self, symbol: str, use_cache: bool = True
    ) -> AlpacaSnapshot:
        """Get latest snapshot for a symbol."""
        cache_key = f"snap:{symbol}"
        if use_cache and not self._cache.is_stale(cache_key):
            cached = self._cache.snapshots.get(symbol)
            if cached:
                return cached

        snapshot = await self._client.get_snapshot(symbol)
        if use_cache:
            self._cache.set_snapshot(symbol, snapshot)

        return snapshot

    async def get_latest_quote(
        self, symbol: str, use_cache: bool = True
    ) -> AlpacaQuote:
        """Get latest quote for a symbol."""
        cache_key = f"quote:{symbol}"
        if use_cache and not self._cache.is_stale(cache_key):
            cached = self._cache.quotes.get(symbol)
            if cached:
                return cached

        quote = await self._client.get_latest_quote(symbol)
        if use_cache:
            self._cache.set_quote(symbol, quote)

        return quote

    async def get_multi_snapshots(
        self, symbols: list[str]
    ) -> dict[str, AlpacaSnapshot]:
        """Get snapshots for multiple symbols."""
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = await self.get_snapshot(symbol)
            except Exception as e:
                logger.warning(f"Snapshot failed for {symbol}: {e}")
        return result

    async def get_latest_prices(
        self, symbols: list[str]
    ) -> dict[str, float]:
        """Get latest prices for multiple symbols.

        Returns dict of symbol -> price.
        """
        prices = {}
        snapshots = await self.get_multi_snapshots(symbols)
        for symbol, snap in snapshots.items():
            prices[symbol] = snap.latest_trade_price
        return prices

    async def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            clock = await self._client.get_clock()
            return clock.get("is_open", False)
        except Exception:
            return False

    async def get_market_hours(self) -> dict:
        """Get current market hours."""
        return await self._client.get_clock()
