"""Tests for src/db/ — Database engine, base, and ORM models.

Tests cover: Base declarative base, engine factory functions (async/sync),
session factories, ORM model definitions (Instrument, PriceBar, Financial,
FactorScore, EconomicIndicator, DataQualityLog), model column types,
table constraints, and enum types.

Run: python3 -m pytest tests/test_db.py -v
"""

import os
import sys
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.base import Base
from src.db.models import (
    AssetType,
    MarketRegimeType,
    Instrument,
    PriceBar,
    Financial,
    FactorScore,
    EconomicIndicator,
    DataQualityLog,
)


# =============================================================================
# Declarative Base
# =============================================================================


class TestDbBase(unittest.TestCase):
    """Tests for the SQLAlchemy declarative base."""

    def test_base_is_declarative_base(self):
        from sqlalchemy.orm import DeclarativeBase
        self.assertTrue(issubclass(Base, DeclarativeBase))

    def test_base_has_metadata(self):
        self.assertIsNotNone(Base.metadata)

    def test_base_metadata_has_tables(self):
        tables = Base.metadata.tables
        self.assertIn("instruments", tables)
        self.assertIn("price_bars", tables)
        self.assertIn("financials", tables)


# =============================================================================
# Engine Factory — Async
# =============================================================================


class TestDbAsyncEngine(unittest.TestCase):
    """Tests for async engine creation."""

    def setUp(self):
        import src.db.engine as engine_module
        self._orig_async = engine_module._async_engine
        engine_module._async_engine = None

    def tearDown(self):
        import src.db.engine as engine_module
        engine_module._async_engine = self._orig_async

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_async_engine")
    def test_get_async_engine_creates_engine_once(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_url="postgresql+asyncpg://test:test@localhost/test"
        )
        mock_create.return_value = MagicMock()

        from src.db.engine import get_async_engine
        e1 = get_async_engine()
        e2 = get_async_engine()
        self.assertIs(e1, e2)
        mock_create.assert_called_once()

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_async_engine")
    def test_get_async_engine_uses_settings_url(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_url="postgresql+asyncpg://user:pass@host/db"
        )
        mock_create.return_value = MagicMock()
        from src.db.engine import get_async_engine
        get_async_engine()
        call_args = mock_create.call_args
        self.assertEqual(call_args[0][0], "postgresql+asyncpg://user:pass@host/db")

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_async_engine")
    def test_get_async_engine_sets_pool_params(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_url="postgresql+asyncpg://test:test@localhost/test"
        )
        mock_create.return_value = MagicMock()
        from src.db.engine import get_async_engine
        get_async_engine()
        kwargs = mock_create.call_args[1]
        self.assertEqual(kwargs["pool_size"], 20)
        self.assertEqual(kwargs["max_overflow"], 10)
        self.assertTrue(kwargs["pool_pre_ping"])


# =============================================================================
# Engine Factory — Sync
# =============================================================================


class TestDbSyncEngine(unittest.TestCase):
    """Tests for sync engine creation."""

    def setUp(self):
        import src.db.engine as engine_module
        self._orig_sync = engine_module._sync_engine
        engine_module._sync_engine = None

    def tearDown(self):
        import src.db.engine as engine_module
        engine_module._sync_engine = self._orig_sync

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_engine")
    def test_get_sync_engine_creates_once(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_sync_url="postgresql+psycopg2://test:test@localhost/test"
        )
        mock_create.return_value = MagicMock()
        from src.db.engine import get_sync_engine
        e1 = get_sync_engine()
        e2 = get_sync_engine()
        self.assertIs(e1, e2)
        mock_create.assert_called_once()

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_engine")
    def test_get_sync_engine_uses_sync_url(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_sync_url="postgresql+psycopg2://u:p@h/d"
        )
        mock_create.return_value = MagicMock()
        from src.db.engine import get_sync_engine
        get_sync_engine()
        self.assertEqual(mock_create.call_args[0][0], "postgresql+psycopg2://u:p@h/d")

    @patch("src.db.engine.get_settings")
    @patch("src.db.engine.create_engine")
    def test_get_sync_engine_sets_pre_ping(self, mock_create, mock_settings):
        mock_settings.return_value = MagicMock(
            database_sync_url="postgresql+psycopg2://test:test@localhost/test"
        )
        mock_create.return_value = MagicMock()
        from src.db.engine import get_sync_engine
        get_sync_engine()
        self.assertTrue(mock_create.call_args[1]["pool_pre_ping"])


# =============================================================================
# Session Factories
# =============================================================================


class TestDbSessionFactories(unittest.TestCase):
    """Tests for session factory aliases."""

    def test_async_session_local_is_callable(self):
        from src.db.engine import AsyncSessionLocal
        self.assertTrue(callable(AsyncSessionLocal))

    def test_sync_session_local_is_callable(self):
        from src.db.engine import SyncSessionLocal
        self.assertTrue(callable(SyncSessionLocal))


# =============================================================================
# Enum Types
# =============================================================================


class TestDbEnumTypes(unittest.TestCase):
    """Tests for ORM enum types."""

    def test_asset_type_values(self):
        self.assertEqual(AssetType.STOCK.value, "stock")
        self.assertEqual(AssetType.ETF.value, "etf")
        self.assertEqual(AssetType.INDEX.value, "index")

    def test_market_regime_type_values(self):
        self.assertEqual(MarketRegimeType.BULL.value, "bull")
        self.assertEqual(MarketRegimeType.BEAR.value, "bear")
        self.assertEqual(MarketRegimeType.SIDEWAYS.value, "sideways")
        self.assertEqual(MarketRegimeType.CRISIS.value, "crisis")

    def test_asset_type_members(self):
        members = list(AssetType)
        self.assertEqual(len(members), 3)

    def test_market_regime_members(self):
        members = list(MarketRegimeType)
        self.assertEqual(len(members), 4)


# =============================================================================
# Instrument Model
# =============================================================================


class TestDbInstrumentModel(unittest.TestCase):
    """Tests for the Instrument ORM model."""

    def test_tablename(self):
        self.assertEqual(Instrument.__tablename__, "instruments")

    def test_has_primary_key(self):
        cols = {c.name for c in Instrument.__table__.columns}
        self.assertIn("id", cols)

    def test_has_ticker_column(self):
        col = Instrument.__table__.c.ticker
        self.assertFalse(col.nullable)
        self.assertTrue(col.unique)

    def test_has_gics_columns(self):
        cols = {c.name for c in Instrument.__table__.columns}
        self.assertIn("gics_sector", cols)
        self.assertIn("gics_industry_group", cols)
        self.assertIn("gics_industry", cols)
        self.assertIn("gics_sub_industry", cols)

    def test_is_active_default(self):
        col = Instrument.__table__.c.is_active
        self.assertIsNotNone(col.default)

    def test_has_market_cap_column(self):
        cols = {c.name for c in Instrument.__table__.columns}
        self.assertIn("market_cap", cols)


# =============================================================================
# PriceBar Model
# =============================================================================


class TestDbPriceBarModel(unittest.TestCase):
    """Tests for the PriceBar ORM model."""

    def test_tablename(self):
        self.assertEqual(PriceBar.__tablename__, "price_bars")

    def test_has_ohlcv_columns(self):
        cols = {c.name for c in PriceBar.__table__.columns}
        for col in ["open", "high", "low", "close", "volume", "adj_close"]:
            self.assertIn(col, cols, f"Missing {col}")

    def test_composite_primary_key(self):
        pk_cols = [c.name for c in PriceBar.__table__.primary_key.columns]
        self.assertIn("time", pk_cols)
        self.assertIn("instrument_id", pk_cols)

    def test_has_source_column(self):
        cols = {c.name for c in PriceBar.__table__.columns}
        self.assertIn("source", cols)


# =============================================================================
# Financial Model
# =============================================================================


class TestDbFinancialModel(unittest.TestCase):
    """Tests for the Financial ORM model."""

    def test_tablename(self):
        self.assertEqual(Financial.__tablename__, "financials")

    def test_has_fundamental_columns(self):
        cols = {c.name for c in Financial.__table__.columns}
        expected = [
            "trailing_pe", "price_to_book", "dividend_yield",
            "ev_to_ebitda", "return_on_equity", "debt_to_equity",
            "revenue_growth", "earnings_growth", "market_cap", "current_price",
        ]
        for col in expected:
            self.assertIn(col, cols, f"Missing {col}")

    def test_has_unique_constraint(self):
        constraints = Financial.__table__.constraints
        uq_names = [c.name for c in constraints if hasattr(c, "name") and c.name]
        self.assertIn("uq_financial_date", uq_names)

    def test_instrument_id_not_nullable(self):
        col = Financial.__table__.c.instrument_id
        self.assertFalse(col.nullable)


# =============================================================================
# FactorScore Model
# =============================================================================


class TestDbFactorScoreModel(unittest.TestCase):
    """Tests for the FactorScore ORM model."""

    def test_tablename(self):
        self.assertEqual(FactorScore.__tablename__, "factor_scores")

    def test_has_original_factors(self):
        cols = {c.name for c in FactorScore.__table__.columns}
        for col in ["value_score", "momentum_score", "quality_score", "growth_score"]:
            self.assertIn(col, cols)

    def test_has_v2_factors(self):
        cols = {c.name for c in FactorScore.__table__.columns}
        self.assertIn("volatility_score", cols)
        self.assertIn("technical_score", cols)

    def test_has_composite_scores(self):
        cols = {c.name for c in FactorScore.__table__.columns}
        self.assertIn("composite_score", cols)
        self.assertIn("sector_relative_score", cols)

    def test_has_unique_constraint(self):
        constraints = FactorScore.__table__.constraints
        uq_names = [c.name for c in constraints if hasattr(c, "name") and c.name]
        self.assertIn("uq_score_date", uq_names)


# =============================================================================
# EconomicIndicator Model
# =============================================================================


class TestDbEconomicIndicatorModel(unittest.TestCase):
    """Tests for the EconomicIndicator ORM model."""

    def test_tablename(self):
        self.assertEqual(EconomicIndicator.__tablename__, "economic_indicators")

    def test_has_required_columns(self):
        cols = {c.name for c in EconomicIndicator.__table__.columns}
        for col in ["series_id", "date", "value", "source"]:
            self.assertIn(col, cols)

    def test_series_id_not_nullable(self):
        col = EconomicIndicator.__table__.c.series_id
        self.assertFalse(col.nullable)

    def test_has_unique_constraint(self):
        constraints = EconomicIndicator.__table__.constraints
        uq_names = [c.name for c in constraints if hasattr(c, "name") and c.name]
        self.assertIn("uq_indicator_date", uq_names)


# =============================================================================
# DataQualityLog Model
# =============================================================================


class TestDbDataQualityLogModel(unittest.TestCase):
    """Tests for the DataQualityLog ORM model."""

    def test_tablename(self):
        self.assertEqual(DataQualityLog.__tablename__, "data_quality_logs")

    def test_has_columns(self):
        cols = {c.name for c in DataQualityLog.__table__.columns}
        self.assertIn("id", cols)
        # Should have at least id and some meaningful columns
        self.assertTrue(len(cols) >= 2)


# =============================================================================
# Module Exports
# =============================================================================


class TestDbModuleExports(unittest.TestCase):
    """Tests that the db package exports the correct symbols."""

    def test_exports_base(self):
        from src.db import Base as B
        self.assertIs(B, Base)

    def test_exports_engine_functions(self):
        from src.db import get_async_engine, get_sync_engine
        self.assertTrue(callable(get_async_engine))
        self.assertTrue(callable(get_sync_engine))

    def test_exports_session_factories(self):
        from src.db import AsyncSessionLocal, SyncSessionLocal
        self.assertTrue(callable(AsyncSessionLocal))
        self.assertTrue(callable(SyncSessionLocal))

    def test_exports_models(self):
        from src.db import Instrument, PriceBar, Financial, FactorScore
        self.assertEqual(Instrument.__tablename__, "instruments")
        self.assertEqual(PriceBar.__tablename__, "price_bars")

    def test_exports_economic_indicator(self):
        from src.db import EconomicIndicator
        self.assertEqual(EconomicIndicator.__tablename__, "economic_indicators")

    def test_exports_data_quality_log(self):
        from src.db import DataQualityLog
        self.assertEqual(DataQualityLog.__tablename__, "data_quality_logs")
