"""YFinance data provider.

Wraps the existing synchronous yfinance calls in an async interface
using ThreadPoolExecutor. This is the fallback provider when Polygon
or database are unavailable.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pandas as pd
import yfinance as yf

from src.settings import get_settings

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


class YFinanceProvider:
    """Async wrapper around yfinance API."""

    async def fetch_prices(
        self,
        tickers: list[str],
        period: str = "14mo",
    ) -> pd.DataFrame:
        """Fetch OHLCV price data for multiple tickers.

        Returns DataFrame with DatetimeIndex and ticker columns (adjusted close).
        Matches the output format of data_fetcher.download_price_data().
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._fetch_prices_sync, tickers, period)

    def _fetch_prices_sync(self, tickers: list[str], period: str) -> pd.DataFrame:
        settings = get_settings()
        all_data = pd.DataFrame()
        batch_size = settings.batch_size

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            try:
                data = yf.download(
                    batch,
                    period=period,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                if not data.empty:
                    if isinstance(data.columns, pd.MultiIndex):
                        prices = data["Close"]
                    else:
                        prices = data[["Close"]]
                        prices.columns = batch[:1]
                    all_data = pd.concat([all_data, prices], axis=1)
            except Exception as e:
                logger.warning("YFinance batch fetch failed for %s: %s", batch[:3], e)

            if i + batch_size < len(tickers):
                import time
                time.sleep(settings.batch_sleep)

        # Remove duplicate columns
        all_data = all_data.loc[:, ~all_data.columns.duplicated()]
        return all_data

    async def fetch_fundamentals(self, tickers: list[str]) -> pd.DataFrame:
        """Fetch fundamental data for multiple tickers.

        Returns DataFrame with ticker index and fundamental columns.
        Matches the output format of data_fetcher.download_fundamentals().
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._fetch_fundamentals_sync, tickers)

    def _fetch_fundamentals_sync(self, tickers: list[str]) -> pd.DataFrame:
        settings = get_settings()
        fields = [
            "trailingPE", "priceToBook", "dividendYield",
            "enterpriseToEbitda", "returnOnEquity", "debtToEquity",
            "revenueGrowth", "earningsGrowth", "marketCap", "currentPrice",
        ]
        rows = {}

        for ticker in tickers:
            try:
                info = yf.Ticker(ticker).info or {}
                row = {}
                for field in fields:
                    val = info.get(field)
                    if field == "debtToEquity" and val is not None:
                        val = val / 100.0  # Yahoo returns as percentage
                    row[field] = val
                rows[ticker] = row
            except Exception as e:
                logger.debug("YFinance fundamentals failed for %s: %s", ticker, e)
            import time
            time.sleep(settings.fundamental_sleep)

        return pd.DataFrame.from_dict(rows, orient="index")

    async def get_quote(self, ticker: str) -> Optional[dict]:
        """Get a real-time quote for a single ticker."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._get_quote_sync, ticker)

    def _get_quote_sync(self, ticker: str) -> Optional[dict]:
        try:
            info = yf.Ticker(ticker).info or {}
            return {
                "ticker": ticker,
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "change_percent": info.get("regularMarketChangePercent"),
                "volume": info.get("regularMarketVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "sector": info.get("sector"),
                "name": info.get("shortName"),
                "source": "yfinance",
            }
        except Exception as e:
            logger.warning("YFinance quote failed for %s: %s", ticker, e)
            return None
