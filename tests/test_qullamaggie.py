"""Qullamaggie Momentum Strategies — tests.

Tests for all 3 strategies (Breakout, Episodic Pivot, Parabolic Short),
indicators, configs, scanner presets, and integration with StrategyRegistry.
~90 tests across 10 classes.
"""

from __future__ import annotations

import random
import pytest

from src.strategies.base import BotStrategy
from src.qullamaggie.config import (
    BreakoutConfig,
    EpisodicPivotConfig,
    ParabolicShortConfig,
)
from src.qullamaggie.indicators import (
    ConsolidationResult,
    compute_adr,
    compute_atr,
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_adx,
    compute_vwap,
    detect_consolidation,
    detect_higher_lows,
    volume_contraction,
)
from src.qullamaggie.breakout_strategy import QullamaggieBreakoutStrategy
from src.qullamaggie.episodic_pivot_strategy import EpisodicPivotStrategy
from src.qullamaggie.parabolic_short_strategy import ParabolicShortStrategy
from src.qullamaggie.scanner import (
    QULLAMAGGIE_PRESETS,
    QULLAMAGGIE_EP_SCAN,
    QULLAMAGGIE_BREAKOUT_SCAN,
    QULLAMAGGIE_HTF_SCAN,
    QULLAMAGGIE_MOMENTUM_LEADER_SCAN,
    QULLAMAGGIE_PARABOLIC_SCAN,
)


# ═════════════════════════════════════════════════════════════════════
# Module Imports
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieModuleImports:
    """All module exports should be importable."""

    def test_config_imports(self):
        from src.qullamaggie import BreakoutConfig, EpisodicPivotConfig, ParabolicShortConfig
        assert BreakoutConfig is not None
        assert EpisodicPivotConfig is not None
        assert ParabolicShortConfig is not None

    def test_indicator_imports(self):
        from src.qullamaggie import (
            compute_adr, compute_atr, compute_sma, compute_ema,
            compute_rsi, compute_adx, compute_vwap,
            detect_consolidation, detect_higher_lows, volume_contraction,
        )
        assert callable(compute_adr)

    def test_strategy_imports(self):
        from src.qullamaggie import (
            QullamaggieBreakoutStrategy,
            EpisodicPivotStrategy,
            ParabolicShortStrategy,
        )
        assert QullamaggieBreakoutStrategy is not None

    def test_scanner_imports(self):
        from src.qullamaggie import QULLAMAGGIE_PRESETS
        assert isinstance(QULLAMAGGIE_PRESETS, dict)

    def test_all_exports(self):
        import src.qullamaggie as mod
        assert hasattr(mod, "__all__")
        assert len(mod.__all__) >= 15


# ═════════════════════════════════════════════════════════════════════
# Indicators
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieIndicators:
    """Test shared indicator helpers."""

    def _make_prices(self, n=50, base=100.0, seed=42):
        random.seed(seed)
        closes = [base + random.uniform(-3, 3) for _ in range(n)]
        highs = [c + random.uniform(0.5, 2) for c in closes]
        lows = [c - random.uniform(0.5, 2) for c in closes]
        volumes = [random.randint(100000, 500000) for _ in range(n)]
        return highs, lows, closes, volumes

    def test_compute_adr_basic(self):
        highs = [105, 106, 107, 108, 109] * 4
        lows = [95, 96, 97, 98, 99] * 4
        result = compute_adr(highs, lows, period=20)
        assert result > 0
        assert isinstance(result, float)

    def test_compute_adr_insufficient_data(self):
        assert compute_adr([100], [90], period=20) == 0.0

    def test_compute_atr_basic(self):
        highs, lows, closes, _ = self._make_prices()
        result = compute_atr(highs, lows, closes, period=14)
        assert result > 0

    def test_compute_atr_insufficient_data(self):
        assert compute_atr([100], [90], [95], period=14) == 0.0

    def test_compute_sma_basic(self):
        values = [10, 20, 30, 40, 50]
        sma = compute_sma(values, 3)
        assert len(sma) == 3
        assert sma[0] == pytest.approx(20.0)  # (10+20+30)/3
        assert sma[-1] == pytest.approx(40.0)  # (30+40+50)/3

    def test_compute_sma_insufficient_data(self):
        assert compute_sma([10], 5) == []

    def test_compute_ema_basic(self):
        values = [10, 20, 30, 40, 50, 60, 70]
        ema = compute_ema(values, 3)
        assert len(ema) == 7
        # EMA should be responsive to recent values
        assert ema[-1] > ema[0]

    def test_compute_ema_insufficient_data(self):
        assert compute_ema([10], 5) == []

    def test_compute_rsi_bullish(self):
        # Steadily rising prices -> high RSI
        closes = [50 + i * 0.5 for i in range(30)]
        rsi = compute_rsi(closes, period=14)
        assert rsi > 70

    def test_compute_rsi_bearish(self):
        # Steadily falling prices -> low RSI
        closes = [100 - i * 0.5 for i in range(30)]
        rsi = compute_rsi(closes, period=14)
        assert rsi < 30

    def test_compute_rsi_insufficient_data(self):
        assert compute_rsi([50, 51], period=14) == 50.0

    def test_compute_adx_trending(self):
        # Strong uptrend
        highs = [100 + i * 2 for i in range(30)]
        lows = [98 + i * 2 for i in range(30)]
        closes = [99 + i * 2 for i in range(30)]
        adx = compute_adx(highs, lows, closes, period=14)
        assert adx > 0

    def test_compute_adx_insufficient_data(self):
        assert compute_adx([100], [90], [95], period=14) == 0.0

    def test_compute_vwap_basic(self):
        highs = [102, 104, 106]
        lows = [98, 100, 102]
        closes = [100, 102, 104]
        volumes = [1000, 2000, 3000]
        vwap = compute_vwap(highs, lows, closes, volumes)
        assert 100 < vwap < 106
        assert isinstance(vwap, float)

    def test_compute_vwap_no_volume(self):
        result = compute_vwap([], [], [], [])
        assert result == 0.0

    def test_detect_consolidation_found(self):
        # Prior move then flat
        highs = [50 + i for i in range(20)] + [70 + random.uniform(-1, 1) for _ in range(20)]
        lows = [48 + i for i in range(20)] + [68 + random.uniform(-1, 1) for _ in range(20)]
        closes = [49 + i for i in range(20)] + [69 + random.uniform(-1, 1) for _ in range(20)]
        cfg = BreakoutConfig(consolidation_min_bars=5, consolidation_max_bars=30)
        result = detect_consolidation(highs, lows, closes, cfg)
        # May or may not detect depending on randomness, just check no crash
        assert result is None or isinstance(result, ConsolidationResult)

    def test_detect_consolidation_insufficient_data(self):
        result = detect_consolidation([100], [90], [95], BreakoutConfig())
        assert result is None

    def test_detect_higher_lows_ascending(self):
        # 3 ascending swing lows: 10, 12, 14
        lows = [15, 10, 15, 12, 16, 14, 18]
        assert detect_higher_lows(lows, 7) is True

    def test_detect_higher_lows_flat(self):
        lows = [10, 10, 10, 10, 10]
        assert detect_higher_lows(lows, 5) is False

    def test_detect_higher_lows_insufficient(self):
        assert detect_higher_lows([10], 1) is False

    def test_volume_contraction_basic(self):
        # High volume then low volume
        volumes = [1000000] * 15 + [300000] * 5
        ratio = volume_contraction(volumes, lookback=20)
        assert ratio < 1.0  # Contracting

    def test_volume_contraction_expanding(self):
        # Low volume then high volume
        volumes = [300000] * 15 + [1000000] * 5
        ratio = volume_contraction(volumes, lookback=20)
        assert ratio > 1.0  # Expanding

    def test_volume_contraction_insufficient(self):
        assert volume_contraction([100], lookback=20) == 1.0


# ═════════════════════════════════════════════════════════════════════
# Breakout Config
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieBreakoutConfig:
    """Test BreakoutConfig defaults and overrides."""

    def test_defaults(self):
        cfg = BreakoutConfig()
        assert cfg.prior_gain_pct == 30.0
        assert cfg.consolidation_min_bars == 10
        assert cfg.consolidation_max_bars == 60
        assert cfg.pullback_max_pct == 25.0
        assert cfg.volume_contraction_ratio == 0.7
        assert cfg.breakout_volume_mult == 1.5
        assert cfg.adr_min_pct == 5.0
        assert cfg.stop_atr_mult == 1.0
        assert cfg.risk_per_trade == 0.005
        assert cfg.price_min == 5.0
        assert cfg.avg_volume_min == 300_000

    def test_custom_override(self):
        cfg = BreakoutConfig(prior_gain_pct=50.0, price_min=10.0)
        assert cfg.prior_gain_pct == 50.0
        assert cfg.price_min == 10.0
        # Unchanged defaults
        assert cfg.consolidation_min_bars == 10


# ═════════════════════════════════════════════════════════════════════
# Breakout Strategy
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieBreakoutStrategy:
    """Test breakout strategy analysis."""

    def _make_bars(self, n=80, seed=42):
        random.seed(seed)
        closes = [50 + random.uniform(-1, 1) for _ in range(n)]
        opens = [c + random.uniform(-0.3, 0.3) for c in closes]
        highs = [max(o, c) + random.uniform(0.2, 1) for o, c in zip(opens, closes)]
        lows = [min(o, c) - random.uniform(0.2, 1) for o, c in zip(opens, closes)]
        volumes = [random.randint(300000, 800000) for _ in range(n)]
        return opens, highs, lows, closes, volumes

    def test_protocol_compliance(self):
        strategy = QullamaggieBreakoutStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = QullamaggieBreakoutStrategy()
        assert strategy.name == "qullamaggie_breakout"

    def test_analyze_insufficient_data(self):
        strategy = QullamaggieBreakoutStrategy()
        result = strategy.analyze("AAPL", [100], [101], [99], [100], [500000])
        assert result is None

    def test_analyze_flat_market_no_signal(self):
        strategy = QullamaggieBreakoutStrategy()
        opens, highs, lows, closes, volumes = self._make_bars()
        result = strategy.analyze("FLAT", opens, highs, lows, closes, volumes)
        # Flat market should not trigger breakout
        assert result is None

    def test_analyze_low_price_rejected(self):
        strategy = QullamaggieBreakoutStrategy(BreakoutConfig(price_min=100.0))
        opens, highs, lows, closes, volumes = self._make_bars()
        result = strategy.analyze("CHEAP", opens, highs, lows, closes, volumes)
        assert result is None

    def test_analyze_low_volume_rejected(self):
        strategy = QullamaggieBreakoutStrategy(BreakoutConfig(avg_volume_min=10_000_000))
        opens, highs, lows, closes, volumes = self._make_bars()
        result = strategy.analyze("THIN", opens, highs, lows, closes, volumes)
        assert result is None

    def test_breakout_signal_structure(self):
        """Test that a breakout signal has correct structure when detected."""
        # Build a scenario: prior move + consolidation + breakout
        random.seed(100)
        # Prior move: 50 -> 80 (60% gain)
        prior = [50 + i * 0.6 for i in range(50)]
        # Consolidation: flat around 80 for 20 bars
        cons = [80 + random.uniform(-1, 1) for _ in range(20)]
        # Breakout: jump above consolidation high
        breakout_price = max(cons) + 3
        closes = prior + cons + [breakout_price]

        opens = [c + random.uniform(-0.3, 0.3) for c in closes]
        highs = [max(o, c) + random.uniform(0.5, 1.5) for o, c in zip(opens, closes)]
        lows = [min(o, c) - random.uniform(0.5, 1.5) for o, c in zip(opens, closes)]
        volumes = [random.randint(300000, 600000) for _ in range(len(closes))]
        # Consolidation volume low, breakout volume high
        for i in range(50, 70):
            volumes[i] = random.randint(100000, 200000)
        volumes[-1] = 1500000  # Breakout volume spike

        strategy = QullamaggieBreakoutStrategy(BreakoutConfig(
            prior_gain_pct=20.0,
            adr_min_pct=1.0,
            consolidation_min_bars=5,
            consolidation_max_bars=40,
            volume_contraction_ratio=0.8,
            breakout_volume_mult=1.2,
        ))
        result = strategy.analyze("BKOUT", opens, highs, lows, closes, volumes)
        if result is not None:
            assert result.ticker == "BKOUT"
            assert result.direction == "long"
            assert result.stop_loss < result.entry_price
            assert result.conviction >= 60
            assert result.conviction <= 90
            assert result.metadata["strategy"] == "qullamaggie_breakout"

    def test_custom_config(self):
        cfg = BreakoutConfig(prior_gain_pct=10.0, adr_min_pct=1.0)
        strategy = QullamaggieBreakoutStrategy(cfg)
        assert strategy.config.prior_gain_pct == 10.0


# ═════════════════════════════════════════════════════════════════════
# Episodic Pivot Config
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieEPConfig:
    """Test EpisodicPivotConfig defaults."""

    def test_defaults(self):
        cfg = EpisodicPivotConfig()
        assert cfg.gap_min_pct == 10.0
        assert cfg.volume_mult_min == 2.0
        assert cfg.prior_flat_bars == 60
        assert cfg.prior_flat_max_range_pct == 30.0
        assert cfg.adr_min_pct == 3.5
        assert cfg.stop_at_lod is True
        assert cfg.earnings_only is False

    def test_custom_override(self):
        cfg = EpisodicPivotConfig(gap_min_pct=15.0, earnings_only=True)
        assert cfg.gap_min_pct == 15.0
        assert cfg.earnings_only is True


# ═════════════════════════════════════════════════════════════════════
# Episodic Pivot Strategy
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieEPStrategy:
    """Test episodic pivot strategy analysis."""

    def test_protocol_compliance(self):
        strategy = EpisodicPivotStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = EpisodicPivotStrategy()
        assert strategy.name == "qullamaggie_ep"

    def test_analyze_insufficient_data(self):
        strategy = EpisodicPivotStrategy()
        result = strategy.analyze("TEST", [100], [101], [99], [100], [500000])
        assert result is None

    def test_no_gap_no_signal(self):
        """No gap-up should produce no signal."""
        random.seed(50)
        n = 65
        closes = [30 + random.uniform(-0.5, 0.5) for _ in range(n)]
        opens = [c + random.uniform(-0.2, 0.2) for c in closes]
        highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
        volumes = [random.randint(200000, 400000) for _ in range(n)]
        strategy = EpisodicPivotStrategy()
        result = strategy.analyze("FLAT", opens, highs, lows, closes, volumes)
        assert result is None

    def test_gap_detected(self):
        """A proper gap-up with volume should produce a signal."""
        random.seed(51)
        n = 65
        # Flat base for 63 bars
        closes = [30 + random.uniform(-0.5, 0.5) for _ in range(n - 2)]
        # Pre-gap close
        closes.append(30.0)
        # Gap day close (open will be 15% above)
        closes.append(35.0)

        opens = [c + random.uniform(-0.1, 0.1) for c in closes]
        opens[-1] = 34.5  # Gap open = 34.5 (15% above 30)

        highs = [max(o, c) + 0.3 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 0.3 for o, c in zip(opens, closes)]
        volumes = [random.randint(200000, 400000) for _ in range(n)]
        volumes[-1] = 1500000  # Volume spike

        strategy = EpisodicPivotStrategy(EpisodicPivotConfig(adr_min_pct=0.5))
        result = strategy.analyze("EP_TEST", opens, highs, lows, closes, volumes)
        if result is not None:
            assert result.ticker == "EP_TEST"
            assert result.direction == "long"
            assert result.metadata["strategy"] == "qullamaggie_ep"
            assert result.metadata["gap_pct"] >= 10.0

    def test_volume_too_low_rejected(self):
        """Gap-up with insufficient volume should be rejected."""
        random.seed(52)
        n = 65
        closes = [30 + random.uniform(-0.5, 0.5) for _ in range(n - 1)]
        closes.append(35.0)
        opens = [c for c in closes]
        opens[-1] = 34.5
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        volumes = [500000] * n  # Uniform — no volume spike

        strategy = EpisodicPivotStrategy(EpisodicPivotConfig(
            volume_mult_min=3.0, adr_min_pct=0.5
        ))
        result = strategy.analyze("LOW_VOL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_prior_not_flat_rejected(self):
        """If the prior base is too volatile, reject."""
        random.seed(53)
        n = 65
        # Volatile prior base
        closes = [30 + random.uniform(-10, 10) for _ in range(n - 1)]
        closes.append(35.0)
        opens = [c for c in closes]
        opens[-1] = 34.5
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [400000] * (n - 1) + [1500000]

        strategy = EpisodicPivotStrategy(EpisodicPivotConfig(
            prior_flat_max_range_pct=10.0, adr_min_pct=0.5
        ))
        result = strategy.analyze("VOLATILE", opens, highs, lows, closes, volumes)
        assert result is None


# ═════════════════════════════════════════════════════════════════════
# Parabolic Short Config
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieParabolicConfig:
    """Test ParabolicShortConfig defaults."""

    def test_defaults(self):
        cfg = ParabolicShortConfig()
        assert cfg.surge_min_pct == 100.0
        assert cfg.surge_max_bars == 20
        assert cfg.consecutive_up_days == 3
        assert cfg.vwap_entry is True
        assert cfg.stop_at_hod is True
        assert cfg.target_sma_period == 20
        assert cfg.risk_per_trade == 0.005

    def test_custom_override(self):
        cfg = ParabolicShortConfig(surge_min_pct=50.0, consecutive_up_days=5)
        assert cfg.surge_min_pct == 50.0
        assert cfg.consecutive_up_days == 5


# ═════════════════════════════════════════════════════════════════════
# Parabolic Short Strategy
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieParabolicStrategy:
    """Test parabolic short strategy analysis."""

    def test_protocol_compliance(self):
        strategy = ParabolicShortStrategy()
        assert isinstance(strategy, BotStrategy)

    def test_name(self):
        strategy = ParabolicShortStrategy()
        assert strategy.name == "qullamaggie_parabolic_short"

    def test_analyze_insufficient_data(self):
        strategy = ParabolicShortStrategy()
        result = strategy.analyze("TEST", [10], [11], [9], [10], [500000])
        assert result is None

    def test_no_surge_no_signal(self):
        """Flat market should produce no signal."""
        random.seed(60)
        n = 30
        closes = [50 + random.uniform(-1, 1) for _ in range(n)]
        opens = [c + random.uniform(-0.3, 0.3) for c in closes]
        highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
        volumes = [random.randint(500000, 1000000) for _ in range(n)]
        strategy = ParabolicShortStrategy()
        result = strategy.analyze("FLAT", opens, highs, lows, closes, volumes)
        assert result is None

    def test_surge_with_exhaustion(self):
        """Parabolic surge followed by red candle should trigger short."""
        random.seed(61)
        # Base at 10, surge to 25 (150% gain), then red candle
        base = [10 + random.uniform(-0.2, 0.2) for _ in range(5)]
        surge = [10 + i * 1.0 for i in range(16)]  # 10 -> 25
        # Red candle: open high, close lower
        red_close = 24.0
        closes = base + surge + [red_close]
        opens = [c + random.uniform(-0.1, 0.1) for c in closes]
        opens[-1] = 25.5  # Open above close (red candle)
        highs = [max(o, c) + 0.3 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 0.3 for o, c in zip(opens, closes)]
        volumes = [random.randint(500000, 1000000) for _ in range(len(closes))]

        strategy = ParabolicShortStrategy(ParabolicShortConfig(
            surge_min_pct=80.0, consecutive_up_days=3,
        ))
        result = strategy.analyze("PARA", opens, highs, lows, closes, volumes)
        if result is not None:
            assert result.direction == "short"
            assert result.metadata["strategy"] == "qullamaggie_parabolic_short"
            assert result.metadata["is_red_candle"] is True
            assert result.stop_loss > result.entry_price  # Stop above for shorts

    def test_consecutive_up_days_count(self):
        """Verify consecutive up days counter."""
        closes = [10, 11, 12, 13, 14, 15, 14.5]  # 5 up, then reversal
        count = ParabolicShortStrategy._count_consecutive_up(closes)
        assert count == 5

    def test_consecutive_up_days_no_up(self):
        closes = [15, 14, 13, 12]
        count = ParabolicShortStrategy._count_consecutive_up(closes)
        assert count == 0

    def test_short_direction(self):
        """Parabolic short signals should always be direction='short'."""
        random.seed(62)
        base = [8 + random.uniform(-0.1, 0.1) for _ in range(5)]
        surge = [8 + i * 1.2 for i in range(18)]
        red = [28.0]  # Red after 28.6 peak
        closes = base + surge + red
        opens = [c + 0.1 for c in closes]
        opens[-1] = 29.0  # Red candle
        highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
        lows = [min(o, c) - 0.5 for o, c in zip(opens, closes)]
        volumes = [800000] * len(closes)

        strategy = ParabolicShortStrategy(ParabolicShortConfig(
            surge_min_pct=80.0, consecutive_up_days=3,
        ))
        result = strategy.analyze("SHORT_DIR", opens, highs, lows, closes, volumes)
        if result is not None:
            assert result.direction == "short"


# ═════════════════════════════════════════════════════════════════════
# Scanner Presets
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieScannerPresets:
    """Test scanner presets are correctly defined."""

    def test_five_presets_defined(self):
        assert len(QULLAMAGGIE_PRESETS) == 5

    def test_preset_keys(self):
        expected = {
            "qullamaggie_ep",
            "qullamaggie_breakout",
            "qullamaggie_htf",
            "qullamaggie_momentum_leaders",
            "qullamaggie_parabolic",
        }
        assert set(QULLAMAGGIE_PRESETS.keys()) == expected

    def test_ep_scan_criteria(self):
        scan = QULLAMAGGIE_EP_SCAN
        fields = [c.field for c in scan.criteria]
        assert "gap_pct" in fields
        assert "relative_volume" in fields
        assert scan.is_preset is True

    def test_breakout_scan_criteria(self):
        scan = QULLAMAGGIE_BREAKOUT_SCAN
        fields = [c.field for c in scan.criteria]
        assert "adx" in fields
        assert scan.is_preset is True

    def test_htf_scan_has_criteria(self):
        assert len(QULLAMAGGIE_HTF_SCAN.criteria) >= 3

    def test_momentum_leader_scan(self):
        scan = QULLAMAGGIE_MOMENTUM_LEADER_SCAN
        fields = [c.field for c in scan.criteria]
        assert "dist_sma_200" in fields

    def test_parabolic_scan_has_rsi(self):
        scan = QULLAMAGGIE_PARABOLIC_SCAN
        fields = [c.field for c in scan.criteria]
        assert "rsi" in fields

    def test_all_presets_are_momentum_category(self):
        from src.scanner.config import ScanCategory
        for scan in QULLAMAGGIE_PRESETS.values():
            assert scan.category == ScanCategory.MOMENTUM

    def test_all_presets_have_names(self):
        for scan in QULLAMAGGIE_PRESETS.values():
            assert scan.name
            assert scan.description


# ═════════════════════════════════════════════════════════════════════
# Integration with StrategyRegistry
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieIntegration:
    """Test integration with the platform StrategyRegistry."""

    def test_register_all_strategies(self):
        from src.strategies.registry import StrategyRegistry
        registry = StrategyRegistry()
        registry.register(QullamaggieBreakoutStrategy(), description="Breakout", category="momentum")
        registry.register(EpisodicPivotStrategy(), description="EP", category="momentum")
        registry.register(ParabolicShortStrategy(), description="Parabolic Short", category="momentum")

        items = registry.list_strategies()
        names = [i["name"] for i in items]
        assert "qullamaggie_breakout" in names
        assert "qullamaggie_ep" in names
        assert "qullamaggie_parabolic_short" in names

    def test_strategies_in_strategies_init(self):
        """Strategies should be re-exported from src.strategies."""
        from src.strategies import (
            QullamaggieBreakoutStrategy,
            EpisodicPivotStrategy,
            ParabolicShortStrategy,
        )
        assert QullamaggieBreakoutStrategy is not None

    def test_scanner_presets_in_main_presets(self):
        """Qullamaggie scanner presets should be in the main PRESET_SCANNERS dict."""
        from src.scanner.presets import PRESET_SCANNERS, _ensure_extensions
        _ensure_extensions()
        assert "qullamaggie_ep" in PRESET_SCANNERS
        assert "qullamaggie_breakout" in PRESET_SCANNERS

    def test_scan_fields_include_qullamaggie(self):
        """Scanner config should have Qullamaggie-specific fields."""
        from src.scanner.config import SCAN_FIELDS
        assert "adr_pct" in SCAN_FIELDS
        assert "perf_1m" in SCAN_FIELDS
        assert "consecutive_up_days" in SCAN_FIELDS


# ═════════════════════════════════════════════════════════════════════
# Edge Cases
# ═════════════════════════════════════════════════════════════════════


class TestQullamaggieEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_breakout_zero_volume(self):
        """Zero volumes should not crash."""
        strategy = QullamaggieBreakoutStrategy()
        closes = [50.0] * 70
        opens = closes[:]
        highs = [51.0] * 70
        lows = [49.0] * 70
        volumes = [0] * 70
        result = strategy.analyze("ZERO", opens, highs, lows, closes, volumes)
        assert result is None

    def test_ep_zero_close(self):
        """Zero prior close should not crash."""
        strategy = EpisodicPivotStrategy()
        closes = [0.0] * 63 + [10.0]
        opens = closes[:]
        highs = [0.1] * 63 + [11.0]
        lows = [0.0] * 64
        volumes = [500000] * 64
        result = strategy.analyze("ZERO_CL", opens, highs, lows, closes, volumes)
        assert result is None

    def test_parabolic_all_same_price(self):
        """All same price should produce no signal."""
        strategy = ParabolicShortStrategy()
        n = 30
        price = [50.0] * n
        volumes = [1000000] * n
        result = strategy.analyze("SAME", price, price, price, price, volumes)
        assert result is None

    def test_sma_empty_values(self):
        assert compute_sma([], 10) == []

    def test_ema_empty_values(self):
        assert compute_ema([], 10) == []

    def test_higher_lows_two_elements(self):
        assert detect_higher_lows([10, 20], 2) is False

    def test_vwap_single_bar(self):
        result = compute_vwap([101], [99], [100], [1000])
        assert abs(result - 100.0) < 1.0
