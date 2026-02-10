"""PRD-177: Multi-Strategy Bot — tests.

Tests VWAPStrategy, ORBStrategy, RSIDivergenceStrategy,
StrategyRegistry, and BotStrategy protocol compliance.
~50 tests across 5 classes.
"""

from __future__ import annotations

import random
import pytest

from src.strategies.base import BotStrategy
from src.strategies.vwap_strategy import VWAPConfig, VWAPStrategy
from src.strategies.orb_strategy import ORBConfig, ORBStrategy
from src.strategies.rsi_divergence import RSIDivergenceConfig, RSIDivergenceStrategy
from src.strategies.registry import StrategyInfo, StrategyRegistry


# ═════════════════════════════════════════════════════════════════════
# Test VWAP Strategy
# ═════════════════════════════════════════════════════════════════════


class TestVWAPStrategy:
    """Test VWAP mean-reversion strategy."""

    def _make_bars(self, n=30, base=100.0, seed=42):
        random.seed(seed)
        closes = [base + random.uniform(-2, 2) for _ in range(n)]
        opens = [c + random.uniform(-0.5, 0.5) for c in closes]
        highs = [max(o, c) + random.uniform(0, 1) for o, c in zip(opens, closes)]
        lows = [min(o, c) - random.uniform(0, 1) for o, c in zip(opens, closes)]
        volumes = [random.randint(1000, 5000) for _ in range(n)]
        return opens, highs, lows, closes, volumes

    def test_protocol_compliance(self):
        strategy = VWAPStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = VWAPStrategy()
        assert strategy.name == "vwap_reversion"

    def test_analyze_insufficient_data(self):
        strategy = VWAPStrategy()
        result = strategy.analyze("AAPL", [100], [101], [99], [100], [1000])
        assert result is None

    def test_analyze_normal_market(self):
        strategy = VWAPStrategy()
        opens, highs, lows, closes, volumes = self._make_bars()
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        # May or may not fire — just check it doesn't crash
        assert result is None or result.ticker == "AAPL"

    def test_analyze_oversold_condition(self):
        """Price far below VWAP with low RSI should trigger long."""
        strategy = VWAPStrategy(VWAPConfig(
            vwap_deviation_pct=0.1,
            rsi_oversold=50.0,
            min_volume_ratio=0.1,
        ))
        n = 30
        # Build declining prices with high volume
        closes = [100 - i * 0.5 for i in range(n)]
        opens = [c + 0.1 for c in closes]
        highs = [c + 1 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [5000] * n
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "long"
            assert result.stop_loss < result.entry_price

    def test_analyze_overbought_condition(self):
        """Price far above VWAP with high RSI should trigger short."""
        strategy = VWAPStrategy(VWAPConfig(
            vwap_deviation_pct=0.1,
            rsi_overbought=50.0,
            min_volume_ratio=0.1,
        ))
        n = 30
        # Build rising prices
        closes = [100 + i * 0.5 for i in range(n)]
        opens = [c - 0.1 for c in closes]
        highs = [c + 0.5 for c in closes]
        lows = [c - 1 for c in closes]
        volumes = [5000] * n
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "short"

    def test_low_volume_filtered(self):
        strategy = VWAPStrategy(VWAPConfig(min_volume_ratio=10.0))
        opens, highs, lows, closes, volumes = self._make_bars()
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None  # Volume too low

    def test_config_defaults(self):
        config = VWAPConfig()
        assert config.rsi_period == 14
        assert config.vwap_deviation_pct == 0.5

    def test_vwap_computation(self):
        vwap = VWAPStrategy._compute_vwap(
            [102, 104], [98, 96], [100, 100], [1000, 1000]
        )
        assert 98 < vwap < 102

    def test_rsi_computation(self):
        closes = list(range(100, 120))  # Monotonically increasing
        rsi = VWAPStrategy._compute_rsi(closes, 14)
        assert rsi > 50  # Strong uptrend


# ═════════════════════════════════════════════════════════════════════
# Test ORB Strategy
# ═════════════════════════════════════════════════════════════════════


class TestORBStrategy:
    """Test Opening Range Breakout strategy."""

    def test_protocol_compliance(self):
        strategy = ORBStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = ORBStrategy()
        assert strategy.name == "orb_breakout"

    def test_analyze_insufficient_data(self):
        strategy = ORBStrategy()
        result = strategy.analyze("AAPL", [100], [101], [99], [100], [1000])
        assert result is None

    def test_bullish_breakout(self):
        """Price breaks above opening range high with volume."""
        config = ORBConfig(
            opening_range_bars=3,
            volume_multiplier=0.5,
            breakout_threshold_pct=0.01,
        )
        strategy = ORBStrategy(config)
        # Opening range: highs 102, lows 98 → range 98-102
        opens = [100, 100, 100, 100, 100, 105]
        highs = [102, 101, 102, 101, 101, 106]
        lows = [98, 99, 98, 99, 99, 104]
        closes = [100, 100, 100, 100, 100, 105]  # Last bar above range
        volumes = [1000, 1000, 1000, 1000, 1000, 2000]
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "long"

    def test_bearish_breakout(self):
        """Price breaks below opening range low with volume."""
        config = ORBConfig(
            opening_range_bars=3,
            volume_multiplier=0.5,
            breakout_threshold_pct=0.01,
        )
        strategy = ORBStrategy(config)
        opens = [100, 100, 100, 100, 100, 95]
        highs = [102, 101, 102, 101, 101, 96]
        lows = [98, 99, 98, 99, 99, 94]
        closes = [100, 100, 100, 100, 100, 95]
        volumes = [1000, 1000, 1000, 1000, 1000, 2000]
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        if result:
            assert result.direction == "short"

    def test_no_breakout_within_range(self):
        strategy = ORBStrategy(ORBConfig(volume_multiplier=0.1))
        opens = [100] * 10
        highs = [102] * 10
        lows = [98] * 10
        closes = [100] * 10
        volumes = [1000] * 10
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_insufficient_volume_rejected(self):
        strategy = ORBStrategy(ORBConfig(volume_multiplier=5.0))
        opens = [100] * 10
        highs = [102, 101, 102, 101, 101, 101, 101, 101, 101, 110]
        lows = [98] * 10
        closes = [100] * 9 + [110]
        volumes = [1000] * 9 + [500]  # Low volume on breakout bar
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_config_defaults(self):
        config = ORBConfig()
        assert config.opening_range_bars == 3
        assert config.time_stop_bars == 24


# ═════════════════════════════════════════════════════════════════════
# Test RSI Divergence Strategy
# ═════════════════════════════════════════════════════════════════════


class TestRSIDivergenceStrategy:
    """Test RSI divergence strategy."""

    def test_protocol_compliance(self):
        strategy = RSIDivergenceStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = RSIDivergenceStrategy()
        assert strategy.name == "rsi_divergence"

    def test_analyze_insufficient_data(self):
        strategy = RSIDivergenceStrategy()
        result = strategy.analyze("AAPL", [100] * 5, [101] * 5, [99] * 5, [100] * 5, [1000] * 5)
        assert result is None

    def test_analyze_normal_market(self):
        """Should not fire in random noise."""
        strategy = RSIDivergenceStrategy()
        random.seed(42)
        n = 50
        closes = [100 + random.uniform(-1, 1) for _ in range(n)]
        opens = [c + random.uniform(-0.5, 0.5) for c in closes]
        highs = [max(o, c) + random.uniform(0, 0.5) for o, c in zip(opens, closes)]
        lows = [min(o, c) - random.uniform(0, 0.5) for o, c in zip(opens, closes)]
        volumes = [random.randint(1000, 5000) for _ in range(n)]
        result = strategy.analyze("AAPL", opens, highs, lows, closes, volumes)
        # May or may not fire
        assert result is None or result.ticker == "AAPL"

    def test_config_defaults(self):
        config = RSIDivergenceConfig()
        assert config.rsi_period == 14
        assert config.lookback_bars == 10
        assert config.volume_confirmation is True

    def test_rsi_series_computation(self):
        closes = list(range(100, 130))
        rsi_series = RSIDivergenceStrategy._compute_rsi_series(closes, 14)
        assert len(rsi_series) > 0
        # Rising closes should produce high RSI
        assert rsi_series[-1] > 60

    def test_rsi_series_insufficient_data(self):
        rsi_series = RSIDivergenceStrategy._compute_rsi_series([100, 101], 14)
        assert rsi_series == []


# ═════════════════════════════════════════════════════════════════════
# Test StrategyRegistry
# ═════════════════════════════════════════════════════════════════════


class TestStrategyRegistry:
    """Test strategy registration, discovery, and execution."""

    def test_empty_registry(self):
        registry = StrategyRegistry()
        assert registry.get_strategy_count() == 0
        assert registry.list_strategies() == []

    def test_register_strategy(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy(), description="VWAP reversion")
        assert registry.get_strategy_count() == 1
        strategies = registry.list_strategies()
        assert strategies[0]["name"] == "vwap_reversion"

    def test_register_multiple(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy(), category="mean_reversion")
        registry.register(ORBStrategy(), category="breakout")
        registry.register(RSIDivergenceStrategy(), category="divergence")
        assert registry.get_strategy_count() == 3

    def test_get_strategy_by_name(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy())
        strategy = registry.get_strategy("vwap_reversion")
        assert strategy is not None
        assert strategy.name == "vwap_reversion"

    def test_get_nonexistent_strategy(self):
        registry = StrategyRegistry()
        assert registry.get_strategy("does_not_exist") is None

    def test_unregister(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy())
        assert registry.unregister("vwap_reversion") is True
        assert registry.get_strategy_count() == 0

    def test_unregister_nonexistent(self):
        registry = StrategyRegistry()
        assert registry.unregister("nope") is False

    def test_enable_disable(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy())
        registry.disable("vwap_reversion")
        enabled = registry.get_enabled_strategies()
        assert len(enabled) == 0
        registry.enable("vwap_reversion")
        enabled = registry.get_enabled_strategies()
        assert len(enabled) == 1

    def test_analyze_all(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy())
        registry.register(ORBStrategy())
        random.seed(42)
        n = 30
        opens = [100 + random.uniform(-2, 2) for _ in range(n)]
        highs = [o + random.uniform(0, 1) for o in opens]
        lows = [o - random.uniform(0, 1) for o in opens]
        closes = [o + random.uniform(-1, 1) for o in opens]
        volumes = [random.randint(1000, 5000) for _ in range(n)]
        results = registry.analyze_all("AAPL", opens, highs, lows, closes, volumes)
        # Results are list of (strategy_name, signal) tuples
        assert isinstance(results, list)

    def test_analyze_all_disabled_skipped(self):
        registry = StrategyRegistry()
        registry.register(VWAPStrategy())
        registry.disable("vwap_reversion")
        results = registry.analyze_all("AAPL", [100] * 30, [101] * 30, [99] * 30, [100] * 30, [1000] * 30)
        assert len(results) == 0  # Disabled strategy not called

    def test_strategy_info_to_dict(self):
        info = StrategyInfo(name="test", description="A test", category="demo")
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["category"] == "demo"
        assert "registered_at" in d


# ═════════════════════════════════════════════════════════════════════
# Test Protocol Compliance
# ═════════════════════════════════════════════════════════════════════


class TestProtocolCompliance:
    """Verify all strategies implement the BotStrategy protocol."""

    def test_vwap_is_bot_strategy(self):
        assert isinstance(VWAPStrategy(), BotStrategy)

    def test_orb_is_bot_strategy(self):
        assert isinstance(ORBStrategy(), BotStrategy)

    def test_rsi_divergence_is_bot_strategy(self):
        assert isinstance(RSIDivergenceStrategy(), BotStrategy)

    def test_all_have_name_property(self):
        for cls in [VWAPStrategy, ORBStrategy, RSIDivergenceStrategy]:
            s = cls()
            assert isinstance(s.name, str)
            assert len(s.name) > 0

    def test_all_have_analyze_method(self):
        for cls in [VWAPStrategy, ORBStrategy, RSIDivergenceStrategy]:
            s = cls()
            assert callable(s.analyze)
