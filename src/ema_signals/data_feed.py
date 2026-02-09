"""Market data acquisition for EMA cloud signal engine.

Fetches OHLCV bars from multiple data sources with fallback chain:
1. Polygon (real-time, requires API key)
2. Alpaca (streaming, requires API key)
3. Yahoo Finance (historical fallback, free)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Timeframe to yfinance interval mapping
TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "10m": "15m",  # yfinance doesn't have 10m; use 15m as closest
    "1h": "1h",
    "1d": "1d",
}

# Lookback periods by timeframe (trading days/hours)
LOOKBACK_MAP = {
    "1m": "5d",
    "5m": "10d",
    "10m": "15d",
    "1h": "60d",
    "1d": "1y",
}


class DataFeed:
    """Fetch OHLCV bars from Polygon, Alpaca, or Yahoo Finance.

    Supports:
    - Historical bars for initial cloud computation
    - Real-time/streaming bars for live signal detection
    - WebSocket subscription for 1-min bars (placeholder)
    """

    def __init__(
        self,
        polygon_api_key: Optional[str] = None,
        alpaca_api_key: Optional[str] = None,
        alpaca_secret_key: Optional[str] = None,
        preferred_source: str = "yahoo",
    ):
        self.polygon_api_key = polygon_api_key
        self.alpaca_api_key = alpaca_api_key
        self.alpaca_secret_key = alpaca_secret_key
        self.preferred_source = preferred_source
        self._subscribers: dict[str, list[Callable]] = {}

    def get_bars(
        self,
        ticker: str,
        timeframe: str,
        lookback: int = 200,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars with fallback chain.

        Args:
            ticker: Ticker symbol (e.g., "AAPL").
            timeframe: Timeframe string ("1m", "5m", "10m", "1h", "1d").
            lookback: Number of bars to fetch (approximate).

        Returns:
            DataFrame with columns: open, high, low, close, volume.
            Index is DatetimeIndex. Empty DataFrame if all sources fail.
        """
        sources = self._get_source_chain()

        for source_name, fetch_fn in sources:
            try:
                df = fetch_fn(ticker, timeframe, lookback)
                if df is not None and not df.empty and len(df) >= 10:
                    return self._normalize(df)
            except Exception as e:
                logger.debug("Source %s failed for %s/%s: %s", source_name, ticker, timeframe, e)
                continue

        logger.warning("All data sources failed for %s/%s", ticker, timeframe)
        return pd.DataFrame()

    def _get_source_chain(self) -> list[tuple[str, Callable]]:
        """Build ordered data source fallback chain."""
        chain: list[tuple[str, Callable]] = []

        if self.preferred_source == "polygon" and self.polygon_api_key:
            chain.append(("polygon", self._fetch_polygon))
        if self.preferred_source == "alpaca" and self.alpaca_api_key:
            chain.append(("alpaca", self._fetch_alpaca))

        # Always include yahoo as final fallback
        chain.append(("yahoo", self._fetch_yahoo))
        return chain

    def _fetch_yahoo(
        self, ticker: str, timeframe: str, lookback: int
    ) -> Optional[pd.DataFrame]:
        """Fetch bars from Yahoo Finance via yfinance."""
        import yfinance as yf

        interval = TIMEFRAME_MAP.get(timeframe, "1d")
        period = LOOKBACK_MAP.get(timeframe, "1y")

        data = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )

        if data is None or data.empty:
            return None

        # Handle MultiIndex columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        return data

    def _fetch_polygon(
        self, ticker: str, timeframe: str, lookback: int
    ) -> Optional[pd.DataFrame]:
        """Fetch bars from Polygon.io REST API."""
        try:
            from polygon import RESTClient

            client = RESTClient(api_key=self.polygon_api_key)

            multiplier, span = self._parse_polygon_timeframe(timeframe)
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=lookback if timeframe == "1d" else lookback // 6)

            aggs = client.get_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=span,
                from_=start.strftime("%Y-%m-%d"),
                to=end.strftime("%Y-%m-%d"),
                limit=lookback,
            )

            if not aggs:
                return None

            rows = []
            for a in aggs:
                rows.append({
                    "open": a.open,
                    "high": a.high,
                    "low": a.low,
                    "close": a.close,
                    "volume": a.volume,
                    "timestamp": pd.Timestamp(a.timestamp, unit="ms"),
                })

            df = pd.DataFrame(rows)
            df.set_index("timestamp", inplace=True)
            return df

        except ImportError:
            logger.debug("polygon-api-client not installed")
            return None

    def _fetch_alpaca(
        self, ticker: str, timeframe: str, lookback: int
    ) -> Optional[pd.DataFrame]:
        """Fetch bars from Alpaca Markets API."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            client = StockHistoricalDataClient(
                api_key=self.alpaca_api_key,
                secret_key=self.alpaca_secret_key,
            )

            tf_map = {
                "1m": TimeFrame.Minute,
                "5m": TimeFrame(5, "Min"),
                "10m": TimeFrame(10, "Min"),
                "1h": TimeFrame.Hour,
                "1d": TimeFrame.Day,
            }

            end = datetime.now(timezone.utc)
            start = end - timedelta(days=lookback if timeframe == "1d" else lookback // 6)

            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=tf_map.get(timeframe, TimeFrame.Day),
                start=start,
                end=end,
                limit=lookback,
            )

            bars = client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                return None

            # Reset multi-index if present
            if isinstance(df.index, pd.MultiIndex):
                df = df.droplevel("symbol")

            return df

        except ImportError:
            logger.debug("alpaca-py not installed")
            return None

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to lowercase standard."""
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            # Try to find matching columns case-insensitively
            col_map = {}
            for col in df.columns:
                for req in required:
                    if col.lower().startswith(req):
                        col_map[col] = req
                        break
            if col_map:
                df = df.rename(columns=col_map)
        return df

    @staticmethod
    def _parse_polygon_timeframe(timeframe: str) -> tuple[int, str]:
        """Convert timeframe string to Polygon multiplier and span."""
        mapping = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "10m": (10, "minute"),
            "1h": (1, "hour"),
            "1d": (1, "day"),
        }
        return mapping.get(timeframe, (1, "day"))

    def subscribe_realtime(
        self, tickers: list[str], callback: Callable
    ) -> None:
        """Register a callback for real-time bar updates.

        This is a placeholder for WebSocket streaming integration.
        In production, connects to Polygon/Alpaca WebSocket feed.
        """
        for ticker in tickers:
            if ticker not in self._subscribers:
                self._subscribers[ticker] = []
            self._subscribers[ticker].append(callback)
        logger.info("Subscribed to real-time updates for %d tickers", len(tickers))

    def unsubscribe(self, tickers: list[str]) -> None:
        """Remove real-time subscriptions for given tickers."""
        for ticker in tickers:
            self._subscribers.pop(ticker, None)
        logger.info("Unsubscribed from %d tickers", len(tickers))
