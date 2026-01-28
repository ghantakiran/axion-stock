"""Polygon.io data provider.

REST API for historical bars and real-time quotes.
WebSocket streaming is handled separately in src/services/streaming/.
"""

import logging
from typing import Optional

import aiohttp
import pandas as pd

from src.settings import get_settings

logger = logging.getLogger(__name__)


class PolygonProvider:
    """Polygon.io REST API provider."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def _enabled(self) -> bool:
        return bool(self.settings.polygon_api_key)

    async def get_quote(self, ticker: str) -> Optional[dict]:
        """Get last trade for a ticker."""
        if not self._enabled:
            return None

        url = f"{self.settings.polygon_rest_url}/v2/last/trade/{ticker}"
        params = {"apiKey": self.settings.polygon_api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.debug("Polygon quote %s returned status %d", ticker, resp.status)
                        return None
                    data = await resp.json()
                    result = data.get("results", {})
                    return {
                        "ticker": ticker,
                        "price": result.get("p"),
                        "size": result.get("s"),
                        "timestamp": result.get("t"),
                        "exchange": result.get("x"),
                        "source": "polygon",
                    }
        except Exception as e:
            logger.warning("Polygon quote failed for %s: %s", ticker, e)
            return None

    async def fetch_historical(
        self,
        ticker: str,
        start: str,
        end: str,
        timespan: str = "day",
        multiplier: int = 1,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars.

        Args:
            ticker: Stock ticker symbol
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            timespan: bar size - minute, hour, day, week, month
            multiplier: multiplier for timespan (e.g. 5 for 5-minute bars)

        Returns:
            DataFrame with columns: open, high, low, close, volume, vwap
            Index: DatetimeIndex
        """
        if not self._enabled:
            return pd.DataFrame()

        url = (
            f"{self.settings.polygon_rest_url}/v2/aggs/ticker/{ticker}"
            f"/range/{multiplier}/{timespan}/{start}/{end}"
        )
        params = {
            "apiKey": self.settings.polygon_api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning("Polygon historical %s returned status %d", ticker, resp.status)
                        return pd.DataFrame()

                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        return pd.DataFrame()

                    df = pd.DataFrame(results)
                    df["time"] = pd.to_datetime(df["t"], unit="ms")
                    df = df.rename(columns={
                        "o": "open",
                        "h": "high",
                        "l": "low",
                        "c": "close",
                        "v": "volume",
                        "vw": "vwap",
                    })
                    cols = ["time", "open", "high", "low", "close", "volume"]
                    if "vwap" in df.columns:
                        cols.append("vwap")
                    return df[cols].set_index("time")

        except Exception as e:
            logger.warning("Polygon historical failed for %s: %s", ticker, e)
            return pd.DataFrame()

    async def get_ticker_details(self, ticker: str) -> Optional[dict]:
        """Get ticker metadata (name, sector, exchange, etc.)."""
        if not self._enabled:
            return None

        url = f"{self.settings.polygon_rest_url}/v3/reference/tickers/{ticker}"
        params = {"apiKey": self.settings.polygon_api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    result = data.get("results", {})
                    return {
                        "ticker": result.get("ticker"),
                        "name": result.get("name"),
                        "market_cap": result.get("market_cap"),
                        "exchange": result.get("primary_exchange"),
                        "sic_code": result.get("sic_code"),
                        "sic_description": result.get("sic_description"),
                    }
        except Exception as e:
            logger.warning("Polygon ticker details failed for %s: %s", ticker, e)
            return None
