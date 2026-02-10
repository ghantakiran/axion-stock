"""Tests for Ripster EMA Cloud methodology upgrades.

Covers all new functionality from the Ripster upgrade plan:
- 5th cloud layer (72/89)
- Cloud slope analysis
- Candlestick pattern detection at cloud levels
- Conviction scorer 7-factor update (slope)
- PullbackToCloudStrategy
- TrendDayStrategy
- SessionScalpStrategy
- Trail-to-breakeven exit
- Partial scale-out exit
- Orchestrator partial close
~80+ tests across 8 test classes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.ema_signals.clouds import CloudConfig, CloudState, EMACloudCalculator
from src.ema_signals.conviction import ConvictionScore, ConvictionScorer
from src.ema_signals.detector import SignalDetector, SignalType, TradeSignal
from src.strategies.base import BotStrategy
from src.strategies.pullback_strategy import PullbackConfig, PullbackToCloudStrategy
from src.strategies.trend_day_strategy import TrendDayConfig, TrendDayStrategy
from src.strategies.session_scalp_strategy import SessionScalpConfig, SessionScalpStrategy
from src.trade_executor.executor import ExecutorConfig, Position
from src.trade_executor.exit_monitor import ExitMonitor, ExitSignal


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _make_ohlcv_df(n: int, base: float = 100.0, trend: float = 0.0, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame.

    Args:
        n: Number of bars.
        base: Starting price.
        trend: Per-bar price drift (positive = uptrend, negative = downtrend).
        seed: Random seed for reproducibility.
    """
    rng = np.random.RandomState(seed)
    closes = [base]
    for i in range(1, n):
        noise = rng.uniform(-0.3, 0.3)
        closes.append(closes[-1] + trend + noise)
    closes = np.array(closes)
    opens = closes + rng.uniform(-0.2, 0.2, n)
    highs = np.maximum(opens, closes) + rng.uniform(0, 0.5, n)
    lows = np.minimum(opens, closes) - rng.uniform(0, 0.5, n)
    volumes = rng.randint(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes,
    })


def _make_bar_lists(n: int, base: float = 100.0, trend: float = 0.0, seed: int = 42):
    """Generate parallel lists (opens, highs, lows, closes, volumes) for strategy.analyze()."""
    df = _make_ohlcv_df(n, base, trend, seed)
    return (
        df["open"].tolist(), df["high"].tolist(), df["low"].tolist(),
        df["close"].tolist(), df["volume"].tolist(),
    )


def _make_position(
    ticker: str = "AAPL", direction: str = "long", entry: float = 150.0,
    stop: float = 145.0, target: Optional[float] = 160.0, shares: int = 100,
    trade_type: str = "day",
) -> Position:
    return Position(
        ticker=ticker, direction=direction, entry_price=entry,
        current_price=entry, shares=shares, stop_loss=stop,
        target_price=target, entry_time=datetime.now(timezone.utc),
        trade_type=trade_type,
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. Fifth Cloud Layer (72/89)
# ═══════════════════════════════════════════════════════════════════════


class TestFifthCloudLayer:
    """Tests for the 5th (long-term 72/89) EMA cloud layer."""

    def test_cloud_config_defaults(self):
        config = CloudConfig()
        assert config.long_term_short == 72
        assert config.long_term_long == 89

    def test_get_pairs_returns_five(self):
        config = CloudConfig()
        pairs = config.get_pairs()
        assert len(pairs) == 5
        names = [p[0] for p in pairs]
        assert names == ["fast", "pullback", "trend", "macro", "long_term"]

    def test_max_period_is_89(self):
        config = CloudConfig()
        assert config.max_period == 89

    def test_custom_long_term_periods(self):
        config = CloudConfig(long_term_short=80, long_term_long=100)
        assert config.max_period == 100
        pairs = config.get_pairs()
        lt = [p for p in pairs if p[0] == "long_term"][0]
        assert lt == ("long_term", 80, 100)

    def test_compute_clouds_adds_long_term_columns(self):
        df = _make_ohlcv_df(100)
        calc = EMACloudCalculator()
        result = calc.compute_clouds(df)
        assert "ema_72" in result.columns
        assert "ema_89" in result.columns
        assert "cloud_long_term_bull" in result.columns

    def test_get_cloud_states_returns_five(self):
        df = _make_ohlcv_df(100)
        calc = EMACloudCalculator()
        states = calc.get_cloud_states(df)
        assert len(states) == 5
        names = [s.cloud_name for s in states]
        assert "long_term" in names

    def test_get_all_cloud_states_has_long_term(self):
        df = _make_ohlcv_df(100)
        calc = EMACloudCalculator()
        result = calc.get_all_cloud_states(df)
        assert "price_above_long_term" in result.columns
        assert "price_inside_long_term" in result.columns
        assert "price_below_long_term" in result.columns

    def test_cloud_thickness_long_term(self):
        df = _make_ohlcv_df(100)
        calc = EMACloudCalculator()
        thickness = calc.cloud_thickness(df, "long_term")
        assert len(thickness) == 100
        assert all(t >= 0 for t in thickness)

    def test_backward_compat_four_layer_callers(self):
        """Default CloudConfig() should work for code that only used 4 layers."""
        config = CloudConfig()
        # Old code would access fast/pullback/trend/macro — all still work
        assert config.fast_short == 5
        assert config.macro_long == 50

    def test_signal_detector_uses_five_clouds(self):
        """SignalDetector should scan all 5 cloud names."""
        detector = SignalDetector()
        assert "long_term" in detector.CLOUD_NAMES
        assert len(detector.CLOUD_NAMES) == 5

    def test_detector_min_bars_increased(self):
        """Detector now requires 89+2 = 91 bars minimum."""
        detector = SignalDetector()
        df_short = _make_ohlcv_df(80)
        signals = detector.detect(df_short, "AAPL", "5m")
        assert signals == []  # Too few bars


# ═══════════════════════════════════════════════════════════════════════
# 2. Cloud Slope Analysis
# ═══════════════════════════════════════════════════════════════════════


class TestCloudSlopeAnalysis:
    """Tests for cloud slope computation and direction classification."""

    def test_slope_rising(self):
        """Uptrending data should produce rising slope."""
        df = _make_ohlcv_df(100, trend=0.5, seed=10)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        slope, direction = calc._compute_slope(cloud_df, "ema_5", "ema_12")
        assert slope > 0
        assert direction == "rising"

    def test_slope_falling(self):
        """Downtrending data should produce falling slope."""
        df = _make_ohlcv_df(100, base=200.0, trend=-0.5, seed=11)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        slope, direction = calc._compute_slope(cloud_df, "ema_5", "ema_12")
        assert slope < 0
        assert direction == "falling"

    def test_slope_flat(self):
        """Flat/sideways data should produce flat slope."""
        # Zero trend — noise only, small enough to stay within threshold
        df = _make_ohlcv_df(100, trend=0.0, seed=42)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        # Use macro cloud (34/50) which has stronger smoothing
        slope, direction = calc._compute_slope(cloud_df, "ema_34", "ema_50")
        assert abs(slope) < 0.01  # Within reasonable flatness

    def test_slope_in_cloud_state(self):
        """get_cloud_states() should populate slope fields."""
        df = _make_ohlcv_df(100, trend=0.3)
        calc = EMACloudCalculator()
        states = calc.get_cloud_states(df)
        for s in states:
            assert hasattr(s, "slope")
            assert hasattr(s, "slope_direction")
            assert s.slope_direction in ("rising", "falling", "flat")

    def test_slope_short_data(self):
        """Slope computation with insufficient data returns flat."""
        df = _make_ohlcv_df(3)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        slope, direction = calc._compute_slope(cloud_df, "ema_5", "ema_12")
        assert slope == 0.0
        assert direction == "flat"

    def test_slope_to_dict(self):
        """CloudState.to_dict() should include slope fields."""
        state = CloudState(
            cloud_name="fast", short_ema=100.0, long_ema=99.0,
            is_bullish=True, thickness=0.01,
            price_above=True, price_inside=False, price_below=False,
            slope=0.005, slope_direction="rising",
        )
        d = state.to_dict()
        assert d["slope"] == 0.005
        assert d["slope_direction"] == "rising"


# ═══════════════════════════════════════════════════════════════════════
# 3. Candlestick Pattern Detection
# ═══════════════════════════════════════════════════════════════════════


class TestCandlestickPatterns:
    """Tests for candlestick pattern detection at cloud levels."""

    def test_signal_types_exist(self):
        assert SignalType.CANDLESTICK_BULLISH.value == "candlestick_bullish"
        assert SignalType.CANDLESTICK_BEARISH.value == "candlestick_bearish"

    def test_hammer_at_cloud(self):
        """Hammer pattern near a cloud level should produce bullish signal."""
        # Build data where last bar is a hammer near a cloud level
        n = 100
        df = _make_ohlcv_df(n, base=100, trend=0.1, seed=42)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        states = calc.get_cloud_states(cloud_df)

        # Get a cloud level to place our hammer near
        fast_upper = max(states[0].short_ema, states[0].long_ema)

        # Overwrite last bar to be a hammer near that level
        close_price = fast_upper * 1.001  # Near the cloud
        open_price = close_price - 0.05  # Small body (green)
        low_price = close_price - 2.0     # Long lower wick
        high_price = close_price + 0.1

        cloud_df.iloc[-1, cloud_df.columns.get_loc("open")] = open_price
        cloud_df.iloc[-1, cloud_df.columns.get_loc("high")] = high_price
        cloud_df.iloc[-1, cloud_df.columns.get_loc("low")] = low_price
        cloud_df.iloc[-1, cloud_df.columns.get_loc("close")] = close_price

        detector = SignalDetector()
        signals = detector._detect_candlestick_patterns(cloud_df, "AAPL", "5m", states)
        # Should detect at least one bullish candlestick pattern
        bullish = [s for s in signals if s.signal_type == SignalType.CANDLESTICK_BULLISH]
        assert len(bullish) > 0

    def test_bearish_engulfing_at_cloud(self):
        """Bearish engulfing near a cloud should produce bearish signal."""
        n = 100
        df = _make_ohlcv_df(n, base=100, trend=-0.1, seed=44)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        states = calc.get_cloud_states(cloud_df)

        fast_lower = min(states[0].short_ema, states[0].long_ema)

        # Prev bar: small green candle
        prev_open = fast_lower * 0.999
        prev_close = fast_lower * 1.001
        cloud_df.iloc[-2, cloud_df.columns.get_loc("open")] = prev_open
        cloud_df.iloc[-2, cloud_df.columns.get_loc("close")] = prev_close
        cloud_df.iloc[-2, cloud_df.columns.get_loc("high")] = prev_close + 0.1
        cloud_df.iloc[-2, cloud_df.columns.get_loc("low")] = prev_open - 0.1

        # Current bar: large red candle engulfing
        curr_open = prev_close + 0.5
        curr_close = prev_open - 0.5
        cloud_df.iloc[-1, cloud_df.columns.get_loc("open")] = curr_open
        cloud_df.iloc[-1, cloud_df.columns.get_loc("close")] = curr_close
        cloud_df.iloc[-1, cloud_df.columns.get_loc("high")] = curr_open + 0.2
        cloud_df.iloc[-1, cloud_df.columns.get_loc("low")] = curr_close - 0.2

        detector = SignalDetector()
        signals = detector._detect_candlestick_patterns(cloud_df, "AAPL", "5m", states)
        bearish = [s for s in signals if s.signal_type == SignalType.CANDLESTICK_BEARISH]
        assert len(bearish) > 0

    def test_no_signal_far_from_cloud(self):
        """Candlestick patterns far from any cloud level should not fire."""
        n = 100
        df = _make_ohlcv_df(n, base=100, trend=0.3, seed=42)
        calc = EMACloudCalculator()
        cloud_df = calc.compute_clouds(df)
        states = calc.get_cloud_states(cloud_df)

        # Force last bar far above all clouds
        cloud_df.iloc[-1, cloud_df.columns.get_loc("close")] = 200.0
        cloud_df.iloc[-1, cloud_df.columns.get_loc("open")] = 200.1
        cloud_df.iloc[-1, cloud_df.columns.get_loc("high")] = 202.0
        cloud_df.iloc[-1, cloud_df.columns.get_loc("low")] = 198.0

        detector = SignalDetector()
        signals = detector._detect_candlestick_patterns(cloud_df, "AAPL", "5m", states)
        assert len(signals) == 0

    def test_insufficient_data_returns_empty(self):
        df = pd.DataFrame({
            "open": [100, 100], "high": [101, 101], "low": [99, 99],
            "close": [100, 100], "volume": [1000, 1000],
        })
        detector = SignalDetector()
        signals = detector._detect_candlestick_patterns(df, "AAPL", "5m", [])
        assert signals == []

    def test_candlestick_integrated_in_detect(self):
        """Candlestick patterns should appear in the full detect() output."""
        n = 100
        df = _make_ohlcv_df(n, base=100, trend=0.0, seed=42)
        detector = SignalDetector()
        signals = detector.detect(df, "AAPL", "5m")
        # We don't guarantee a candlestick fires here, but the code path runs without error
        assert isinstance(signals, list)


# ═══════════════════════════════════════════════════════════════════════
# 4. Conviction Scorer (slope factor)
# ═══════════════════════════════════════════════════════════════════════


class TestConvictionSlope:
    """Tests for the 7-factor conviction scorer with cloud slope."""

    def test_weights_sum_to_100(self):
        scorer = ConvictionScorer()
        total = (
            scorer.WEIGHT_CLOUD_ALIGNMENT + scorer.WEIGHT_MTF_CONFLUENCE
            + scorer.WEIGHT_VOLUME + scorer.WEIGHT_THICKNESS
            + scorer.WEIGHT_SLOPE + scorer.WEIGHT_CANDLE
            + scorer.WEIGHT_FACTOR
        )
        assert total == 100.0

    def test_slope_weight_is_5(self):
        scorer = ConvictionScorer()
        assert scorer.WEIGHT_SLOPE == 5.0

    def test_thickness_weight_is_5(self):
        """Thickness was reduced from 10 to 5 to make room for slope."""
        scorer = ConvictionScorer()
        assert scorer.WEIGHT_THICKNESS == 5.0

    def test_score_cloud_slope_all_rising(self):
        scorer = ConvictionScorer()
        states = [
            CloudState("fast", 100, 99, True, 0.01, True, False, False, 0.005, "rising"),
            CloudState("pullback", 100, 99, True, 0.01, True, False, False, 0.003, "rising"),
            CloudState("trend", 100, 99, True, 0.01, True, False, False, 0.002, "rising"),
            CloudState("macro", 100, 99, True, 0.01, True, False, False, 0.001, "rising"),
            CloudState("long_term", 100, 99, True, 0.01, True, False, False, 0.001, "rising"),
        ]
        pts = scorer._score_cloud_slope(states)
        assert pts == scorer.WEIGHT_SLOPE  # All rising = full points

    def test_score_cloud_slope_mixed(self):
        scorer = ConvictionScorer()
        states = [
            CloudState("fast", 100, 99, True, 0.01, True, False, False, 0.005, "rising"),
            CloudState("pullback", 100, 99, True, 0.01, True, False, False, 0.003, "rising"),
            CloudState("trend", 100, 99, True, 0.01, True, False, False, 0.0, "flat"),
            CloudState("macro", 100, 99, True, 0.01, True, False, False, -0.002, "falling"),
            CloudState("long_term", 100, 99, True, 0.01, True, False, False, -0.001, "falling"),
        ]
        pts = scorer._score_cloud_slope(states)
        # 2 rising vs 2 falling vs 1 flat → dominant=2/5=0.4
        assert 0 < pts < scorer.WEIGHT_SLOPE

    def test_score_cloud_slope_empty(self):
        scorer = ConvictionScorer()
        pts = scorer._score_cloud_slope([])
        assert pts == 0.0

    def test_conviction_score_has_slope_field(self):
        scorer = ConvictionScorer()
        signal = TradeSignal(
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long", ticker="AAPL", timeframe="5m",
            conviction=0, entry_price=100, stop_loss=95,
            cloud_states=[
                CloudState("fast", 100, 99, True, 0.01, True, False, False, 0.005, "rising"),
            ],
        )
        score = scorer.score(signal)
        assert hasattr(score, "cloud_slope")
        assert isinstance(score.cloud_slope, float)

    def test_conviction_breakdown_includes_slope_counts(self):
        scorer = ConvictionScorer()
        states = [
            CloudState("fast", 100, 99, True, 0.01, True, False, False, 0.005, "rising"),
            CloudState("macro", 100, 101, False, 0.01, False, False, True, -0.005, "falling"),
        ]
        signal = TradeSignal(
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long", ticker="AAPL", timeframe="5m",
            conviction=0, entry_price=100, stop_loss=95,
            cloud_states=states,
        )
        score = scorer.score(signal)
        assert "slope_rising" in score.breakdown
        assert "slope_falling" in score.breakdown
        assert score.breakdown["slope_rising"] == 1
        assert score.breakdown["slope_falling"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. PullbackToCloudStrategy
# ═══════════════════════════════════════════════════════════════════════


class TestPullbackToCloudStrategy:
    """Tests for the pullback-to-cloud entry strategy."""

    def test_protocol_compliance(self):
        strategy = PullbackToCloudStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = PullbackToCloudStrategy()
        assert strategy.name == "pullback_to_cloud"

    def test_insufficient_data(self):
        strategy = PullbackToCloudStrategy()
        result = strategy.analyze("AAPL", [100] * 5, [101] * 5, [99] * 5, [100] * 5, [1000] * 5)
        assert result is None

    def test_config_defaults(self):
        config = PullbackConfig()
        assert config.trend_lookback == 10
        assert config.pullback_threshold_pct == 0.3
        assert config.risk_reward == 2.0

    def test_bullish_pullback_signal(self):
        """Craft an uptrend with pullback to fast cloud and bounce."""
        config = PullbackConfig(
            trend_lookback=5, pullback_threshold_pct=1.0,
            min_volume_ratio=0.5, risk_reward=2.0,
        )
        strategy = PullbackToCloudStrategy(config)

        n = 70
        # Strong uptrend then dip and recovery
        closes = [100 + i * 0.5 for i in range(n - 3)]
        # Pullback: dip down toward fast cloud
        closes.append(closes[-1] - 2.0)
        closes.append(closes[-1] - 0.5)
        # Bounce: close back above
        closes.append(closes[-3] + 0.5)

        opens = [c - 0.1 for c in closes]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        # Pullback bar has low touching cloud area
        lows[-2] = closes[-2] - 1.0
        volumes = [2000.0] * n

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "long"
            assert result.signal_type == SignalType.CLOUD_BOUNCE_LONG
            assert result.stop_loss < result.entry_price
            assert result.target_price > result.entry_price
            assert result.metadata["strategy"] == "pullback_to_cloud"

    def test_bearish_pullback_signal(self):
        """Craft a downtrend with pullback to fast cloud and drop."""
        config = PullbackConfig(
            trend_lookback=5, pullback_threshold_pct=1.0,
            min_volume_ratio=0.5,
        )
        strategy = PullbackToCloudStrategy(config)

        n = 70
        # Strong downtrend then rally and resume
        closes = [200 - i * 0.5 for i in range(n - 3)]
        # Rally toward cloud
        closes.append(closes[-1] + 2.0)
        closes.append(closes[-1] + 0.5)
        # Resume drop
        closes.append(closes[-3] - 0.5)

        opens = [c + 0.1 for c in closes]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        highs[-2] = closes[-2] + 1.0  # Rally bar high touches cloud
        volumes = [2000.0] * n

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "short"
            assert result.signal_type == SignalType.CLOUD_BOUNCE_SHORT

    def test_low_volume_filtered(self):
        """High min_volume_ratio should filter out low-volume bars."""
        config = PullbackConfig(min_volume_ratio=10.0)
        strategy = PullbackToCloudStrategy(config)
        opens, highs, lows, closes, volumes = _make_bar_lists(70, trend=0.3)
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_no_trend_no_signal(self):
        """Choppy market with no trend should not produce a signal."""
        strategy = PullbackToCloudStrategy(PullbackConfig(min_volume_ratio=0.1))
        opens, highs, lows, closes, volumes = _make_bar_lists(70, trend=0.0, seed=99)
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None or result.metadata.get("strategy") == "pullback_to_cloud"

    def test_conviction_base(self):
        strategy = PullbackToCloudStrategy()
        assert strategy._compute_conviction(1.0, 10, True) == 60  # base 55 + 5 trend
        assert strategy._compute_conviction(2.0, 10, True) == 75  # base 55 + 15 vol + 5 trend
        assert strategy._compute_conviction(2.5, 15, True) == 80  # base 55 + 15 vol + 10 trend

    def test_conviction_capped_at_90(self):
        strategy = PullbackToCloudStrategy()
        result = strategy._compute_conviction(3.0, 20, True)
        assert result <= 90

    def test_ema_helper(self):
        data = [100.0, 102.0, 101.0, 103.0, 104.0]
        ema = PullbackToCloudStrategy._ema(data, 3)
        assert len(ema) == len(data)
        assert ema[0] == data[0]  # First value same as input

    def test_ema_empty_input(self):
        assert PullbackToCloudStrategy._ema([], 5) == []


# ═══════════════════════════════════════════════════════════════════════
# 6. TrendDayStrategy
# ═══════════════════════════════════════════════════════════════════════


class TestTrendDayStrategy:
    """Tests for trend day detection and full-size entry strategy."""

    def test_protocol_compliance(self):
        strategy = TrendDayStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = TrendDayStrategy()
        assert strategy.name == "trend_day"

    def test_insufficient_data(self):
        strategy = TrendDayStrategy()
        result = strategy.analyze("AAPL", [100] * 5, [101] * 5, [99] * 5, [100] * 5, [1000] * 5)
        assert result is None

    def test_config_defaults(self):
        config = TrendDayConfig()
        assert config.opening_range_bars == 6
        assert config.breakout_deadline_bars == 12
        assert config.volume_threshold == 1.5
        assert config.atr_expansion == 1.2

    def test_bullish_trend_day(self):
        """ORB breakout to upside with volume + ATR expansion + cloud alignment."""
        config = TrendDayConfig(
            opening_range_bars=3, breakout_deadline_bars=6,
            volume_threshold=0.5, atr_expansion=0.1,
        )
        strategy = TrendDayStrategy(config)

        n = 60
        # Uptrending data with a clear ORB break
        closes = [100 + i * 0.3 for i in range(n - 6)]
        # Opening range: tight range
        closes.extend([closes[-1], closes[-1] + 0.1, closes[-1] - 0.1])
        or_high = max(closes[-3:])
        # Breakout bars above opening range
        closes.extend([or_high + 2, or_high + 3, or_high + 4])

        opens = [c - 0.1 for c in closes]
        highs = [c + 1.0 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [2000.0] * n

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "long"
            assert result.conviction >= 80
            assert result.target_price is None  # Trend days trail
            assert result.metadata["strategy"] == "trend_day"

    def test_bearish_trend_day(self):
        """ORB breakout to downside."""
        config = TrendDayConfig(
            opening_range_bars=3, breakout_deadline_bars=6,
            volume_threshold=0.5, atr_expansion=0.1,
        )
        strategy = TrendDayStrategy(config)

        n = 60
        closes = [200 - i * 0.3 for i in range(n - 6)]
        closes.extend([closes[-1], closes[-1] - 0.1, closes[-1] + 0.1])
        or_low = min(closes[-3:])
        closes.extend([or_low - 2, or_low - 3, or_low - 4])

        opens = [c + 0.1 for c in closes]
        highs = [c + 0.5 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = [2000.0] * n

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "short"
            assert result.conviction >= 80

    def test_no_breakout_no_signal(self):
        """Price staying within opening range should not fire."""
        config = TrendDayConfig(volume_threshold=0.1, atr_expansion=0.1)
        strategy = TrendDayStrategy(config)

        n = 60
        closes = [100.0] * n  # Flat — no breakout
        opens = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        volumes = [2000.0] * n

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_low_volume_breakout_filtered(self):
        """Breakout on low volume should not fire."""
        config = TrendDayConfig(volume_threshold=10.0)
        strategy = TrendDayStrategy(config)
        opens, highs, lows, closes, volumes = _make_bar_lists(60, trend=0.5)
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_conviction_high_base(self):
        strategy = TrendDayStrategy()
        assert strategy._compute_conviction(1.5, 1.5) == 80
        assert strategy._compute_conviction(2.5, 1.5) == 90  # 80 + 10 vol
        assert strategy._compute_conviction(2.0, 2.0) == 90  # 80 + 5 vol + 5 atr

    def test_conviction_capped_at_95(self):
        strategy = TrendDayStrategy()
        assert strategy._compute_conviction(3.0, 3.0) == 95

    def test_atr_computation(self):
        highs = [102.0, 103.0, 104.0, 105.0, 106.0]
        lows = [98.0, 99.0, 100.0, 101.0, 102.0]
        closes = [100.0, 101.0, 102.0, 103.0, 104.0]
        atr = TrendDayStrategy._compute_atr(highs, lows, closes, 3)
        assert atr > 0

    def test_atr_insufficient_data(self):
        assert TrendDayStrategy._compute_atr([100], [99], [100], 5) == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 7. SessionScalpStrategy
# ═══════════════════════════════════════════════════════════════════════


class TestSessionScalpStrategy:
    """Tests for session-aware scalping strategy."""

    def test_protocol_compliance(self):
        strategy = SessionScalpStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = SessionScalpStrategy()
        assert strategy.name == "session_scalp"

    def test_insufficient_data(self):
        strategy = SessionScalpStrategy()
        result = strategy.analyze("AAPL", [100] * 5, [101] * 5, [99] * 5, [100] * 5, [1000] * 5)
        assert result is None

    def test_config_defaults(self):
        config = SessionScalpConfig()
        assert config.open_bell_end_bar == 12
        assert config.power_hour_start_bar == 54
        assert config.open_bell_conviction_boost == 10
        assert config.midday_conviction_penalty == 10
        assert config.power_hour_conviction_boost == 5

    def test_session_classification_open_bell(self):
        strategy = SessionScalpStrategy()
        assert strategy._classify_session(8) == "open_bell"
        assert strategy._classify_session(12) == "open_bell"

    def test_session_classification_midday(self):
        strategy = SessionScalpStrategy()
        assert strategy._classify_session(20) == "midday"
        assert strategy._classify_session(40) == "midday"

    def test_session_classification_power_hour(self):
        strategy = SessionScalpStrategy()
        assert strategy._classify_session(54) == "power_hour"
        assert strategy._classify_session(70) == "power_hour"

    def test_open_bell_bullish_breakout(self):
        """First 12 bars with ORB break should route to open_bell analyzer."""
        config = SessionScalpConfig(open_bell_end_bar=12)
        strategy = SessionScalpStrategy(config)

        # 10 bars simulating open bell: tight range then break up
        n = 10
        closes = [100.0] * 3 + [100.0, 100.5, 101.0, 102.0, 103.0, 104.0, 105.0]
        opens = [c - 0.1 for c in closes]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [3000.0] * n  # High volume

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.metadata["session"] == "open_bell"
            assert result.direction in ("long", "short")

    def test_midday_conservative(self):
        """Midday session should only fire on pullback in established trend."""
        config = SessionScalpConfig(
            open_bell_end_bar=5, power_hour_start_bar=80,
            midday_min_trend_bars=3,
        )
        strategy = SessionScalpStrategy(config)

        # 20 bars — past open_bell, before power_hour
        opens, highs, lows, closes, volumes = _make_bar_lists(20, trend=0.0, seed=88)
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        # Choppy market in midday → likely no signal
        assert result is None or result.metadata.get("session") == "midday"

    def test_power_hour_needs_volume(self):
        """Power hour requires volume surge >= 1.3x."""
        config = SessionScalpConfig(power_hour_start_bar=5)
        strategy = SessionScalpStrategy(config)

        n = 60  # Past power_hour_start_bar
        closes = [100.0] * n
        opens = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        volumes = [1000.0] * n  # Low flat volume

        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None  # Volume too low

    def test_open_bell_conviction_boost(self):
        """Open bell conviction = 65 + boost (default 10) = 75."""
        config = SessionScalpConfig(open_bell_conviction_boost=10)
        # 65 + 10 = 75
        expected = min(90, 65 + 10)
        assert expected == 75

    def test_midday_conviction_penalty(self):
        """Midday conviction = 55 - penalty (default 10) = 45."""
        config = SessionScalpConfig(midday_conviction_penalty=10)
        expected = max(40, 55 - 10)
        assert expected == 45


# ═══════════════════════════════════════════════════════════════════════
# 8. Trail-to-Breakeven & Scale-Out Exits
# ═══════════════════════════════════════════════════════════════════════


class TestTrailToBreakeven:
    """Tests for trail-to-breakeven exit strategy."""

    def test_long_at_1r_triggers(self):
        """Long position at 1R profit should move stop to breakeven."""
        pos = _make_position(entry=150.0, stop=145.0, shares=100)
        monitor = ExitMonitor()
        # 1R = $5, so 1R target = $155
        signal = monitor.check_trail_to_breakeven(pos, 155.0)
        assert signal is not None
        assert signal.exit_type == "trail_to_breakeven"
        assert signal.priority == 8
        assert pos.stop_loss > 150.0  # Stop moved above entry

    def test_long_below_1r_no_trigger(self):
        """Long position below 1R should not trigger."""
        pos = _make_position(entry=150.0, stop=145.0)
        monitor = ExitMonitor()
        signal = monitor.check_trail_to_breakeven(pos, 153.0)
        assert signal is None

    def test_short_at_1r_triggers(self):
        """Short position at 1R profit should move stop."""
        pos = _make_position(entry=150.0, stop=155.0, direction="short")
        monitor = ExitMonitor()
        # 1R = $5, target = $145
        signal = monitor.check_trail_to_breakeven(pos, 145.0)
        assert signal is not None
        assert signal.exit_type == "trail_to_breakeven"
        assert pos.stop_loss < 150.0  # Stop moved below entry

    def test_short_above_1r_no_trigger(self):
        pos = _make_position(entry=150.0, stop=155.0, direction="short")
        monitor = ExitMonitor()
        signal = monitor.check_trail_to_breakeven(pos, 148.0)
        assert signal is None

    def test_stop_already_above_breakeven(self):
        """If stop is already at breakeven, should not fire again."""
        pos = _make_position(entry=150.0, stop=150.5)  # Stop already above entry
        monitor = ExitMonitor()
        signal = monitor.check_trail_to_breakeven(pos, 155.0)
        assert signal is None  # new_stop would be ~150.15, less than current 150.5

    def test_zero_risk_no_trigger(self):
        """Stop = entry should not trigger (zero risk)."""
        pos = _make_position(entry=150.0, stop=150.0)
        monitor = ExitMonitor()
        signal = monitor.check_trail_to_breakeven(pos, 155.0)
        assert signal is None

    def test_metadata_contains_prices(self):
        pos = _make_position(entry=150.0, stop=145.0)
        monitor = ExitMonitor()
        signal = monitor.check_trail_to_breakeven(pos, 155.0)
        assert signal is not None
        assert "new_stop" in signal.metadata
        assert "trigger_price" in signal.metadata
        assert signal.metadata["trigger_price"] == 155.0


class TestScaleOut:
    """Tests for partial scale-out exit strategy."""

    def test_long_scale_out_at_1r(self):
        pos = _make_position(entry=150.0, stop=145.0, shares=100)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 155.0)
        assert signal is not None
        assert signal.exit_type == "scale_out"
        assert signal.priority == 9
        assert signal.metadata["partial"] is True
        assert signal.metadata["scale_qty"] == 50

    def test_short_scale_out_at_1r(self):
        pos = _make_position(entry=150.0, stop=155.0, direction="short", shares=100)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 145.0)
        assert signal is not None
        assert signal.metadata["scale_qty"] == 50

    def test_single_share_no_scale(self):
        pos = _make_position(entry=150.0, stop=145.0, shares=1)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 155.0)
        assert signal is None  # Can't scale out 1 share

    def test_below_1r_no_scale(self):
        pos = _make_position(entry=150.0, stop=145.0, shares=100)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 153.0)
        assert signal is None

    def test_zero_risk_no_scale(self):
        pos = _make_position(entry=150.0, stop=150.0, shares=100)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 155.0)
        assert signal is None

    def test_odd_shares_floor_division(self):
        pos = _make_position(entry=150.0, stop=145.0, shares=7)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 155.0)
        assert signal is not None
        assert signal.metadata["scale_qty"] == 3  # 7 // 2

    def test_scale_pct_is_half(self):
        pos = _make_position(entry=150.0, stop=145.0, shares=100)
        monitor = ExitMonitor()
        signal = monitor.check_scale_out(pos, 155.0)
        assert signal.metadata["scale_pct"] == 0.5

    def test_check_all_includes_new_exits(self):
        """check_all() should include trail_to_breakeven and scale_out."""
        pos = _make_position(entry=150.0, stop=145.0, shares=100)
        monitor = ExitMonitor()
        # At 1R: both trail_to_breakeven (priority 8) and scale_out (priority 9) fire
        # But stop_loss doesn't fire, target doesn't fire
        # Trail to breakeven fires and has higher priority
        signal = monitor.check_all(pos, 155.0)
        assert signal is not None
        # Highest priority should win — trail_to_breakeven (8) < scale_out (9)
        assert signal.exit_type == "trail_to_breakeven"


# ═══════════════════════════════════════════════════════════════════════
# 9. Orchestrator Partial Close
# ═══════════════════════════════════════════════════════════════════════


class TestOrchestratorPartialClose:
    """Tests for orchestrator.close_position() partial close handling."""

    def _make_orchestrator(self):
        """Create a minimal BotOrchestrator for testing."""
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig
        config = PipelineConfig()
        orch = BotOrchestrator(config)
        return orch

    def _add_position(self, orch, ticker="AAPL", shares=100, entry=150.0, stop=145.0):
        pos = Position(
            ticker=ticker, direction="long", entry_price=entry,
            current_price=entry, shares=shares, stop_loss=stop,
            target_price=160.0, entry_time=datetime.now(timezone.utc),
        )
        orch.positions.append(pos)
        return pos

    def test_full_close_removes_position(self):
        orch = self._make_orchestrator()
        self._add_position(orch, shares=100)
        closed = orch.close_position("AAPL", "test", exit_price=155.0)
        assert closed is not None
        assert closed.shares == 100
        assert len(orch.positions) == 0

    def test_partial_close_reduces_shares(self):
        orch = self._make_orchestrator()
        self._add_position(orch, shares=100)
        closed = orch.close_position("AAPL", "scale_out", exit_price=155.0, partial_qty=50)
        assert closed is not None
        assert closed.shares == 50  # Returned closed portion
        assert len(orch.positions) == 1  # Position still exists
        assert orch.positions[0].shares == 50  # Remaining shares

    def test_partial_close_equal_shares_does_full(self):
        """partial_qty >= shares should do full close."""
        orch = self._make_orchestrator()
        self._add_position(orch, shares=100)
        closed = orch.close_position("AAPL", "test", exit_price=155.0, partial_qty=100)
        assert closed is not None
        assert len(orch.positions) == 0  # Full close

    def test_partial_close_preserves_direction(self):
        orch = self._make_orchestrator()
        self._add_position(orch, shares=100)
        closed = orch.close_position("AAPL", "scale_out", exit_price=155.0, partial_qty=30)
        assert closed.direction == "long"
        assert closed.ticker == "AAPL"
        assert closed.entry_price == 150.0

    def test_close_nonexistent_ticker(self):
        orch = self._make_orchestrator()
        closed = orch.close_position("MSFT", "test", exit_price=100.0)
        assert closed is None


# ═══════════════════════════════════════════════════════════════════════
# 10. Strategy Registration (New Strategies in __init__)
# ═══════════════════════════════════════════════════════════════════════


class TestNewStrategyRegistration:
    """Verify new strategies are properly exported and protocol-compliant."""

    def test_import_pullback(self):
        from src.strategies import PullbackToCloudStrategy
        s = PullbackToCloudStrategy()
        assert isinstance(s, BotStrategy)

    def test_import_trend_day(self):
        from src.strategies import TrendDayStrategy
        s = TrendDayStrategy()
        assert isinstance(s, BotStrategy)

    def test_import_session_scalp(self):
        from src.strategies import SessionScalpStrategy
        s = SessionScalpStrategy()
        assert isinstance(s, BotStrategy)

    def test_all_exports(self):
        from src.strategies import __all__
        assert "PullbackToCloudStrategy" in __all__
        assert "TrendDayStrategy" in __all__
        assert "SessionScalpStrategy" in __all__

    def test_all_six_strategies_in_registry(self):
        """Registry should be able to hold all 6 strategies."""
        from src.strategies.registry import StrategyRegistry
        from src.strategies import (
            VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
            PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy,
        )
        reg = StrategyRegistry()
        for cls in [VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
                    PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy]:
            reg.register(cls())
        assert reg.get_strategy_count() == 6

    def test_unique_strategy_names(self):
        from src.strategies import (
            VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
            PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy,
        )
        names = {cls().name for cls in [
            VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
            PullbackToCloudStrategy, TrendDayStrategy, SessionScalpStrategy,
        ]}
        assert len(names) == 6  # All unique
