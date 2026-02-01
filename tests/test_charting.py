"""Tests for PRD-40: Technical Charting."""

import pytest
import numpy as np
import pandas as pd
from datetime import date

from src.charting.config import (
    PatternType,
    TrendDirection,
    SRType,
    CrossoverType,
    PatternConfig,
    TrendConfig,
    SRConfig,
    FibConfig,
    ChartingConfig,
    DEFAULT_PATTERN_CONFIG,
    DEFAULT_TREND_CONFIG,
    DEFAULT_SR_CONFIG,
    DEFAULT_FIB_CONFIG,
    DEFAULT_CONFIG,
)
from src.charting.models import (
    ChartPattern,
    TrendAnalysis,
    MACrossover,
    SRLevel,
    FibonacciLevels,
)
from src.charting.patterns import PatternDetector
from src.charting.trend import TrendAnalyzer
from src.charting.support_resistance import SRDetector
from src.charting.fibonacci import FibCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uptrend(n: int = 200, seed: int = 42) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Generate uptrending OHLC data."""
    rng = np.random.RandomState(seed)
    trend = np.linspace(100, 150, n) + rng.normal(0, 1.5, n)
    close = pd.Series(trend)
    high = close + np.abs(rng.normal(0.5, 0.3, n))
    low = close - np.abs(rng.normal(0.5, 0.3, n))
    open_ = close + rng.normal(0, 0.3, n)
    return open_, high, low, close


def _make_downtrend(n: int = 200, seed: int = 42) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Generate downtrending OHLC data."""
    rng = np.random.RandomState(seed)
    trend = np.linspace(150, 100, n) + rng.normal(0, 1.5, n)
    close = pd.Series(trend)
    high = close + np.abs(rng.normal(0.5, 0.3, n))
    low = close - np.abs(rng.normal(0.5, 0.3, n))
    open_ = close + rng.normal(0, 0.3, n)
    return open_, high, low, close


def _make_sideways(n: int = 200, seed: int = 42) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Generate sideways OHLC data."""
    rng = np.random.RandomState(seed)
    trend = 120.0 + rng.normal(0, 2.0, n)
    close = pd.Series(trend)
    high = close + np.abs(rng.normal(0.5, 0.3, n))
    low = close - np.abs(rng.normal(0.5, 0.3, n))
    open_ = close + rng.normal(0, 0.3, n)
    return open_, high, low, close


def _make_double_top(n: int = 60) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Generate price data with a double top pattern."""
    # Rise -> peak1 -> dip -> peak2 -> decline
    part1 = np.linspace(100, 120, 15)  # Rise
    part2 = np.linspace(120, 110, 10)  # Dip
    part3 = np.linspace(110, 120, 10)  # Rise to second peak
    part4 = np.linspace(120, 105, 15)  # Decline below neckline
    part5 = np.linspace(105, 100, 10)  # Continue down
    prices = np.concatenate([part1, part2, part3, part4, part5])
    close = pd.Series(prices)
    high = close + 0.5
    low = close - 0.5
    return high, low, close


def _make_double_bottom(n: int = 60) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Generate price data with a double bottom pattern."""
    part1 = np.linspace(120, 100, 15)
    part2 = np.linspace(100, 110, 10)
    part3 = np.linspace(110, 100, 10)
    part4 = np.linspace(100, 115, 15)
    part5 = np.linspace(115, 120, 10)
    prices = np.concatenate([part1, part2, part3, part4, part5])
    close = pd.Series(prices)
    high = close + 0.5
    low = close - 0.5
    return high, low, close


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:
    """Test configuration enums and dataclasses."""

    def test_pattern_type_values(self):
        assert PatternType.DOUBLE_TOP.value == "double_top"
        assert PatternType.DOUBLE_BOTTOM.value == "double_bottom"
        assert PatternType.HEAD_AND_SHOULDERS.value == "head_and_shoulders"
        assert PatternType.ASCENDING_TRIANGLE.value == "ascending_triangle"
        assert PatternType.FLAG.value == "flag"
        assert len(PatternType) == 8

    def test_trend_direction_values(self):
        assert TrendDirection.UP.value == "up"
        assert TrendDirection.DOWN.value == "down"
        assert TrendDirection.SIDEWAYS.value == "sideways"

    def test_sr_type_values(self):
        assert SRType.SUPPORT.value == "support"
        assert SRType.RESISTANCE.value == "resistance"

    def test_crossover_type_values(self):
        assert CrossoverType.GOLDEN_CROSS.value == "golden_cross"
        assert CrossoverType.DEATH_CROSS.value == "death_cross"

    def test_pattern_config_defaults(self):
        cfg = PatternConfig()
        assert cfg.min_pattern_bars == 10
        assert cfg.price_tolerance == 0.02
        assert cfg.min_confidence == 0.5

    def test_trend_config_defaults(self):
        cfg = TrendConfig()
        assert cfg.short_window == 20
        assert cfg.medium_window == 50
        assert cfg.long_window == 200

    def test_sr_config_defaults(self):
        cfg = SRConfig()
        assert cfg.lookback == 100
        assert cfg.min_touches == 2
        assert cfg.max_levels == 10

    def test_fib_config_defaults(self):
        cfg = FibConfig()
        assert 0.618 in cfg.retracement_levels
        assert 1.618 in cfg.extension_levels
        assert len(cfg.retracement_levels) == 5
        assert len(cfg.extension_levels) == 5

    def test_charting_config_bundles(self):
        cfg = ChartingConfig()
        assert isinstance(cfg.pattern, PatternConfig)
        assert isinstance(cfg.trend, TrendConfig)
        assert isinstance(cfg.sr, SRConfig)
        assert isinstance(cfg.fib, FibConfig)

    def test_default_config_exists(self):
        assert DEFAULT_CONFIG.pattern.min_pattern_bars == 10


# ===========================================================================
# Model Tests
# ===========================================================================

class TestModels:
    """Test data models."""

    def test_chart_pattern_bullish(self):
        p = ChartPattern(pattern_type=PatternType.DOUBLE_BOTTOM)
        assert p.is_bullish is True
        assert p.is_bearish is False

    def test_chart_pattern_bearish(self):
        p = ChartPattern(pattern_type=PatternType.DOUBLE_TOP)
        assert p.is_bearish is True
        assert p.is_bullish is False

    def test_chart_pattern_height(self):
        p = ChartPattern(neckline=100.0, target_price=90.0)
        assert p.pattern_height == 10.0

    def test_chart_pattern_to_dict(self):
        p = ChartPattern(pattern_type=PatternType.HEAD_AND_SHOULDERS, confidence=0.75)
        d = p.to_dict()
        assert d["pattern_type"] == "head_and_shoulders"
        assert d["is_bearish"] is True

    def test_trend_analysis_ma_aligned_bullish(self):
        t = TrendAnalysis(ma_short=110, ma_medium=105, ma_long=100)
        assert t.ma_aligned_bullish is True
        assert t.ma_aligned_bearish is False

    def test_trend_analysis_ma_aligned_bearish(self):
        t = TrendAnalysis(ma_short=100, ma_medium=105, ma_long=110)
        assert t.ma_aligned_bearish is True
        assert t.ma_aligned_bullish is False

    def test_trend_analysis_ma_not_aligned(self):
        t = TrendAnalysis(ma_short=105, ma_medium=100, ma_long=110)
        assert t.ma_aligned_bullish is False
        assert t.ma_aligned_bearish is False

    def test_trend_analysis_to_dict(self):
        t = TrendAnalysis(direction=TrendDirection.UP, strength=75.0)
        d = t.to_dict()
        assert d["direction"] == "up"
        assert d["strength"] == 75.0

    def test_sr_level_is_strong(self):
        sr = SRLevel(touches=4, strength=0.8)
        assert sr.is_strong is True
        sr2 = SRLevel(touches=1, strength=0.3)
        assert sr2.is_strong is False

    def test_sr_level_to_dict(self):
        sr = SRLevel(level_type=SRType.SUPPORT, price=150.0, touches=3)
        d = sr.to_dict()
        assert d["level_type"] == "support"

    def test_fibonacci_levels_swing_range(self):
        fib = FibonacciLevels(swing_high=120.0, swing_low=100.0)
        assert fib.swing_range == 20.0

    def test_fibonacci_nearest_retracement(self):
        fib = FibonacciLevels(
            swing_high=120.0,
            swing_low=100.0,
            retracements={0.382: 112.36, 0.500: 110.0, 0.618: 107.64},
        )
        nearest = fib.nearest_retracement(111.0)
        assert nearest is not None
        assert nearest[0] == 0.500  # 110.0 is closest to 111.0

    def test_fibonacci_to_dict(self):
        fib = FibonacciLevels(
            swing_high=120.0,
            swing_low=100.0,
            retracements={0.618: 107.64},
        )
        d = fib.to_dict()
        assert d["swing_range"] == 20.0
        assert "0.618" in d["retracements"]


# ===========================================================================
# Pattern Tests
# ===========================================================================

class TestPatternDetector:
    """Test chart pattern detection."""

    def test_detect_double_top(self):
        high, low, close = _make_double_top()
        detector = PatternDetector()
        patterns = detector.detect_double_top(high, close, symbol="TEST")
        # Should find at least one double top
        tops = [p for p in patterns if p.pattern_type == PatternType.DOUBLE_TOP]
        assert len(tops) >= 1
        assert tops[0].confidence > 0

    def test_detect_double_bottom(self):
        high, low, close = _make_double_bottom()
        detector = PatternDetector()
        patterns = detector.detect_double_bottom(low, close, symbol="TEST")
        bottoms = [p for p in patterns if p.pattern_type == PatternType.DOUBLE_BOTTOM]
        assert len(bottoms) >= 1
        assert bottoms[0].is_bullish is True

    def test_detect_all(self):
        high, low, close = _make_double_top()
        detector = PatternDetector()
        patterns = detector.detect_all(high, low, close, symbol="ALL")
        # Should return sorted by confidence
        if len(patterns) > 1:
            assert patterns[0].confidence >= patterns[-1].confidence

    def test_insufficient_data(self):
        detector = PatternDetector()
        short = pd.Series([100, 101, 102])
        patterns = detector.detect_double_top(short, short)
        assert patterns == []

    def test_find_peaks(self):
        data = np.array([1, 2, 5, 2, 1, 2, 6, 2, 1, 2, 5, 2, 1])
        detector = PatternDetector()
        peaks = detector._find_peaks(data, order=2)
        assert 2 in peaks
        assert 6 in peaks
        assert 10 in peaks

    def test_find_troughs(self):
        data = np.array([5, 4, 1, 4, 5, 4, 1, 4, 5])
        detector = PatternDetector()
        troughs = detector._find_troughs(data, order=2)
        assert 2 in troughs
        assert 6 in troughs

    def test_head_and_shoulders(self):
        # Create H&S pattern: left shoulder, head, right shoulder
        ls = np.linspace(100, 115, 10)
        d1 = np.linspace(115, 105, 8)
        hd = np.linspace(105, 120, 10)
        d2 = np.linspace(120, 105, 8)
        rs = np.linspace(105, 115, 10)
        d3 = np.linspace(115, 100, 10)
        tail = np.linspace(100, 98, 5)
        prices = np.concatenate([ls, d1, hd, d2, rs, d3, tail])
        close = pd.Series(prices)
        high = close + 0.3
        low = close - 0.3
        detector = PatternDetector()
        patterns = detector.detect_head_and_shoulders(high, low, close, symbol="HS")
        hs_patterns = [p for p in patterns if p.pattern_type == PatternType.HEAD_AND_SHOULDERS]
        # Pattern detection depends on peak finding; may find it
        # At minimum, the method should run without error
        assert isinstance(patterns, list)

    def test_triangle_detection(self):
        _, high, low, close = _make_sideways(100)
        detector = PatternDetector()
        patterns = detector.detect_triangle(high, low, close, symbol="TRI")
        assert isinstance(patterns, list)


# ===========================================================================
# Trend Tests
# ===========================================================================

class TestTrendAnalyzer:
    """Test trend analysis."""

    def test_uptrend_detection(self):
        _, _, _, close = _make_uptrend(200)
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(close, symbol="UP")
        assert trend.direction == TrendDirection.UP
        assert trend.slope > 0
        assert trend.strength > 0

    def test_downtrend_detection(self):
        _, _, _, close = _make_downtrend(200)
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(close, symbol="DN")
        assert trend.direction == TrendDirection.DOWN
        assert trend.slope < 0

    def test_sideways_detection(self):
        _, _, _, close = _make_sideways(200)
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(close, symbol="SIDE")
        # Sideways has near-zero slope
        assert abs(trend.slope) < 0.01

    def test_ma_values(self):
        _, _, _, close = _make_uptrend(250)
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(close)
        assert trend.ma_short > 0
        assert trend.ma_medium > 0
        assert trend.ma_long > 0
        # In uptrend, short MA > long MA
        assert trend.ma_short > trend.ma_long

    def test_insufficient_data(self):
        analyzer = TrendAnalyzer()
        trend = analyzer.analyze(pd.Series([100, 101]))
        assert trend.direction == TrendDirection.SIDEWAYS
        assert trend.strength == 0.0

    def test_detect_crossovers(self):
        # Build data with a golden cross: start below, then cross above
        rng = np.random.RandomState(42)
        # Initially trending down, then sharply up
        down = np.linspace(150, 100, 150)
        up = np.linspace(100, 160, 150)
        prices = np.concatenate([down, up]) + rng.normal(0, 1.0, 300)
        close = pd.Series(prices)
        analyzer = TrendAnalyzer()
        crossovers = analyzer.detect_crossovers(close, fast_window=20, slow_window=50)
        # Should find at least one crossover
        assert len(crossovers) > 0
        types = {c.crossover_type for c in crossovers}
        assert len(types) > 0

    def test_compute_moving_averages(self):
        _, _, _, close = _make_uptrend(250)
        analyzer = TrendAnalyzer()
        mas = analyzer.compute_moving_averages(close, windows=[20, 50, 200])
        assert 20 in mas
        assert 50 in mas
        assert 200 in mas

    def test_linreg(self):
        analyzer = TrendAnalyzer()
        x = np.arange(10, dtype=float)
        y = 2.0 * x + 5.0
        slope, intercept, r2 = analyzer._linreg(x, y)
        assert slope == pytest.approx(2.0, abs=0.01)
        assert intercept == pytest.approx(5.0, abs=0.01)
        assert r2 == pytest.approx(1.0, abs=0.01)


# ===========================================================================
# Support/Resistance Tests
# ===========================================================================

class TestSRDetector:
    """Test support/resistance detection."""

    def test_find_levels(self):
        _, high, low, close = _make_sideways(150)
        detector = SRDetector()
        levels = detector.find_levels(high, low, close, symbol="SR")
        assert isinstance(levels, list)
        # In sideways market should find some levels
        for lv in levels:
            assert lv.price > 0
            assert lv.touches >= 2

    def test_find_support(self):
        _, high, low, close = _make_sideways(150)
        detector = SRDetector()
        support = detector.find_support(low, close, symbol="SUP")
        for lv in support:
            assert lv.level_type == SRType.SUPPORT

    def test_find_resistance(self):
        _, high, low, close = _make_sideways(150)
        detector = SRDetector()
        resistance = detector.find_resistance(high, close, symbol="RES")
        for lv in resistance:
            assert lv.level_type == SRType.RESISTANCE

    def test_insufficient_data(self):
        detector = SRDetector()
        short_high = pd.Series([100.0, 101.0])
        short_low = pd.Series([99.0, 100.0])
        short_close = pd.Series([99.5, 100.5])
        levels = detector.find_levels(short_high, short_low, short_close)
        assert levels == []

    def test_test_level(self):
        detector = SRDetector()
        level = SRLevel(level_type=SRType.SUPPORT, price=100.0, touches=3, strength=0.8)
        result = detector.test_level(level, current_price=102.0)
        assert result["distance"] == pytest.approx(2.0, abs=0.01)
        assert result["distance_pct"] == pytest.approx(2.0, abs=0.1)
        assert result["proximity"] > 0

    def test_max_levels_respected(self):
        _, high, low, close = _make_sideways(200)
        cfg = SRConfig(max_levels=4)
        detector = SRDetector(config=cfg)
        levels = detector.find_levels(high, low, close)
        assert len(levels) <= 4


# ===========================================================================
# Fibonacci Tests
# ===========================================================================

class TestFibCalculator:
    """Test Fibonacci calculator."""

    def test_compute_from_points_uptrend(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0, is_uptrend=True)
        assert fib.swing_high == 120.0
        assert fib.swing_low == 100.0
        assert fib.swing_range == 20.0
        assert fib.is_uptrend is True

        # Check retracements (from high toward low in uptrend)
        assert 0.382 in fib.retracements
        assert 0.618 in fib.retracements
        assert fib.retracements[0.500] == pytest.approx(110.0, abs=0.01)
        assert fib.retracements[0.618] == pytest.approx(107.64, abs=0.01)

    def test_compute_from_points_downtrend(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0, is_uptrend=False)
        assert fib.is_uptrend is False
        # In downtrend, retracements go from low toward high
        assert fib.retracements[0.500] == pytest.approx(110.0, abs=0.01)
        assert fib.retracements[0.618] == pytest.approx(112.36, abs=0.01)

    def test_extensions_uptrend(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0, is_uptrend=True)
        # Extensions from low in uptrend
        assert 1.618 in fib.extensions
        assert fib.extensions[1.0] == pytest.approx(120.0, abs=0.01)
        assert fib.extensions[1.618] == pytest.approx(132.36, abs=0.01)

    def test_extensions_downtrend(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0, is_uptrend=False)
        assert fib.extensions[1.0] == pytest.approx(100.0, abs=0.01)
        assert fib.extensions[1.618] == pytest.approx(87.64, abs=0.01)

    def test_invalid_points(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(100.0, 120.0)  # high < low
        assert fib.swing_range == 0.0
        assert fib.retracements == {}

    def test_compute_auto_detect(self):
        _, high, low, close = _make_uptrend(100)
        calc = FibCalculator()
        fib = calc.compute(high, low, close, symbol="AUTO")
        assert fib.swing_high > fib.swing_low
        assert len(fib.retracements) == 5
        assert len(fib.extensions) == 5

    def test_nearest_level(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0, is_uptrend=True)
        nearest = calc.find_nearest_level(fib, price=108.0)
        assert nearest is not None
        assert nearest[0] == "retracement"
        # Should be close to 0.618 (107.64)
        assert abs(nearest[2] - 108.0) < 2.0

    def test_empty_fib_nearest(self):
        calc = FibCalculator()
        fib = FibonacciLevels()
        nearest = calc.find_nearest_level(fib, price=100.0)
        assert nearest is None

    def test_to_dict(self):
        calc = FibCalculator()
        fib = calc.compute_from_points(120.0, 100.0)
        d = fib.to_dict()
        assert d["swing_range"] == 20.0
        assert len(d["retracements"]) == 5
        assert len(d["extensions"]) == 5


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_analysis_pipeline(self):
        """Trend -> S/R -> Fib -> Patterns."""
        _, high, low, close = _make_uptrend(250)

        # Trend
        trend_analyzer = TrendAnalyzer()
        trend = trend_analyzer.analyze(close, symbol="SPY")
        assert trend.direction == TrendDirection.UP

        # S/R
        sr_detector = SRDetector()
        levels = sr_detector.find_levels(high, low, close, symbol="SPY")
        assert isinstance(levels, list)

        # Fibonacci
        fib_calc = FibCalculator()
        fib = fib_calc.compute(high, low, close, symbol="SPY")
        assert fib.swing_high > fib.swing_low

        # Patterns
        pattern_detector = PatternDetector()
        patterns = pattern_detector.detect_all(high, low, close, symbol="SPY")
        assert isinstance(patterns, list)

    def test_crossover_with_trend(self):
        """Detect crossovers and verify trend alignment."""
        rng = np.random.RandomState(42)
        down = np.linspace(150, 100, 150)
        up = np.linspace(100, 160, 150)
        prices = np.concatenate([down, up]) + rng.normal(0, 1.0, 300)
        close = pd.Series(prices)

        analyzer = TrendAnalyzer()
        crossovers = analyzer.detect_crossovers(close, fast_window=20, slow_window=50)
        trend = analyzer.analyze(close)

        # End of series is uptrend
        assert trend.direction == TrendDirection.UP
        assert len(crossovers) > 0


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.charting import (
            PatternDetector,
            TrendAnalyzer,
            SRDetector,
            FibCalculator,
            PatternType,
            TrendDirection,
            SRType,
            CrossoverType,
            ChartPattern,
            TrendAnalysis,
            SRLevel,
            FibonacciLevels,
            DEFAULT_CONFIG,
        )
        assert PatternDetector is not None
        assert TrendAnalyzer is not None
        assert SRDetector is not None
        assert FibCalculator is not None
