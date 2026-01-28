"""Synchronous adapter for DataService.

Provides backward-compatible synchronous wrappers around the async DataService
so that existing code (main.py, app/tools.py, factor_model.py, portfolio.py,
backtest.py) can use the new data layer without any changes to their calling code.

Usage:
    from src.services.sync_adapter import sync_data_service as ds
    prices = ds.download_price_data(tickers)
    fundamentals = ds.download_fundamentals(tickers)
"""

import asyncio
import logging
from typing import Optional

import pandas as pd

from src.services.data_service import DataService

logger = logging.getLogger(__name__)


class SyncDataService:
    """Synchronous wrapper around async DataService.

    Exposes the same function signatures as src/data_fetcher.py
    so callers don't need any changes.
    """

    def __init__(self):
        self._service = DataService()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
            # Inside an existing event loop (e.g., Streamlit, Jupyter)
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except RuntimeError:
            # No running loop — create one
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            return self._loop.run_until_complete(coro)

    def build_universe(self, verbose: bool = False) -> list[str]:
        """Get stock universe. Replaces universe.build_universe()."""
        return self._run(self._service.get_universe())

    def download_price_data(
        self,
        tickers: list[str],
        use_cache: bool = True,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """Get historical prices. Replaces data_fetcher.download_price_data()."""
        return self._run(self._service.get_prices(tickers))

    def download_fundamentals(
        self,
        tickers: list[str],
        use_cache: bool = True,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """Get fundamentals. Replaces data_fetcher.download_fundamentals()."""
        return self._run(self._service.get_fundamentals(tickers))

    def get_quote(self, ticker: str) -> dict:
        """Get real-time quote for a single ticker."""
        return self._run(self._service.get_quote(ticker))

    def get_economic_indicator(self, series_id: str, start: Optional[str] = None) -> pd.Series:
        """Get FRED economic indicator."""
        return self._run(self._service.get_economic_indicator(series_id, start))

    def get_scores(self, tickers: Optional[list[str]] = None) -> pd.DataFrame:
        """Get pre-computed factor scores from database."""
        return self._run(self._service.get_scores(tickers))

    @staticmethod
    def compute_price_returns(prices: pd.DataFrame) -> pd.DataFrame:
        """Delegate to existing pure-computation function (no I/O change)."""
        from src.data_fetcher import compute_price_returns
        return compute_price_returns(prices)

    @staticmethod
    def filter_universe(
        fundamentals: pd.DataFrame,
        prices: pd.DataFrame,
        verbose: bool = False,
    ) -> list[str]:
        """Delegate to existing pure-computation function (no I/O change)."""
        from src.data_fetcher import filter_universe
        return filter_universe(fundamentals, prices, verbose)


# Module-level singleton
sync_data_service = SyncDataService()
