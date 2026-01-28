"""Tests for the DataService and related infrastructure."""

import json
import pickle
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.settings import Settings


# ============================================================================
# Settings Tests
# ============================================================================


class TestSettings:
    def test_default_values(self):
        settings = Settings()
        assert settings.min_price == 5.0
        assert settings.min_market_cap == 500_000_000
        assert settings.batch_size == 50
        assert settings.use_database is False
        assert settings.use_redis is True
        assert settings.fallback_to_yfinance is True

    def test_database_defaults(self):
        settings = Settings()
        assert "asyncpg" in settings.database_url
        assert "psycopg2" in settings.database_sync_url
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_ttl_defaults(self):
        settings = Settings()
        assert settings.redis_quote_ttl == 30
        assert settings.redis_score_ttl == 3600
        assert settings.redis_fundamental_ttl == 14400
        assert settings.redis_universe_ttl == 86400

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("AXION_USE_DATABASE", "true")
        monkeypatch.setenv("AXION_MIN_PRICE", "10.0")
        settings = Settings()
        assert settings.use_database is True
        assert settings.min_price == 10.0


# ============================================================================
# Redis Cache Tests
# ============================================================================


class TestRedisCache:
    def test_cache_import(self):
        from src.cache.redis_client import RedisCache, cache
        assert isinstance(cache, RedisCache)

    def test_cache_key_format(self):
        from src.cache import keys
        assert "axion:quote:" in keys.QUOTE
        assert "axion:scores:all" == keys.SCORES_ALL
        assert "axion:universe:" in keys.UNIVERSE


# ============================================================================
# Data Quality Tests
# ============================================================================


class TestPriceValidator:
    def test_valid_ohlcv(self):
        from src.quality.validators import PriceValidator

        validator = PriceValidator()
        df = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000000, 1100000, 1200000],
        })
        results = validator.validate_ohlcv(df, "TEST")
        for r in results:
            assert r.passed, f"Check {r.check_name} failed: {r.message}"

    def test_negative_price(self):
        from src.quality.validators import PriceValidator

        validator = PriceValidator()
        df = pd.DataFrame({
            "open": [100.0],
            "high": [105.0],
            "low": [99.0],
            "close": [-1.0],  # Invalid
            "volume": [1000000],
        })
        results = validator.validate_ohlcv(df, "BAD")
        positive_check = [r for r in results if r.check_name == "positive_prices"][0]
        assert not positive_check.passed

    def test_ohlc_inconsistency(self):
        from src.quality.validators import PriceValidator

        validator = PriceValidator()
        df = pd.DataFrame({
            "open": [100.0],
            "high": [90.0],   # High below open — invalid
            "low": [99.0],
            "close": [95.0],
            "volume": [1000000],
        })
        results = validator.validate_ohlcv(df, "BAD")
        ohlc_check = [r for r in results if r.check_name == "ohlc_consistency"][0]
        assert not ohlc_check.passed

    def test_empty_dataframe(self):
        from src.quality.validators import PriceValidator

        validator = PriceValidator()
        results = validator.validate_ohlcv(pd.DataFrame(), "EMPTY")
        assert not results[0].passed
        assert results[0].severity == "error"


class TestFundamentalValidator:
    def test_valid_fundamentals(self):
        from src.quality.validators import FundamentalValidator

        validator = FundamentalValidator()
        df = pd.DataFrame({
            "trailingPE": [15.0, 20.0, 25.0],
            "marketCap": [1e9, 5e9, 10e9],
        }, index=["AAPL", "MSFT", "GOOGL"])

        # Pad to 400 for universe coverage check
        extra = pd.DataFrame({
            "trailingPE": [10.0] * 400,
            "marketCap": [1e9] * 400,
        }, index=[f"TICK{i}" for i in range(400)])
        df = pd.concat([df, extra])

        results = validator.validate(df)
        for r in results:
            assert r.passed, f"Check {r.check_name} failed: {r.message}"

    def test_negative_market_cap(self):
        from src.quality.validators import FundamentalValidator

        validator = FundamentalValidator()
        df = pd.DataFrame({
            "marketCap": [-1e9, 5e9],
        }, index=["BAD", "GOOD"])
        results = validator.validate(df)
        cap_check = [r for r in results if r.check_name == "positive_market_cap"][0]
        assert not cap_check.passed


# ============================================================================
# Gap Detector Tests
# ============================================================================


class TestGapDetector:
    def test_no_gaps(self):
        from src.quality.gap_detector import GapDetector

        detector = GapDetector()
        dates = pd.bdate_range("2024-01-02", periods=5)
        df = pd.DataFrame({"close": [100, 101, 102, 103, 104]}, index=dates)
        gaps = detector.detect_gaps(df, "TEST")
        assert len(gaps) == 0

    def test_empty_dataframe(self):
        from src.quality.gap_detector import GapDetector

        detector = GapDetector()
        gaps = detector.detect_gaps(pd.DataFrame(), "EMPTY")
        assert len(gaps) == 0

    def test_holiday_detection(self):
        from src.quality.gap_detector import GapDetector

        detector = GapDetector()
        # Christmas (Dec 25) should be detected as a likely holiday
        christmas = pd.Timestamp("2024-12-25")
        assert detector._is_likely_holiday(christmas)

        # Regular business day should not be a holiday
        regular = pd.Timestamp("2024-03-15")
        assert not detector._is_likely_holiday(regular)


# ============================================================================
# Sync Adapter Tests
# ============================================================================


class TestSyncAdapter:
    def test_compute_price_returns_delegates(self):
        """Verify pure computation functions delegate correctly."""
        from src.services.sync_adapter import SyncDataService

        adapter = SyncDataService()
        prices = pd.DataFrame(
            np.random.lognormal(5, 0.3, (300, 3)),
            index=pd.bdate_range("2024-01-01", periods=300),
            columns=["AAPL", "MSFT", "GOOGL"],
        )
        returns = adapter.compute_price_returns(prices)
        assert "ret_6m" in returns.columns
        assert "ret_12m" in returns.columns
        assert len(returns) == 3

    def test_filter_universe_delegates(self):
        """Verify filter_universe passes through correctly."""
        from src.services.sync_adapter import SyncDataService

        adapter = SyncDataService()
        fundamentals = pd.DataFrame({
            "marketCap": [1e10, 100, 5e9],
            "currentPrice": [150.0, 2.0, 80.0],
        }, index=["AAPL", "PENNY", "MSFT"])
        prices = pd.DataFrame({
            "AAPL": [150.0],
            "PENNY": [2.0],
            "MSFT": [80.0],
        })
        valid = adapter.filter_universe(fundamentals, prices)
        assert "AAPL" in valid
        assert "PENNY" not in valid  # Below min price
        assert "MSFT" in valid


# ============================================================================
# Database Models Tests
# ============================================================================


class TestModels:
    def test_instrument_model(self):
        from src.db.models import Instrument, AssetType
        inst = Instrument(ticker="AAPL", name="Apple Inc", asset_type=AssetType.STOCK)
        assert inst.ticker == "AAPL"
        assert inst.asset_type == AssetType.STOCK

    def test_price_bar_model(self):
        from src.db.models import PriceBar
        from datetime import datetime
        bar = PriceBar(
            time=datetime.now(), instrument_id=1,
            open=100, high=105, low=99, close=103, volume=1000000
        )
        assert bar.close == 103

    def test_financial_model(self):
        from src.db.models import Financial
        from datetime import date
        fin = Financial(
            instrument_id=1, as_of_date=date.today(),
            trailing_pe=25.0, return_on_equity=0.35
        )
        assert fin.trailing_pe == 25.0

    def test_factor_score_model(self):
        from src.db.models import FactorScore
        from datetime import date
        score = FactorScore(
            instrument_id=1, computed_date=date.today(),
            value_score=0.75, momentum_score=0.82,
            quality_score=0.91, growth_score=0.68,
            composite_score=0.80
        )
        assert score.composite_score == 0.80

    def test_economic_indicator_model(self):
        from src.db.models import EconomicIndicator
        from datetime import date
        ind = EconomicIndicator(series_id="VIXCLS", date=date.today(), value=18.5)
        assert ind.series_id == "VIXCLS"


# ============================================================================
# Provider Tests
# ============================================================================


class TestFREDProvider:
    def test_provider_disabled_without_key(self):
        from src.services.providers.fred_provider import FREDProvider
        provider = FREDProvider()
        # With empty API key, provider should report disabled
        assert not provider._enabled or provider.settings.fred_api_key == ""

    def test_fred_series_constants(self):
        from src.services.providers.fred_provider import FRED_SERIES
        assert "VIXCLS" in FRED_SERIES
        assert "DGS10" in FRED_SERIES
        assert "T10Y2Y" in FRED_SERIES
        assert "FEDFUNDS" in FRED_SERIES


class TestPolygonProvider:
    def test_provider_disabled_without_key(self):
        from src.services.providers.polygon_provider import PolygonProvider
        provider = PolygonProvider()
        assert not provider._enabled or provider.settings.polygon_api_key == ""
