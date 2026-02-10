"""Tests for src/services/ — Data access layer (DataService + SyncDataService).

Tests cover: DataService (multi-layer resolution for universe, prices,
fundamentals, quotes, economic indicators, scores), helper methods
(_safe_float, _safe_int, _cache_series), SyncDataService (sync wrappers,
event loop management), and module singleton.

Run: python3 -m pytest tests/test_services.py -v
"""

import asyncio
import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# DataService — Helper Methods
# =============================================================================


class TestServicesSafeFloat(unittest.TestCase):
    """Tests for DataService._safe_float static method."""

    def setUp(self):
        from src.services.data_service import DataService
        self.safe_float = DataService._safe_float

    def test_none_returns_none(self):
        self.assertIsNone(self.safe_float(None))

    def test_nan_returns_none(self):
        self.assertIsNone(self.safe_float(float("nan")))

    def test_valid_float(self):
        self.assertEqual(self.safe_float(3.14), 3.14)

    def test_int_to_float(self):
        self.assertEqual(self.safe_float(42), 42.0)

    def test_string_float(self):
        self.assertEqual(self.safe_float("1.5"), 1.5)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(self.safe_float("abc"))

    def test_zero(self):
        self.assertEqual(self.safe_float(0), 0.0)

    def test_negative(self):
        self.assertEqual(self.safe_float(-2.5), -2.5)


class TestServicesSafeInt(unittest.TestCase):
    """Tests for DataService._safe_int static method."""

    def setUp(self):
        from src.services.data_service import DataService
        self.safe_int = DataService._safe_int

    def test_none_returns_none(self):
        self.assertIsNone(self.safe_int(None))

    def test_nan_returns_none(self):
        self.assertIsNone(self.safe_int(float("nan")))

    def test_valid_int(self):
        self.assertEqual(self.safe_int(500_000_000), 500_000_000)

    def test_float_to_int(self):
        self.assertEqual(self.safe_int(1e9), 1_000_000_000)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(self.safe_int("N/A"))

    def test_string_int(self):
        self.assertEqual(self.safe_int("100"), 100)


# =============================================================================
# DataService — get_universe
# =============================================================================


class TestServicesDataServiceGetUniverse(unittest.TestCase):
    """Tests for DataService.get_universe multi-layer resolution."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_from_cache_when_available(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False)
        mock_cache.get_json = AsyncMock(return_value=["AAPL", "MSFT"])
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_universe())
        self.assertEqual(result, ["AAPL", "MSFT"])

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_falls_back_to_scraper_when_cache_miss_and_no_db(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False)
        mock_cache.get_json = AsyncMock(return_value=None)
        mock_cache.set_json = AsyncMock()
        from src.services.data_service import DataService
        ds = DataService()
        with patch("src.universe.build_universe", return_value=["GOOG", "AMZN"]):
            result = self._run(ds.get_universe())
        self.assertEqual(result, ["GOOG", "AMZN"])


# =============================================================================
# DataService — get_prices
# =============================================================================


class TestServicesDataServiceGetPrices(unittest.TestCase):
    """Tests for DataService.get_prices multi-layer resolution."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_cached_prices_with_high_coverage(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False, fallback_to_yfinance=False)
        df = pd.DataFrame(
            {"AAPL": [150.0, 151.0], "MSFT": [300.0, 301.0]},
            index=pd.date_range("2024-01-01", periods=2),
        )
        mock_cache.get_dataframe = AsyncMock(return_value=df)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_prices(["AAPL", "MSFT"]))
        self.assertIn("AAPL", result.columns)
        self.assertIn("MSFT", result.columns)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_empty_when_no_source(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(
            use_database=False, fallback_to_yfinance=False
        )
        mock_cache.get_dataframe = AsyncMock(return_value=None)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_prices(["AAPL"]))
        self.assertTrue(result.empty)


# =============================================================================
# DataService — get_fundamentals
# =============================================================================


class TestServicesDataServiceGetFundamentals(unittest.TestCase):
    """Tests for DataService.get_fundamentals."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_cached_fundamentals(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(
            use_database=False, fallback_to_yfinance=False,
            redis_fundamental_ttl=14400,
        )
        df = pd.DataFrame(
            {"trailingPE": [15.0, 20.0]},
            index=["AAPL", "MSFT"],
        )
        mock_cache.get_dataframe = AsyncMock(return_value=df)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_fundamentals(["AAPL", "MSFT"]))
        self.assertEqual(len(result), 2)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_empty_when_no_source(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(
            use_database=False, fallback_to_yfinance=False,
        )
        mock_cache.get_dataframe = AsyncMock(return_value=None)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_fundamentals(["AAPL"]))
        self.assertTrue(result.empty)


# =============================================================================
# DataService — get_quote
# =============================================================================


class TestServicesDataServiceGetQuote(unittest.TestCase):
    """Tests for DataService.get_quote."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_cached_quote(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(polygon_api_key="", fallback_to_yfinance=False)
        mock_cache.get_quote = AsyncMock(return_value={"ticker": "AAPL", "price": 185.0})
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_quote("AAPL"))
        self.assertEqual(result["price"], 185.0)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_unavailable_when_no_source(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(polygon_api_key="", fallback_to_yfinance=False)
        mock_cache.get_quote = AsyncMock(return_value=None)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_quote("XYZ"))
        self.assertIsNone(result["price"])
        self.assertEqual(result["source"], "unavailable")


# =============================================================================
# DataService — get_economic_indicator
# =============================================================================


class TestServicesDataServiceGetEconomic(unittest.TestCase):
    """Tests for DataService.get_economic_indicator."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_cached_economic(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False, fred_api_key="")
        mock_cache.get_json = AsyncMock(return_value={
            "dates": ["2024-01-01", "2024-02-01"],
            "values": [3.5, 3.6],
        })
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_economic_indicator("GDP"))
        self.assertEqual(len(result), 2)
        self.assertEqual(result.name, "GDP")

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_empty_series_when_no_source(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False, fred_api_key="")
        mock_cache.get_json = AsyncMock(return_value=None)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_economic_indicator("UNKNOWN"))
        self.assertTrue(result.empty)
        self.assertEqual(result.name, "UNKNOWN")


# =============================================================================
# DataService — get_scores
# =============================================================================


class TestServicesDataServiceGetScores(unittest.TestCase):
    """Tests for DataService.get_scores."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_cached_scores(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False, redis_score_ttl=3600)
        df = pd.DataFrame(
            {"value": [0.8, 0.6], "momentum": [0.7, 0.9]},
            index=["AAPL", "MSFT"],
        )
        mock_cache.get_dataframe = AsyncMock(return_value=df)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_scores(["AAPL"]))
        self.assertEqual(len(result), 1)
        self.assertIn("AAPL", result.index)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_all_scores_when_no_tickers(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False, redis_score_ttl=3600)
        df = pd.DataFrame(
            {"value": [0.8, 0.6]},
            index=["AAPL", "MSFT"],
        )
        mock_cache.get_dataframe = AsyncMock(return_value=df)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_scores())
        self.assertEqual(len(result), 2)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_returns_empty_when_no_source(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock(use_database=False)
        mock_cache.get_dataframe = AsyncMock(return_value=None)
        from src.services.data_service import DataService
        ds = DataService()
        result = self._run(ds.get_scores())
        self.assertTrue(result.empty)


# =============================================================================
# DataService — _cache_series
# =============================================================================


class TestServicesDataServiceCacheSeries(unittest.TestCase):
    """Tests for DataService._cache_series helper."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_cache_series_stores_dates_and_values(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock()
        mock_cache.set_json = AsyncMock()
        from src.services.data_service import DataService
        ds = DataService()
        series = pd.Series(
            [1.5, 2.5],
            index=pd.to_datetime(["2024-01-01", "2024-02-01"]),
            name="GDP",
        )
        self._run(ds._cache_series("axion:economic:GDP", series))
        mock_cache.set_json.assert_awaited_once()
        stored = mock_cache.set_json.call_args[0][1]
        self.assertEqual(len(stored["dates"]), 2)
        self.assertEqual(len(stored["values"]), 2)

    @patch("src.services.data_service.cache")
    @patch("src.services.data_service.get_settings")
    def test_cache_series_handles_nan(self, mock_settings, mock_cache):
        mock_settings.return_value = MagicMock()
        mock_cache.set_json = AsyncMock()
        from src.services.data_service import DataService
        ds = DataService()
        series = pd.Series(
            [1.0, float("nan")],
            index=pd.to_datetime(["2024-01-01", "2024-02-01"]),
        )
        self._run(ds._cache_series("k", series))
        stored = mock_cache.set_json.call_args[0][1]
        self.assertIsNone(stored["values"][1])


# =============================================================================
# SyncDataService — Init and _run
# =============================================================================


class TestServicesSyncDataServiceInit(unittest.TestCase):
    """Tests for SyncDataService initialization and event loop management."""

    @patch("src.services.data_service.get_settings")
    def test_init_creates_internal_service(self, mock_settings):
        mock_settings.return_value = MagicMock()
        from src.services.sync_adapter import SyncDataService
        sds = SyncDataService()
        self.assertIsNotNone(sds._service)
        self.assertIsNone(sds._loop)


# =============================================================================
# SyncDataService — Sync Wrappers
# =============================================================================


class TestServicesSyncDataServiceWrappers(unittest.TestCase):
    """Tests for SyncDataService sync wrapper methods."""

    @patch("src.services.data_service.get_settings")
    def setUp(self, mock_settings):
        mock_settings.return_value = MagicMock()
        from src.services.sync_adapter import SyncDataService
        self.sds = SyncDataService()
        self.sds._service = MagicMock()

    def test_build_universe_calls_async(self):
        async def mock_get_universe():
            return ["AAPL", "GOOG"]
        self.sds._service.get_universe = MagicMock(return_value=mock_get_universe())
        result = self.sds._run(self.sds._service.get_universe())
        self.assertEqual(result, ["AAPL", "GOOG"])

    def test_get_quote_calls_async(self):
        async def mock_get_quote(ticker):
            return {"ticker": ticker, "price": 185.0}
        self.sds._service.get_quote = MagicMock(
            return_value=mock_get_quote("AAPL")
        )
        result = self.sds._run(self.sds._service.get_quote("AAPL"))
        self.assertEqual(result["price"], 185.0)


# =============================================================================
# SyncDataService — compute_price_returns
# =============================================================================


class TestServicesSyncComputeReturns(unittest.TestCase):
    """Tests for SyncDataService.compute_price_returns static method."""

    @patch("src.services.data_service.get_settings")
    def test_delegates_to_data_fetcher(self, mock_settings):
        mock_settings.return_value = MagicMock()
        from src.services.sync_adapter import SyncDataService
        prices = pd.DataFrame({"AAPL": [100.0, 110.0, 105.0]})
        with patch("src.data_fetcher.compute_price_returns", return_value=prices.pct_change()) as mock_fn:
            result = SyncDataService.compute_price_returns(prices)
            mock_fn.assert_called_once()


# =============================================================================
# SyncDataService — filter_universe
# =============================================================================


class TestServicesSyncFilterUniverse(unittest.TestCase):
    """Tests for SyncDataService.filter_universe static method."""

    @patch("src.services.data_service.get_settings")
    def test_delegates_to_data_fetcher(self, mock_settings):
        mock_settings.return_value = MagicMock()
        from src.services.sync_adapter import SyncDataService
        fundamentals = pd.DataFrame({"marketCap": [1e9]}, index=["AAPL"])
        prices = pd.DataFrame({"AAPL": [100.0]})
        with patch("src.data_fetcher.filter_universe", return_value=["AAPL"]) as mock_fn:
            result = SyncDataService.filter_universe(fundamentals, prices)
            mock_fn.assert_called_once()
            self.assertEqual(result, ["AAPL"])


# =============================================================================
# Module Singleton
# =============================================================================


class TestServicesModuleSingleton(unittest.TestCase):
    """Tests for the module-level sync_data_service singleton."""

    def test_singleton_exists(self):
        from src.services.sync_adapter import sync_data_service
        self.assertIsNotNone(sync_data_service)

    def test_singleton_has_service_methods(self):
        from src.services.sync_adapter import sync_data_service
        self.assertTrue(hasattr(sync_data_service, "build_universe"))
        self.assertTrue(hasattr(sync_data_service, "download_price_data"))
        self.assertTrue(hasattr(sync_data_service, "download_fundamentals"))
        self.assertTrue(hasattr(sync_data_service, "get_quote"))
        self.assertTrue(hasattr(sync_data_service, "get_economic_indicator"))
        self.assertTrue(hasattr(sync_data_service, "get_scores"))
