"""Tests for TradingView Scanner integration.

All tests mock tvscreener to avoid network calls.
"""

import math
import os
import sys
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tv_scanner.config import AssetClass, TVScanCategory, TVScannerConfig, TVTimeInterval
from src.tv_scanner.models import TVFieldSpec, TVFilterCriterion, TVPreset, TVScanResult, TVScanReport
from src.tv_scanner.presets import (
    PRESET_TV_SCANS, get_tv_preset, get_tv_presets_by_category, get_all_tv_presets,
)
from src.tv_scanner.engine import TVScannerEngine, _safe_float
from src.tv_scanner.bridge import TVDataBridge


# ── Helpers ─────────────────────────────────────────────────────────

def _make_mock_dataframe(rows=3):
    """Build a sample DataFrame mimicking tvscreener output."""
    data = []
    symbols = ["AAPL", "NVDA", "MSFT", "TSLA", "AMZN"]
    for i in range(rows):
        sym = symbols[i % len(symbols)]
        data.append({
            "symbol": sym,
            "name": f"{sym} Inc.",
            "close": 150.0 + i * 10,
            "change": 2.5 + i * 0.5,
            "volume": 1_000_000 + i * 500_000,
            "relative_volume_10d_calc": 1.5 + i * 0.3,
            "RSI": 55.0 + i * 5,
            "MACD.macd": 0.5 + i * 0.1,
            "MACD.signal": 0.3 + i * 0.05,
            "SMA20": 145.0 + i * 8,
            "SMA50": 140.0 + i * 7,
            "SMA200": 130.0 + i * 5,
            "Recommend.All": 0.3 + i * 0.1,
            "market_cap_basic": 2e12 + i * 1e11,
            "price_earnings_ttm": 20.0 + i * 2,
            "dividend_yield_recent": 1.5 + i * 0.2,
            "sector": "Technology",
            "Perf.W": 3.0 + i,
            "Perf.1M": 8.0 + i * 2,
            "Perf.Y": 25.0 + i * 5,
        })
    return pd.DataFrame(data)


def _build_mock_tvscreener():
    """Create a mock tvscreener module with StockScreener, StockField, etc."""
    mock_tvs = MagicMock()

    # Mock screener instance
    mock_screener = MagicMock()
    mock_screener.select.return_value = mock_screener
    mock_screener.where.return_value = mock_screener
    mock_screener.sort_by.return_value = mock_screener
    mock_screener.get.return_value = _make_mock_dataframe()

    mock_tvs.StockScreener.return_value = mock_screener
    mock_tvs.CryptoScreener.return_value = mock_screener
    mock_tvs.ForexScreener.return_value = mock_screener
    mock_tvs.BondScreener.return_value = mock_screener
    mock_tvs.FuturesScreener.return_value = mock_screener
    mock_tvs.CoinScreener.return_value = mock_screener

    # Mock field enums — MagicMock already returns a MagicMock for any attribute
    # access, which supports comparison operators and chaining. We just need to
    # make sure search() works.
    for cls_name in ["StockField", "CryptoField", "ForexField", "BondField", "FuturesField", "CoinField"]:
        field_cls = MagicMock()
        field_cls.search.return_value = ["RSI", "RSI7"]
        setattr(mock_tvs, cls_name, field_cls)

    return mock_tvs


# ── TVFilterCriterion Tests ─────────────────────────────────────────

class TestTVFilterCriterion(unittest.TestCase):
    """Test filter criterion model."""

    def test_describe_gt(self):
        c = TVFilterCriterion("RSI", "gt", 50)
        self.assertIn(">", c.describe())
        self.assertIn("50", c.describe())

    def test_describe_between(self):
        c = TVFilterCriterion("close", "between", 10, 100)
        desc = c.describe()
        self.assertIn("between", desc)
        self.assertIn("10", desc)
        self.assertIn("100", desc)

    def test_describe_isin(self):
        c = TVFilterCriterion("sector", "isin", ["Tech", "Health"])
        desc = c.describe()
        self.assertIn("in", desc)

    def test_describe_lte(self):
        c = TVFilterCriterion("price_earnings_ttm", "lte", 25)
        self.assertIn("<=", c.describe())

    def test_describe_eq(self):
        c = TVFilterCriterion("sector", "eq", "Technology")
        self.assertIn("==", c.describe())


# ── TVPreset Tests ──────────────────────────────────────────────────

class TestTVPreset(unittest.TestCase):
    """Test preset model."""

    def test_creation_defaults(self):
        p = TVPreset(
            name="test",
            description="Test preset",
            category=TVScanCategory.MOMENTUM,
        )
        self.assertEqual(p.name, "test")
        self.assertEqual(p.asset_class, AssetClass.STOCK)
        self.assertEqual(p.max_results, 150)
        self.assertEqual(p.select_fields, [])
        self.assertEqual(p.criteria, [])

    def test_custom_fields(self):
        p = TVPreset(
            name="custom",
            description="Custom",
            category=TVScanCategory.TECHNICAL,
            select_fields=[TVFieldSpec("RSI"), TVFieldSpec("SMA50")],
            criteria=[TVFilterCriterion("RSI", "gt", 50)],
        )
        self.assertEqual(len(p.select_fields), 2)
        self.assertEqual(len(p.criteria), 1)


# ── TVScanResult Tests ──────────────────────────────────────────────

class TestTVScanResult(unittest.TestCase):
    """Test scan result model."""

    def test_defaults(self):
        r = TVScanResult(symbol="AAPL")
        self.assertEqual(r.symbol, "AAPL")
        self.assertIsNone(r.price)
        self.assertIsNone(r.rsi)
        self.assertEqual(r.signal_strength, 0.0)
        self.assertEqual(r.data_source, "tradingview")

    def test_with_values(self):
        r = TVScanResult(
            symbol="NVDA",
            price=800.0,
            change_pct=5.5,
            rsi=65.0,
            signal_strength=72.5,
        )
        self.assertEqual(r.price, 800.0)
        self.assertEqual(r.signal_strength, 72.5)

    def test_raw_data_default(self):
        r = TVScanResult(symbol="X")
        self.assertEqual(r.raw_data, {})


# ── TVScannerEngine Tests ──────────────────────────────────────────

class TestTVScannerEngine(unittest.TestCase):
    """Test the core scanner engine with mocked tvscreener."""

    def setUp(self):
        self.engine = TVScannerEngine()
        self.mock_tvs = _build_mock_tvscreener()

    def test_init_default_config(self):
        self.assertEqual(self.engine.config.max_results, 150)
        self.assertEqual(self.engine.config.default_asset_class, AssetClass.STOCK)

    def test_init_custom_config(self):
        cfg = TVScannerConfig(max_results=50, cache_ttl_seconds=60)
        engine = TVScannerEngine(config=cfg)
        self.assertEqual(engine.config.max_results, 50)

    def test_run_preset_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.engine.run_preset("nonexistent_preset")

    @patch.dict("sys.modules", {"tvscreener": None})
    def test_run_scan_import_error(self):
        """When tvscreener is not installed, report should contain error."""
        # Force ImportError by making import raise
        preset = TVPreset(
            name="test",
            description="Test",
            category=TVScanCategory.MOMENTUM,
        )
        report = self.engine.run_scan(preset)
        self.assertIsNotNone(report.error)

    def test_run_scan_with_mock(self):
        """Run scan with fully mocked tvscreener."""
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            report = self.engine.run_preset("momentum_breakout")

        self.assertIsNone(report.error)
        self.assertEqual(report.preset_name, "momentum_breakout")
        self.assertGreater(report.total_results, 0)
        self.assertGreater(report.execution_time_ms, 0)

        first = report.results[0]
        self.assertEqual(first.symbol, "AAPL")
        self.assertIsNotNone(first.price)
        self.assertEqual(first.data_source, "tradingview")

    def test_signal_strength_computation(self):
        """Signal strength should be 0-100 based on indicators."""
        r = TVScanResult(
            symbol="TEST",
            tv_rating=0.8,       # Strong buy → high score
            rsi=75.0,            # Overbought → decent RSI deviation
            relative_volume=2.5, # High → decent volume score
            change_pct=5.0,      # Good momentum
        )
        strength = self.engine._compute_signal_strength(r)
        self.assertGreater(strength, 0)
        self.assertLessEqual(strength, 100)

    def test_signal_strength_all_none(self):
        """Signal strength with no indicators should be 0."""
        r = TVScanResult(symbol="EMPTY")
        strength = self.engine._compute_signal_strength(r)
        self.assertEqual(strength, 0.0)

    def test_cache_behavior(self):
        """Second call should return cached result."""
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            report1 = self.engine.run_preset("rsi_oversold")
            report2 = self.engine.run_preset("rsi_oversold")

        self.assertEqual(report1.total_results, report2.total_results)

    def test_clear_cache(self):
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            self.engine.run_preset("rsi_oversold")
            self.assertEqual(len(self.engine._cache), 1)
            self.engine.clear_cache()
            self.assertEqual(len(self.engine._cache), 0)

    def test_search_fields(self):
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            results = self.engine.search_fields("rsi")
        self.assertIsInstance(results, list)

    def test_custom_scan(self):
        """Custom scan builds a TVPreset on the fly."""
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            criteria = [TVFilterCriterion("RSI", "lt", 30)]
            report = self.engine.run_custom_scan(criteria, select_fields=["close", "RSI"])
        self.assertEqual(report.preset_name, "custom_scan")
        self.assertIsNone(report.error)

    def test_run_scan_crypto_asset_class(self):
        """Crypto preset should use CryptoScreener."""
        with patch.dict("sys.modules", {"tvscreener": self.mock_tvs}):
            report = self.engine.run_preset("crypto_momentum")
        self.assertIsNone(report.error)
        self.mock_tvs.CryptoScreener.assert_called()


# ── Preset Registry Tests ──────────────────────────────────────────

class TestTVPresets(unittest.TestCase):
    """Test preset registry completeness."""

    def test_minimum_presets(self):
        self.assertGreaterEqual(len(PRESET_TV_SCANS), 12)

    def test_all_presets_have_names(self):
        for pid, preset in PRESET_TV_SCANS.items():
            self.assertEqual(pid, preset.name)
            self.assertTrue(len(preset.description) > 5)

    def test_all_presets_have_criteria(self):
        for preset in PRESET_TV_SCANS.values():
            self.assertGreater(len(preset.criteria), 0, f"Preset {preset.name} has no criteria")

    def test_get_by_category(self):
        momentum = get_tv_presets_by_category(TVScanCategory.MOMENTUM)
        self.assertGreater(len(momentum), 0)
        for p in momentum:
            self.assertEqual(p.category, TVScanCategory.MOMENTUM)

    def test_get_all(self):
        all_presets = get_all_tv_presets()
        self.assertEqual(len(all_presets), len(PRESET_TV_SCANS))

    def test_crypto_uses_crypto_asset(self):
        crypto = get_tv_presets_by_category(TVScanCategory.CRYPTO)
        for p in crypto:
            self.assertEqual(p.asset_class, AssetClass.CRYPTO)

    def test_get_preset_not_found(self):
        with self.assertRaises(KeyError):
            get_tv_preset("this_does_not_exist")

    def test_get_preset_found(self):
        p = get_tv_preset("momentum_breakout")
        self.assertEqual(p.name, "momentum_breakout")


# ── TVDataBridge Tests ──────────────────────────────────────────────

class TestTVDataBridge(unittest.TestCase):
    """Test cross-module data adapters."""

    def setUp(self):
        self.report = TVScanReport(
            preset_name="test",
            total_results=2,
            results=[
                TVScanResult(
                    symbol="AAPL",
                    company_name="Apple Inc.",
                    price=185.0,
                    change_pct=2.5,
                    volume=50_000_000,
                    relative_volume=1.8,
                    rsi=62.0,
                    market_cap=2.8e12,
                    sector="Technology",
                    signal_strength=65.0,
                ),
                TVScanResult(
                    symbol="NVDA",
                    company_name="NVIDIA Corp.",
                    price=800.0,
                    change_pct=5.0,
                    volume=60_000_000,
                    rsi=72.0,
                    market_cap=2.0e12,
                    sector="Technology",
                    signal_strength=80.0,
                ),
            ],
        )

    def test_to_scanner_format(self):
        data = TVDataBridge.to_scanner_format(self.report)
        self.assertIn("AAPL", data)
        self.assertIn("NVDA", data)
        self.assertEqual(data["AAPL"]["price"], 185.0)
        self.assertEqual(data["AAPL"]["signal_strength"], 65.0)

    def test_to_screener_format(self):
        data = TVDataBridge.to_screener_format(self.report)
        self.assertIn("AAPL", data)
        self.assertEqual(data["AAPL"]["symbol"], "AAPL")
        self.assertEqual(data["AAPL"]["pe_ratio"], None)
        self.assertEqual(data["NVDA"]["rsi"], 72.0)

    def test_to_ema_scan_list(self):
        symbols = TVDataBridge.to_ema_scan_list(self.report)
        self.assertEqual(symbols, ["AAPL", "NVDA"])

    def test_empty_report(self):
        empty = TVScanReport(preset_name="empty")
        self.assertEqual(TVDataBridge.to_scanner_format(empty), {})
        self.assertEqual(TVDataBridge.to_screener_format(empty), {})
        self.assertEqual(TVDataBridge.to_ema_scan_list(empty), [])


# ── _safe_float Tests ───────────────────────────────────────────────

class TestSafeFloat(unittest.TestCase):
    """Test NaN-safe float conversion."""

    def test_none(self):
        self.assertIsNone(_safe_float(None))

    def test_valid_float(self):
        self.assertEqual(_safe_float(42.5), 42.5)

    def test_valid_int(self):
        self.assertEqual(_safe_float(10), 10.0)

    def test_nan(self):
        self.assertIsNone(_safe_float(float("nan")))

    def test_string_non_numeric(self):
        self.assertIsNone(_safe_float("hello"))

    def test_zero(self):
        self.assertEqual(_safe_float(0), 0.0)

    def test_negative(self):
        self.assertEqual(_safe_float(-3.14), -3.14)

    def test_string_numeric(self):
        self.assertEqual(_safe_float("42.5"), 42.5)


# ── Module Import Tests ────────────────────────────────────────────

class TestTvScannerModuleImports(unittest.TestCase):
    """Verify all public symbols are importable."""

    def test_import_all(self):
        from src.tv_scanner import (
            AssetClass, TVFieldCategory, TVScanCategory, TVScannerConfig,
            TVTimeInterval, TV_FIELD_MAP,
            TVFieldSpec, TVFilterCriterion, TVPreset, TVScanReport, TVScanResult,
            PRESET_TV_SCANS, get_all_tv_presets, get_tv_preset, get_tv_presets_by_category,
            TVScannerEngine, TVDataBridge,
        )
        self.assertTrue(callable(TVScannerEngine))
        self.assertIsInstance(PRESET_TV_SCANS, dict)

    def test_config_enums(self):
        self.assertEqual(AssetClass.STOCK.value, "stock")
        self.assertEqual(TVScanCategory.MOMENTUM.value, "momentum")
        self.assertEqual(TVTimeInterval.HOUR_1.value, "60")


if __name__ == "__main__":
    unittest.main()
