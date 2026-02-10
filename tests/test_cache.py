"""Tests for src/cache/ — Redis caching package.

Tests cover: RedisCache (async + sync operations, DataFrame/JSON serialization,
quote shortcuts, cache invalidation, connection management), cache key templates,
and module-level singleton.

Run: python3 -m pytest tests/test_cache.py -v
"""

import asyncio
import json
import os
import pickle
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cache.redis_client import RedisCache
from src.cache import keys


# =============================================================================
# RedisCache — Async DataFrame Operations
# =============================================================================


class TestCacheAsyncDataFrame(unittest.TestCase):
    """Tests for async DataFrame get/set on RedisCache."""

    def setUp(self):
        self.cache = RedisCache()
        self.mock_client = AsyncMock()
        self.cache._async_client = self.mock_client

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_get_dataframe_returns_none_when_key_missing(self):
        self.mock_client.get = AsyncMock(return_value=None)
        result = self._run(self.cache.get_dataframe("axion:prices:AAPL:1d"))
        self.assertIsNone(result)

    def test_get_dataframe_deserializes_pickle(self):
        df = pd.DataFrame({"close": [100.0, 101.0]})
        self.mock_client.get = AsyncMock(return_value=pickle.dumps(df))
        result = self._run(self.cache.get_dataframe("axion:prices:AAPL:1d"))
        pd.testing.assert_frame_equal(result, df)

    def test_set_dataframe_calls_setex_with_pickle(self):
        df = pd.DataFrame({"close": [150.0]})
        self.mock_client.setex = AsyncMock()
        self._run(self.cache.set_dataframe("k", df, 300))
        self.mock_client.setex.assert_awaited_once()
        args = self.mock_client.setex.call_args
        self.assertEqual(args[0][0], "k")
        self.assertEqual(args[0][1], 300)
        restored = pickle.loads(args[0][2])
        pd.testing.assert_frame_equal(restored, df)

    def test_get_dataframe_returns_none_on_exception(self):
        self.mock_client.get = AsyncMock(side_effect=ConnectionError("down"))
        result = self._run(self.cache.get_dataframe("k"))
        self.assertIsNone(result)

    def test_set_dataframe_handles_exception_gracefully(self):
        self.mock_client.setex = AsyncMock(side_effect=ConnectionError("down"))
        # Should not raise
        self._run(self.cache.set_dataframe("k", pd.DataFrame(), 60))

    def test_set_dataframe_uses_highest_protocol(self):
        df = pd.DataFrame({"a": [1]})
        self.mock_client.setex = AsyncMock()
        self._run(self.cache.set_dataframe("k", df, 10))
        raw = self.mock_client.setex.call_args[0][2]
        self.assertEqual(pickle.loads(raw).iloc[0, 0], 1)


# =============================================================================
# RedisCache — Async JSON Operations
# =============================================================================


class TestCacheAsyncJSON(unittest.TestCase):
    """Tests for async JSON get/set on RedisCache."""

    def setUp(self):
        self.cache = RedisCache()
        self.mock_client = AsyncMock()
        self.cache._async_client = self.mock_client

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_get_json_returns_none_when_missing(self):
        self.mock_client.get = AsyncMock(return_value=None)
        result = self._run(self.cache.get_json("axion:scores:all"))
        self.assertIsNone(result)

    def test_get_json_deserializes_json(self):
        payload = {"ticker": "AAPL", "price": 185.5}
        self.mock_client.get = AsyncMock(return_value=json.dumps(payload).encode())
        result = self._run(self.cache.get_json("k"))
        self.assertEqual(result, payload)

    def test_set_json_calls_setex(self):
        self.mock_client.setex = AsyncMock()
        data = {"foo": "bar", "num": 42}
        self._run(self.cache.set_json("k", data, 60))
        self.mock_client.setex.assert_awaited_once()
        stored = json.loads(self.mock_client.setex.call_args[0][2])
        self.assertEqual(stored["foo"], "bar")
        self.assertEqual(stored["num"], 42)

    def test_get_json_returns_none_on_error(self):
        self.mock_client.get = AsyncMock(side_effect=TimeoutError)
        result = self._run(self.cache.get_json("k"))
        self.assertIsNone(result)

    def test_set_json_handles_datetime_via_default_str(self):
        from datetime import datetime
        self.mock_client.setex = AsyncMock()
        data = {"ts": datetime(2025, 1, 15, 12, 0)}
        self._run(self.cache.set_json("k", data, 30))
        stored = json.loads(self.mock_client.setex.call_args[0][2])
        self.assertIn("2025", stored["ts"])

    def test_set_json_error_does_not_raise(self):
        self.mock_client.setex = AsyncMock(side_effect=Exception("fail"))
        self._run(self.cache.set_json("k", {"x": 1}, 30))  # no raise

    def test_get_json_with_list_payload(self):
        payload = ["AAPL", "MSFT", "GOOG"]
        self.mock_client.get = AsyncMock(return_value=json.dumps(payload).encode())
        result = self._run(self.cache.get_json("axion:universe:sp500"))
        self.assertEqual(result, payload)


# =============================================================================
# RedisCache — Quote Shortcuts
# =============================================================================


class TestCacheQuoteShortcuts(unittest.TestCase):
    """Tests for get_quote / set_quote convenience methods."""

    def setUp(self):
        self.cache = RedisCache()
        self.mock_client = AsyncMock()
        self.cache._async_client = self.mock_client

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_get_quote_uses_correct_key(self):
        self.mock_client.get = AsyncMock(return_value=None)
        self._run(self.cache.get_quote("TSLA"))
        self.mock_client.get.assert_awaited_once_with("axion:quote:TSLA")

    def test_get_quote_returns_dict(self):
        quote = {"ticker": "AAPL", "price": 185.0}
        self.mock_client.get = AsyncMock(return_value=json.dumps(quote).encode())
        result = self._run(self.cache.get_quote("AAPL"))
        self.assertEqual(result["price"], 185.0)

    def test_set_quote_uses_configured_ttl(self):
        settings = MagicMock()
        settings.redis_quote_ttl = 45
        self.mock_client.setex = AsyncMock()
        with patch("src.settings.get_settings", return_value=settings):
            self._run(self.cache.set_quote("MSFT", {"price": 400}))
        self.mock_client.setex.assert_awaited_once()
        self.assertEqual(self.mock_client.setex.call_args[0][1], 45)


# =============================================================================
# RedisCache — Sync Operations
# =============================================================================


class TestCacheSyncOperations(unittest.TestCase):
    """Tests for synchronous backward-compatibility wrappers."""

    def setUp(self):
        self.cache = RedisCache()
        self.mock_client = MagicMock()
        self.cache._sync_client = self.mock_client

    def test_get_dataframe_sync_returns_none_when_missing(self):
        self.mock_client.get.return_value = None
        result = self.cache.get_dataframe_sync("k")
        self.assertIsNone(result)

    def test_get_dataframe_sync_deserializes(self):
        df = pd.DataFrame({"vol": [1000, 2000]})
        self.mock_client.get.return_value = pickle.dumps(df)
        result = self.cache.get_dataframe_sync("k")
        pd.testing.assert_frame_equal(result, df)

    def test_set_dataframe_sync_calls_setex(self):
        df = pd.DataFrame({"a": [1]})
        self.cache.set_dataframe_sync("k", df, 120)
        self.mock_client.setex.assert_called_once()

    def test_get_json_sync_returns_none_on_error(self):
        self.mock_client.get.side_effect = ConnectionError("down")
        result = self.cache.get_json_sync("k")
        self.assertIsNone(result)

    def test_get_json_sync_deserializes(self):
        data = {"price": 150.5}
        self.mock_client.get.return_value = json.dumps(data).encode()
        result = self.cache.get_json_sync("k")
        self.assertEqual(result["price"], 150.5)

    def test_set_json_sync_calls_setex(self):
        self.cache.set_json_sync("k", {"x": 1}, 60)
        self.mock_client.setex.assert_called_once()

    def test_set_json_sync_handles_error(self):
        self.mock_client.setex.side_effect = Exception("fail")
        self.cache.set_json_sync("k", {"x": 1}, 60)  # no raise

    def test_get_dataframe_sync_returns_none_on_error(self):
        self.mock_client.get.side_effect = Exception("broken")
        result = self.cache.get_dataframe_sync("k")
        self.assertIsNone(result)

    def test_set_dataframe_sync_handles_error(self):
        self.mock_client.setex.side_effect = Exception("broken")
        self.cache.set_dataframe_sync("k", pd.DataFrame(), 10)  # no raise


# =============================================================================
# RedisCache — Connection Management
# =============================================================================


class TestCacheConnectionManagement(unittest.TestCase):
    """Tests for get_async_client, get_sync_client, close."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_get_sync_client_raises_on_failure(self):
        settings = MagicMock(redis_url="redis://bad:9999")
        cache = RedisCache()
        with patch("src.settings.get_settings", return_value=settings):
            with patch("redis.from_url", side_effect=ConnectionError("nope")):
                with self.assertRaises(ConnectionError):
                    cache.get_sync_client()
        self.assertIsNone(cache._sync_client)

    def test_close_clears_both_clients(self):
        cache = RedisCache()
        cache._async_client = AsyncMock()
        cache._sync_client = MagicMock()
        self._run(cache.close())
        self.assertIsNone(cache._async_client)
        self.assertIsNone(cache._sync_client)

    def test_close_noop_when_no_clients(self):
        cache = RedisCache()
        self._run(cache.close())  # should not raise


# =============================================================================
# RedisCache — Cache Invalidation
# =============================================================================


class TestCacheInvalidation(unittest.TestCase):
    """Tests for pattern-based cache invalidation."""

    def setUp(self):
        self.cache = RedisCache()
        self.mock_client = AsyncMock()
        self.cache._async_client = self.mock_client

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_invalidate_pattern_deletes_matching_keys(self):
        async def scan_iter_mock(match=None):
            for key in [b"axion:quote:AAPL", b"axion:quote:MSFT"]:
                yield key

        self.mock_client.scan_iter = scan_iter_mock
        self.mock_client.delete = AsyncMock()
        count = self._run(self.cache.invalidate_pattern("axion:quote:*"))
        self.assertEqual(count, 2)
        self.assertEqual(self.mock_client.delete.await_count, 2)

    def test_invalidate_pattern_returns_zero_on_error(self):
        self.mock_client.scan_iter = MagicMock(side_effect=ConnectionError)
        count = self._run(self.cache.invalidate_pattern("axion:*"))
        self.assertEqual(count, 0)

    def test_invalidate_pattern_returns_zero_when_no_keys(self):
        async def scan_iter_mock(match=None):
            return
            yield  # make this an async generator

        self.mock_client.scan_iter = scan_iter_mock
        count = self._run(self.cache.invalidate_pattern("axion:nothing:*"))
        self.assertEqual(count, 0)


# =============================================================================
# Cache Key Templates
# =============================================================================


class TestCacheKeyTemplates(unittest.TestCase):
    """Tests for key naming conventions in keys.py."""

    def test_quote_key_format(self):
        self.assertEqual(keys.QUOTE.format(ticker="AAPL"), "axion:quote:AAPL")

    def test_prices_key_format(self):
        key = keys.PRICES.format(ticker="MSFT", timeframe="1d")
        self.assertEqual(key, "axion:prices:MSFT:1d")

    def test_prices_bulk_key(self):
        key = keys.PRICES_BULK.format(hash="abc123")
        self.assertEqual(key, "axion:prices:bulk:abc123")

    def test_fundamentals_key(self):
        key = keys.FUNDAMENTALS.format(ticker="GOOG")
        self.assertEqual(key, "axion:fundamentals:GOOG")

    def test_fundamentals_all_key(self):
        self.assertEqual(keys.FUNDAMENTALS_ALL, "axion:fundamentals:all")

    def test_scores_all_key(self):
        self.assertEqual(keys.SCORES_ALL, "axion:scores:all")

    def test_scores_ticker_key(self):
        key = keys.SCORES_TICKER.format(ticker="TSLA")
        self.assertEqual(key, "axion:scores:TSLA")

    def test_universe_key(self):
        key = keys.UNIVERSE.format(index="sp500")
        self.assertEqual(key, "axion:universe:sp500")

    def test_economic_key(self):
        key = keys.ECONOMIC.format(series_id="GDP")
        self.assertEqual(key, "axion:economic:GDP")

    def test_session_key(self):
        key = keys.SESSION.format(session_id="sess_abc")
        self.assertEqual(key, "axion:session:sess_abc")

    def test_all_keys_have_axion_prefix(self):
        for attr in dir(keys):
            if attr.isupper() and not attr.startswith("_"):
                val = getattr(keys, attr)
                if isinstance(val, str):
                    self.assertTrue(val.startswith("axion:"), f"{attr} missing axion: prefix")


# =============================================================================
# Module Singleton
# =============================================================================


class TestCacheModuleSingleton(unittest.TestCase):
    """Tests for the module-level cache singleton."""

    def test_singleton_exists(self):
        from src.cache import cache
        self.assertIsInstance(cache, RedisCache)

    def test_singleton_is_same_instance(self):
        from src.cache import cache as c1
        from src.cache.redis_client import cache as c2
        self.assertIs(c1, c2)

    def test_singleton_starts_disconnected(self):
        cache = RedisCache()
        self.assertIsNone(cache._async_client)
        self.assertIsNone(cache._sync_client)
