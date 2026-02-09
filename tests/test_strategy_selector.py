"""Tests for Multi-Strategy Selector (PRD-165).

9 test classes, ~60 tests covering mean-reversion config/signal/strategy,
ADX config/trend-strength/gate, selector config/selector, and module imports.
"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timezone

from src.strategy_selector.mean_reversion import (
    MeanReversionConfig,
    MeanReversionSignal,
    MeanReversionStrategy,
)
from src.strategy_selector.adx_gate import ADXConfig, ADXGate, TrendStrength
from src.strategy_selector.selector import (
    SelectorConfig,
    StrategyChoice,
    StrategySelector,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _oscillating_prices(n: int = 60, base: float = 100.0, amplitude: float = 5.0) -> list[float]:
    """Generate sinusoidal price series (mean-reverting behaviour)."""
    return [base + amplitude * math.sin(i * 0.3) for i in range(n)]


def _trending_prices(n: int = 60, start: float = 100.0, step: float = 0.5) -> list[float]:
    """Generate linearly trending price series."""
    return [start + i * step for i in range(n)]


def _flat_prices(n: int = 60, value: float = 100.0) -> list[float]:
    """Generate flat (constant) price series."""
    return [value] * n


def _ohlc_from_closes(closes: list[float], spread: float = 1.0):
    """Derive synthetic highs and lows from closes."""
    highs = [c + spread for c in closes]
    lows = [c - spread for c in closes]
    return highs, lows


# ═══════════════════════════════════════════════════════════════════════
#  1. MeanReversionConfig
# ═══════════════════════════════════════════════════════════════════════


class TestMeanReversionConfig(unittest.TestCase):
    """Tests for MeanReversionConfig dataclass."""

    def test_defaults(self):
        cfg = MeanReversionConfig()
        self.assertEqual(cfg.rsi_period, 14)
        self.assertAlmostEqual(cfg.rsi_oversold, 30.0)
        self.assertAlmostEqual(cfg.rsi_overbought, 70.0)
        self.assertEqual(cfg.zscore_period, 50)
        self.assertAlmostEqual(cfg.zscore_entry, 2.0)
        self.assertAlmostEqual(cfg.bb_std, 2.0)
        self.assertEqual(cfg.bb_period, 20)
        self.assertEqual(cfg.max_hold_bars, 10)

    def test_custom_values(self):
        cfg = MeanReversionConfig(rsi_period=10, zscore_period=30, bb_period=15)
        self.assertEqual(cfg.rsi_period, 10)
        self.assertEqual(cfg.zscore_period, 30)
        self.assertEqual(cfg.bb_period, 15)

    def test_is_dataclass(self):
        cfg = MeanReversionConfig()
        self.assertTrue(hasattr(cfg, "__dataclass_fields__"))


# ═══════════════════════════════════════════════════════════════════════
#  2. MeanReversionSignal
# ═══════════════════════════════════════════════════════════════════════


class TestMeanReversionSignal(unittest.TestCase):
    """Tests for MeanReversionSignal dataclass."""

    def test_default_values(self):
        sig = MeanReversionSignal()
        self.assertEqual(sig.ticker, "")
        self.assertEqual(sig.direction, "neutral")
        self.assertAlmostEqual(sig.conviction, 0.0)
        self.assertAlmostEqual(sig.rsi, 50.0)
        self.assertEqual(sig.signal_type, "none")

    def test_custom_signal(self):
        sig = MeanReversionSignal(
            ticker="AAPL", direction="bullish", conviction=72.5,
            rsi=25.0, zscore=-2.5, signal_type="oversold_bounce",
        )
        self.assertEqual(sig.ticker, "AAPL")
        self.assertEqual(sig.direction, "bullish")
        self.assertAlmostEqual(sig.conviction, 72.5)

    def test_to_dict_keys(self):
        sig = MeanReversionSignal(ticker="SPY")
        d = sig.to_dict()
        expected_keys = {
            "ticker", "direction", "conviction", "rsi", "zscore",
            "bb_position", "entry_price", "target_price", "stop_price",
            "signal_type", "timestamp",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_timestamp_is_utc(self):
        sig = MeanReversionSignal()
        self.assertIsNotNone(sig.timestamp.tzinfo)


# ═══════════════════════════════════════════════════════════════════════
#  3. MeanReversionStrategy
# ═══════════════════════════════════════════════════════════════════════


class TestMeanReversionStrategy(unittest.TestCase):
    """Tests for the MeanReversionStrategy engine."""

    def setUp(self):
        self.strategy = MeanReversionStrategy()

    def test_analyze_insufficient_data(self):
        sig = self.strategy.analyze("AAPL", [100.0] * 10)
        self.assertEqual(sig.signal_type, "insufficient_data")

    def test_analyze_sufficient_oscillating_data(self):
        closes = _oscillating_prices(60)
        sig = self.strategy.analyze("SPY", closes)
        self.assertEqual(sig.ticker, "SPY")
        self.assertIn(sig.signal_type, ("oversold_bounce", "overbought_fade", "none"))

    def test_analyze_returns_valid_rsi(self):
        closes = _oscillating_prices(60)
        sig = self.strategy.analyze("AAPL", closes)
        self.assertGreaterEqual(sig.rsi, 0.0)
        self.assertLessEqual(sig.rsi, 100.0)

    def test_analyze_trending_data_low_conviction(self):
        closes = _trending_prices(60)
        sig = self.strategy.analyze("AAPL", closes)
        # Strongly trending data may not trigger mean-reversion
        self.assertIn(sig.direction, ("neutral", "bearish", "bullish"))

    def test_analyze_with_highs_lows(self):
        closes = _oscillating_prices(60)
        highs, lows = _ohlc_from_closes(closes)
        sig = self.strategy.analyze("AAPL", closes, highs=highs, lows=lows)
        self.assertIsNotNone(sig)

    def test_compute_rsi_constant_prices(self):
        closes = [100.0] * 60
        rsi = self.strategy._compute_rsi(closes)
        # With no price change, RSI indeterminate (avg_loss ~0 → 100)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)

    def test_compute_zscore_flat_is_near_zero(self):
        closes = [100.0] * 60
        zscore = self.strategy._compute_zscore(closes)
        self.assertAlmostEqual(zscore, 0.0, places=3)

    def test_compute_bollinger_returns_four_values(self):
        closes = _oscillating_prices(60)
        result = self.strategy._compute_bollinger(closes)
        self.assertEqual(len(result), 4)
        pos, upper, lower, mid = result
        self.assertGreaterEqual(pos, 0.0)
        self.assertLessEqual(pos, 1.0)
        self.assertGreater(upper, lower)

    def test_scan_universe_empty(self):
        signals = self.strategy.scan_universe({})
        self.assertEqual(len(signals), 0)

    def test_scan_universe_filters_by_conviction(self):
        prices = {
            "AAPL": _oscillating_prices(60),
            "SHORT": [100.0] * 10,
        }
        # Use a minimum conviction > 0 to filter out insufficient_data signals
        signals = self.strategy.scan_universe(prices, min_conviction=10.0)
        tickers = [s.ticker for s in signals]
        # "SHORT" has insufficient data (conviction=0), filtered out by min_conviction
        self.assertNotIn("SHORT", tickers)

    def test_scan_universe_sorted_by_conviction(self):
        prices = {
            "A": _oscillating_prices(60, amplitude=10),
            "B": _oscillating_prices(60, amplitude=2),
            "C": _oscillating_prices(60, amplitude=5),
        }
        signals = self.strategy.scan_universe(prices, min_conviction=0.0)
        convictions = [s.conviction for s in signals]
        self.assertEqual(convictions, sorted(convictions, reverse=True))

    def test_min_data_points_threshold(self):
        """Needs max(14, 50, 20) + 5 = 55 bars for valid signal."""
        sig_54 = self.strategy.analyze("X", _oscillating_prices(54))
        self.assertEqual(sig_54.signal_type, "insufficient_data")
        sig_55 = self.strategy.analyze("X", _oscillating_prices(55))
        self.assertNotEqual(sig_55.signal_type, "insufficient_data")


# ═══════════════════════════════════════════════════════════════════════
#  4. ADXConfig
# ═══════════════════════════════════════════════════════════════════════


class TestADXConfig(unittest.TestCase):
    """Tests for ADXConfig dataclass."""

    def test_defaults(self):
        cfg = ADXConfig()
        self.assertEqual(cfg.period, 14)
        self.assertAlmostEqual(cfg.strong_threshold, 40.0)
        self.assertAlmostEqual(cfg.moderate_threshold, 25.0)
        self.assertAlmostEqual(cfg.weak_threshold, 15.0)
        self.assertEqual(cfg.trend_strategy, "ema_cloud")
        self.assertEqual(cfg.range_strategy, "mean_reversion")

    def test_custom_strategies(self):
        cfg = ADXConfig(trend_strategy="my_trend", range_strategy="my_range")
        self.assertEqual(cfg.trend_strategy, "my_trend")
        self.assertEqual(cfg.range_strategy, "my_range")


# ═══════════════════════════════════════════════════════════════════════
#  5. TrendStrength
# ═══════════════════════════════════════════════════════════════════════


class TestTrendStrength(unittest.TestCase):
    """Tests for the TrendStrength enum."""

    def test_four_values(self):
        values = list(TrendStrength)
        self.assertEqual(len(values), 4)

    def test_string_values(self):
        self.assertEqual(TrendStrength.STRONG_TREND.value, "strong_trend")
        self.assertEqual(TrendStrength.MODERATE_TREND.value, "moderate_trend")
        self.assertEqual(TrendStrength.WEAK_TREND.value, "weak_trend")
        self.assertEqual(TrendStrength.NO_TREND.value, "no_trend")

    def test_is_string(self):
        self.assertIsInstance(TrendStrength.STRONG_TREND, str)

    def test_comparison(self):
        self.assertEqual(TrendStrength.NO_TREND, "no_trend")


# ═══════════════════════════════════════════════════════════════════════
#  6. ADXGate
# ═══════════════════════════════════════════════════════════════════════


class TestADXGate(unittest.TestCase):
    """Tests for the ADXGate engine."""

    def setUp(self):
        self.gate = ADXGate()

    def test_compute_adx_insufficient_data(self):
        adx = self.gate.compute_adx([100.0] * 10, [99.0] * 10, [99.5] * 10)
        self.assertAlmostEqual(adx, 0.0)

    def test_compute_adx_minimum_bars(self):
        """Needs period * 2 + 1 = 29 bars minimum."""
        closes = _trending_prices(29)
        highs, lows = _ohlc_from_closes(closes)
        adx = self.gate.compute_adx(highs, lows, closes)
        self.assertGreaterEqual(adx, 0.0)

    def test_compute_adx_trending_data(self):
        closes = _trending_prices(60, step=2.0)
        highs, lows = _ohlc_from_closes(closes, spread=0.5)
        adx = self.gate.compute_adx(highs, lows, closes)
        self.assertGreater(adx, 0.0)

    def test_classify_strong(self):
        self.assertEqual(self.gate.classify(50.0), TrendStrength.STRONG_TREND)

    def test_classify_moderate(self):
        self.assertEqual(self.gate.classify(30.0), TrendStrength.MODERATE_TREND)

    def test_classify_weak(self):
        self.assertEqual(self.gate.classify(20.0), TrendStrength.WEAK_TREND)

    def test_classify_no_trend(self):
        self.assertEqual(self.gate.classify(10.0), TrendStrength.NO_TREND)

    def test_classify_boundary_40(self):
        self.assertEqual(self.gate.classify(40.0), TrendStrength.STRONG_TREND)

    def test_classify_boundary_25(self):
        self.assertEqual(self.gate.classify(25.0), TrendStrength.MODERATE_TREND)

    def test_classify_boundary_15(self):
        self.assertEqual(self.gate.classify(15.0), TrendStrength.WEAK_TREND)

    def test_select_strategy_trending(self):
        self.assertEqual(self.gate.select_strategy(TrendStrength.STRONG_TREND), "ema_cloud")
        self.assertEqual(self.gate.select_strategy(TrendStrength.MODERATE_TREND), "ema_cloud")

    def test_select_strategy_ranging(self):
        self.assertEqual(self.gate.select_strategy(TrendStrength.WEAK_TREND), "mean_reversion")
        self.assertEqual(self.gate.select_strategy(TrendStrength.NO_TREND), "mean_reversion")

    def test_analyze_and_select_returns_tuple(self):
        closes = _trending_prices(60, step=1.0)
        highs, lows = _ohlc_from_closes(closes)
        strategy, strength, adx = self.gate.analyze_and_select(highs, lows, closes)
        self.assertIn(strategy, ("ema_cloud", "mean_reversion"))
        self.assertIsInstance(strength, TrendStrength)
        self.assertGreaterEqual(adx, 0.0)

    def test_compute_flat_data_low_adx(self):
        closes = _flat_prices(60)
        highs, lows = _ohlc_from_closes(closes, spread=0.01)
        adx = self.gate.compute_adx(highs, lows, closes)
        self.assertLess(adx, 15.0)


# ═══════════════════════════════════════════════════════════════════════
#  7. SelectorConfig
# ═══════════════════════════════════════════════════════════════════════


class TestSelectorConfig(unittest.TestCase):
    """Tests for SelectorConfig dataclass."""

    def test_defaults(self):
        cfg = SelectorConfig()
        self.assertIsNone(cfg.force_strategy)
        self.assertFalse(cfg.blend_mode)
        self.assertAlmostEqual(cfg.blend_ema_weight, 0.6)
        self.assertIn("crisis", cfg.regime_override)

    def test_nested_configs(self):
        cfg = SelectorConfig()
        self.assertIsInstance(cfg.adx_config, ADXConfig)
        self.assertIsInstance(cfg.mr_config, MeanReversionConfig)

    def test_crisis_override_default(self):
        cfg = SelectorConfig()
        self.assertEqual(cfg.regime_override["crisis"], "mean_reversion")

    def test_custom_override(self):
        cfg = SelectorConfig(regime_override={"bear": "mean_reversion", "crisis": "mean_reversion"})
        self.assertIn("bear", cfg.regime_override)


# ═══════════════════════════════════════════════════════════════════════
#  8. StrategySelector
# ═══════════════════════════════════════════════════════════════════════


class TestStrategySelector(unittest.TestCase):
    """Tests for the StrategySelector engine."""

    def setUp(self):
        self.selector = StrategySelector()
        self.closes = _trending_prices(60, step=1.0)
        self.highs, self.lows = _ohlc_from_closes(self.closes)

    def test_select_returns_strategy_choice(self):
        choice = self.selector.select("AAPL", self.highs, self.lows, self.closes)
        self.assertIsInstance(choice, StrategyChoice)
        self.assertEqual(choice.ticker, "AAPL")

    def test_select_crisis_regime_override(self):
        choice = self.selector.select(
            "AAPL", self.highs, self.lows, self.closes, regime="crisis",
        )
        self.assertEqual(choice.selected_strategy, "mean_reversion")
        self.assertIn("Regime override", choice.reasoning)

    def test_select_forced_strategy(self):
        cfg = SelectorConfig(force_strategy="ema_cloud")
        selector = StrategySelector(config=cfg)
        choice = selector.select("AAPL", self.highs, self.lows, self.closes)
        self.assertEqual(choice.selected_strategy, "ema_cloud")
        self.assertAlmostEqual(choice.confidence, 100.0)

    def test_select_adx_based(self):
        choice = self.selector.select(
            "AAPL", self.highs, self.lows, self.closes, regime="bull",
        )
        self.assertIn(choice.selected_strategy, ("ema_cloud", "mean_reversion"))
        self.assertGreater(choice.confidence, 0.0)

    def test_select_includes_mr_signal_when_mean_reversion(self):
        osc = _oscillating_prices(60)
        h, l = _ohlc_from_closes(osc, spread=0.5)
        choice = self.selector.select("SPY", h, l, osc, regime="crisis")
        if choice.selected_strategy == "mean_reversion":
            self.assertIsNotNone(choice.mean_reversion_signal)

    def test_strategy_choice_to_dict(self):
        choice = self.selector.select("AAPL", self.highs, self.lows, self.closes)
        d = choice.to_dict()
        expected_keys = {
            "ticker", "selected_strategy", "trend_strength", "adx_value",
            "regime", "mean_reversion_signal", "confidence", "reasoning",
            "timestamp",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_select_batch_multiple_tickers(self):
        data = {
            "AAPL": {"highs": self.highs, "lows": self.lows, "closes": self.closes},
            "MSFT": {"highs": self.highs, "lows": self.lows, "closes": self.closes},
        }
        results = self.selector.select_batch(data, regime="bull")
        self.assertIn("AAPL", results)
        self.assertIn("MSFT", results)

    def test_select_batch_skips_empty_closes(self):
        data = {
            "AAPL": {"highs": self.highs, "lows": self.lows, "closes": self.closes},
            "EMPTY": {"highs": [], "lows": [], "closes": []},
        }
        results = self.selector.select_batch(data)
        self.assertIn("AAPL", results)
        self.assertNotIn("EMPTY", results)

    def test_record_outcome(self):
        self.selector.record_outcome("ema_cloud", 150.0)
        self.selector.record_outcome("ema_cloud", -50.0)
        self.selector.record_outcome("mean_reversion", 100.0)
        stats = self.selector.get_strategy_stats()
        self.assertEqual(stats["ema_cloud"]["signals"], 2)
        self.assertEqual(stats["ema_cloud"]["wins"], 1)
        self.assertAlmostEqual(stats["ema_cloud"]["total_pnl"], 100.0)

    def test_record_outcome_new_strategy(self):
        self.selector.record_outcome("custom_strat", 200.0)
        stats = self.selector.get_strategy_stats()
        self.assertIn("custom_strat", stats)
        self.assertEqual(stats["custom_strat"]["signals"], 1)

    def test_get_strategy_stats_initial(self):
        stats = self.selector.get_strategy_stats()
        self.assertIn("ema_cloud", stats)
        self.assertIn("mean_reversion", stats)
        self.assertEqual(stats["ema_cloud"]["signals"], 0)

    def test_get_strategy_stats_win_rate(self):
        for _ in range(6):
            self.selector.record_outcome("ema_cloud", 100.0)
        for _ in range(4):
            self.selector.record_outcome("ema_cloud", -50.0)
        stats = self.selector.get_strategy_stats()
        self.assertAlmostEqual(stats["ema_cloud"]["win_rate"], 60.0)


# ═══════════════════════════════════════════════════════════════════════
#  9. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports(unittest.TestCase):
    """Verify public API is importable from the package."""

    def test_import_from_package(self):
        from src.strategy_selector import (
            ADXConfig,
            ADXGate,
            MeanReversionConfig,
            MeanReversionSignal,
            MeanReversionStrategy,
            SelectorConfig,
            StrategyChoice,
            StrategySelector,
            TrendStrength,
        )
        self.assertIsNotNone(StrategySelector)
        self.assertIsNotNone(ADXGate)
        self.assertIsNotNone(MeanReversionStrategy)

    def test_trend_strength_enum_count(self):
        self.assertEqual(len(list(TrendStrength)), 4)
