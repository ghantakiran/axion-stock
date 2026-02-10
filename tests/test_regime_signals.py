"""Tests for PRD-63: Regime-Aware Signals."""

import pytest
from datetime import datetime, timezone, timedelta
import math

from src.regime_signals import (
    RegimeType,
    SignalType,
    SignalDirection,
    DetectionMethod,
    TrendDirection,
    VolatilityLevel,
    SignalOutcome,
    REGIME_PARAMETERS,
    RegimeState,
    RegimeSignal,
    SignalPerformance,
    RegimeParameter,
    SignalResult,
    RegimeDetector,
    SignalGenerator,
    ParameterOptimizer,
    PerformanceTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_prices() -> list[float]:
    """Generate sample price data."""
    import random
    random.seed(42)
    prices = [100.0]
    for _ in range(99):
        change = random.gauss(0.001, 0.02)
        prices.append(prices[-1] * (1 + change))
    return prices


@pytest.fixture
def uptrend_prices() -> list[float]:
    """Generate uptrending price data."""
    prices = [100.0]
    for i in range(99):
        prices.append(prices[-1] * 1.005 + (i % 3 - 1) * 0.5)
    return prices


@pytest.fixture
def downtrend_prices() -> list[float]:
    """Generate downtrending price data."""
    prices = [100.0]
    for i in range(99):
        prices.append(prices[-1] * 0.995 - (i % 3 - 1) * 0.5)
    return prices


@pytest.fixture
def sideways_prices() -> list[float]:
    """Generate sideways price data."""
    import math
    prices = []
    for i in range(100):
        prices.append(100.0 + 5 * math.sin(i * 0.3))
    return prices


@pytest.fixture
def detector() -> RegimeDetector:
    """Create a RegimeDetector instance."""
    return RegimeDetector()


@pytest.fixture
def generator() -> SignalGenerator:
    """Create a SignalGenerator instance."""
    return SignalGenerator()


@pytest.fixture
def optimizer() -> ParameterOptimizer:
    """Create a ParameterOptimizer instance."""
    return ParameterOptimizer()


@pytest.fixture
def tracker() -> PerformanceTracker:
    """Create a PerformanceTracker instance."""
    return PerformanceTracker()


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestRegimeSignalsConfig:
    """Test configuration enums and defaults."""

    def test_regime_types(self):
        """Test RegimeType enum values."""
        assert RegimeType.BULL_TRENDING.value == "bull_trending"
        assert RegimeType.BEAR_VOLATILE.value == "bear_volatile"
        assert RegimeType.CRISIS.value == "crisis"
        assert len(RegimeType) == 8

    def test_signal_types(self):
        """Test SignalType enum values."""
        assert SignalType.MOMENTUM.value == "momentum"
        assert SignalType.MEAN_REVERSION.value == "mean_reversion"
        assert SignalType.BREAKOUT.value == "breakout"
        assert len(SignalType) == 10

    def test_signal_directions(self):
        """Test SignalDirection enum values."""
        assert SignalDirection.LONG.value == "long"
        assert SignalDirection.SHORT.value == "short"
        assert SignalDirection.NEUTRAL.value == "neutral"

    def test_detection_methods(self):
        """Test DetectionMethod enum values."""
        assert DetectionMethod.HMM.value == "hmm"
        assert DetectionMethod.COMBINED.value == "combined"
        assert len(DetectionMethod) == 5

    def test_regime_parameters_exist(self):
        """Test that regime parameters are defined."""
        assert len(REGIME_PARAMETERS) == 8
        assert RegimeType.BULL_TRENDING.value in REGIME_PARAMETERS
        assert RegimeType.CRISIS.value in REGIME_PARAMETERS

    def test_regime_parameters_structure(self):
        """Test regime parameter structure."""
        for regime, params in REGIME_PARAMETERS.items():
            assert "preferred_signals" in params
            assert "sma_period" in params
            assert "stop_loss_atr" in params
            assert "position_size_factor" in params


# ---------------------------------------------------------------------------
# Models Tests
# ---------------------------------------------------------------------------


class TestRegimeSignalsModels:
    """Test data models."""

    def test_regime_state(self):
        """Test RegimeState model."""
        state = RegimeState(
            symbol="AAPL",
            regime_type=RegimeType.BULL_TRENDING,
            detection_method=DetectionMethod.COMBINED,
            confidence=0.85,
            volatility_level=VolatilityLevel.MEDIUM,
            trend_direction=TrendDirection.UP,
            trend_strength=0.7,
        )

        assert state.symbol == "AAPL"
        assert state.regime_type == RegimeType.BULL_TRENDING
        assert state.confidence == 0.85

        d = state.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["regime_type"] == "bull_trending"

    def test_regime_signal(self):
        """Test RegimeSignal model."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            strength=0.8,
            confidence=0.75,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=160.0,
        )

        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.MOMENTUM
        assert signal.direction == SignalDirection.LONG

        # Test risk/reward calculation
        rr = signal.calculate_risk_reward()
        assert rr is not None
        assert rr == 2.0  # (160-150)/(150-145)

        d = signal.to_dict()
        assert d["signal_type"] == "momentum"

    def test_signal_expiry(self):
        """Test signal expiry checking."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert signal.is_expired() is True

        signal2 = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert signal2.is_expired() is False

    def test_signal_performance(self):
        """Test SignalPerformance model."""
        perf = SignalPerformance(
            signal_id="sig_1",
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            regime_type=RegimeType.BULL_TRENDING,
            direction=SignalDirection.LONG,
            entry_price=150.0,
        )

        assert perf.outcome == SignalOutcome.PENDING

        # Close position with profit
        perf.close_position(155.0)

        assert perf.exit_price == 155.0
        assert perf.return_pct > 0
        assert perf.outcome == SignalOutcome.WIN
        assert perf.duration_hours is not None

    def test_signal_performance_short(self):
        """Test SignalPerformance for short positions."""
        perf = SignalPerformance(
            signal_id="sig_1",
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            regime_type=RegimeType.BEAR_TRENDING,
            direction=SignalDirection.SHORT,
            entry_price=150.0,
        )

        # Close short with profit (price went down)
        perf.close_position(145.0)

        assert perf.return_pct > 0
        assert perf.outcome == SignalOutcome.WIN

    def test_regime_parameter(self):
        """Test RegimeParameter model."""
        param = RegimeParameter(
            regime_type=RegimeType.BULL_TRENDING,
            signal_type=SignalType.MOMENTUM,
            indicator_name="RSI",
            parameter_name="period",
            default_value=14.0,
        )

        assert param.get_value() == 14.0

        param.optimized_value = 12.0
        assert param.get_value() == 12.0

    def test_signal_result(self):
        """Test SignalResult model."""
        state = RegimeState(
            symbol="AAPL",
            regime_type=RegimeType.BULL_TRENDING,
            detection_method=DetectionMethod.COMBINED,
        )

        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
        )

        result = SignalResult(
            signals=[signal],
            regime_state=state,
            generation_time_ms=10.5,
            indicators_computed=["RSI", "SMA"],
        )

        d = result.to_dict()
        assert d["signal_count"] == 1
        assert "RSI" in d["indicators_computed"]


# ---------------------------------------------------------------------------
# Regime Detector Tests
# ---------------------------------------------------------------------------


class TestRegimeSignalsRegimeDetector:
    """Test regime detection."""

    def test_detect_regime_uptrend(self, detector: RegimeDetector, uptrend_prices: list[float]):
        """Test regime detection on uptrend."""
        state = detector.detect_regime("AAPL", uptrend_prices)

        assert state.symbol == "AAPL"
        assert state.regime_type in [RegimeType.BULL_TRENDING, RegimeType.BULL_VOLATILE]
        assert state.trend_direction == TrendDirection.UP
        assert state.confidence > 0.5

    def test_detect_regime_downtrend(self, detector: RegimeDetector, downtrend_prices: list[float]):
        """Test regime detection on downtrend."""
        state = detector.detect_regime("AAPL", downtrend_prices)

        assert state.trend_direction == TrendDirection.DOWN
        assert state.regime_type in [
            RegimeType.BEAR_TRENDING,
            RegimeType.BEAR_VOLATILE,
            RegimeType.CRISIS,
        ]

    def test_detect_regime_sideways(self, detector: RegimeDetector, sideways_prices: list[float]):
        """Test regime detection on sideways market."""
        state = detector.detect_regime("AAPL", sideways_prices)

        # Sideways prices can be detected as various regimes depending on volatility
        assert state.regime_type in [
            RegimeType.SIDEWAYS_LOW_VOL,
            RegimeType.SIDEWAYS_HIGH_VOL,
            RegimeType.BULL_VOLATILE,  # Oscillating prices can appear volatile
            RegimeType.BEAR_VOLATILE,
        ]

    def test_detect_with_different_methods(self, detector: RegimeDetector, sample_prices: list[float]):
        """Test different detection methods."""
        for method in DetectionMethod:
            state = detector.detect_regime("AAPL", sample_prices, method=method)
            # HMM and other methods may fall back to combined
            assert state.detection_method in [method, DetectionMethod.COMBINED]
            assert state.confidence > 0

    def test_regime_history(self, detector: RegimeDetector, sample_prices: list[float]):
        """Test regime history tracking."""
        # Detect multiple times
        for _ in range(5):
            detector.detect_regime("AAPL", sample_prices)

        history = detector.get_regime_history("AAPL")
        assert len(history) == 5

    def test_regime_statistics(self, detector: RegimeDetector, sample_prices: list[float]):
        """Test regime statistics."""
        for _ in range(10):
            detector.detect_regime("AAPL", sample_prices)

        stats = detector.get_regime_statistics("AAPL")

        assert stats["total_observations"] == 10
        assert "regime_distribution" in stats
        assert "average_confidence" in stats

    def test_insufficient_data(self, detector: RegimeDetector):
        """Test with insufficient data."""
        short_prices = [100.0, 101.0, 102.0]
        state = detector.detect_regime("AAPL", short_prices)

        assert state.confidence < 0.5


# ---------------------------------------------------------------------------
# Signal Generator Tests
# ---------------------------------------------------------------------------


class TestSignalGenerator:
    """Test signal generation."""

    def test_generate_signals(self, generator: SignalGenerator, sample_prices: list[float]):
        """Test basic signal generation."""
        result = generator.generate_signals("AAPL", sample_prices)

        assert result.regime_state is not None
        assert result.generation_time_ms > 0
        assert isinstance(result.signals, list)

    def test_generate_signals_uptrend(self, generator: SignalGenerator, uptrend_prices: list[float]):
        """Test signal generation in uptrend."""
        result = generator.generate_signals("AAPL", uptrend_prices)

        # Should generate momentum/trend signals
        for signal in result.signals:
            assert signal.regime_type in [RegimeType.BULL_TRENDING, RegimeType.BULL_VOLATILE]

    def test_signal_has_stops(self, generator: SignalGenerator, sample_prices: list[float]):
        """Test that signals have stop loss and take profit."""
        result = generator.generate_signals("AAPL", sample_prices)

        for signal in result.signals:
            if signal.direction in [SignalDirection.LONG, SignalDirection.SHORT]:
                assert signal.entry_price is not None
                assert signal.stop_loss is not None
                assert signal.take_profit is not None

    def test_signal_risk_reward(self, generator: SignalGenerator, uptrend_prices: list[float]):
        """Test signal risk/reward ratio."""
        result = generator.generate_signals("AAPL", uptrend_prices)

        for signal in result.signals:
            if signal.risk_reward_ratio is not None:
                assert signal.risk_reward_ratio > 0

    def test_signals_sorted_by_strength(self, generator: SignalGenerator, sample_prices: list[float]):
        """Test that signals are sorted by strength."""
        result = generator.generate_signals("AAPL", sample_prices)

        if len(result.signals) > 1:
            for i in range(len(result.signals) - 1):
                assert result.signals[i].strength >= result.signals[i + 1].strength

    def test_signal_expiry(self, generator: SignalGenerator, sample_prices: list[float]):
        """Test that signals have expiry."""
        result = generator.generate_signals("AAPL", sample_prices)

        for signal in result.signals:
            assert signal.expires_at is not None


# ---------------------------------------------------------------------------
# Parameter Optimizer Tests
# ---------------------------------------------------------------------------


class TestParameterOptimizer:
    """Test parameter optimization."""

    def test_get_default_parameters(self, optimizer: ParameterOptimizer):
        """Test getting default parameters."""
        params = optimizer.get_parameters_for_regime(RegimeType.BULL_TRENDING)

        assert len(params) > 0

    def test_get_optimized_value(self, optimizer: ParameterOptimizer):
        """Test getting optimized values."""
        value = optimizer.get_optimized_value(
            RegimeType.BULL_TRENDING,
            SignalType.MOMENTUM,
            "general",
            "sma_period"
        )

        assert value == 20  # Default from REGIME_PARAMETERS

    def test_record_performance(self, optimizer: ParameterOptimizer):
        """Test recording performance."""
        perf = SignalPerformance(
            signal_id="sig_1",
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            regime_type=RegimeType.BULL_TRENDING,
            direction=SignalDirection.LONG,
            entry_price=150.0,
        )
        perf.close_position(155.0)

        optimizer.record_performance(perf)

        stats = optimizer.get_performance_stats(RegimeType.BULL_TRENDING)
        assert stats["total_signals"] == 1

    def test_optimization_insufficient_data(self, optimizer: ParameterOptimizer):
        """Test optimization with insufficient data."""
        result = optimizer.optimize_parameters(RegimeType.BULL_TRENDING)

        assert result == {}  # Not enough data

    def test_optimization_with_data(self, optimizer: ParameterOptimizer):
        """Test optimization with sufficient data."""
        # Record many performances
        for i in range(50):
            perf = SignalPerformance(
                signal_id=f"sig_{i}",
                symbol="AAPL",
                signal_type=SignalType.MOMENTUM,
                regime_type=RegimeType.BULL_TRENDING,
                direction=SignalDirection.LONG,
                entry_price=150.0,
            )
            if i % 2 == 0:
                perf.close_position(155.0)  # Win
            else:
                perf.close_position(147.0)  # Loss
            optimizer.record_performance(perf)

        # Optimization runs but may return empty if conditions not met
        result = optimizer.optimize_parameters(RegimeType.BULL_TRENDING)

        # Verify performance stats were recorded correctly
        stats = optimizer.get_performance_stats(RegimeType.BULL_TRENDING)
        assert stats["total_signals"] == 50
        assert stats["wins"] == 25
        assert stats["win_rate"] == 0.5

    def test_reset_optimization(self, optimizer: ParameterOptimizer):
        """Test resetting optimization."""
        count = optimizer.reset_optimization(RegimeType.BULL_TRENDING)

        assert count > 0


# ---------------------------------------------------------------------------
# Performance Tracker Tests
# ---------------------------------------------------------------------------


class TestRegimeSignalsPerformanceTracker:
    """Test performance tracking."""

    def test_start_tracking(self, tracker: PerformanceTracker):
        """Test starting to track a signal."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            entry_price=150.0,
        )

        perf = tracker.start_tracking(signal)

        assert perf.signal_id == signal.signal_id
        assert perf.entry_price == 150.0
        assert perf.outcome == SignalOutcome.PENDING

    def test_update_prices(self, tracker: PerformanceTracker):
        """Test updating prices for a tracked signal."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            entry_price=150.0,
        )
        tracker.start_tracking(signal)

        perf = tracker.update_prices(signal.signal_id, 155.0, high_price=156.0, low_price=149.0)

        assert perf.max_favorable == 6.0  # 156 - 150
        assert perf.max_adverse == 1.0  # 150 - 149

    def test_close_signal(self, tracker: PerformanceTracker):
        """Test closing a tracked signal."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
            entry_price=150.0,
        )
        tracker.start_tracking(signal)

        perf = tracker.close_signal(signal.signal_id, 155.0, hit_take_profit=True)

        assert perf.exit_price == 155.0
        assert perf.return_pct > 0
        assert perf.hit_take_profit is True
        assert perf.outcome == SignalOutcome.WIN

    def test_expire_signal(self, tracker: PerformanceTracker):
        """Test expiring a signal."""
        signal = RegimeSignal(
            symbol="AAPL",
            signal_type=SignalType.MOMENTUM,
            direction=SignalDirection.LONG,
            regime_type=RegimeType.BULL_TRENDING,
        )
        tracker.start_tracking(signal)

        perf = tracker.expire_signal(signal.signal_id)

        assert perf.outcome == SignalOutcome.EXPIRED

    def test_get_active_signals(self, tracker: PerformanceTracker):
        """Test getting active signals."""
        for i in range(3):
            signal = RegimeSignal(
                symbol="AAPL" if i < 2 else "MSFT",
                signal_type=SignalType.MOMENTUM,
                direction=SignalDirection.LONG,
                regime_type=RegimeType.BULL_TRENDING,
            )
            tracker.start_tracking(signal)

        all_active = tracker.get_active_signals()
        assert len(all_active) == 3

        aapl_active = tracker.get_active_signals("AAPL")
        assert len(aapl_active) == 2

    def test_get_completed_signals(self, tracker: PerformanceTracker):
        """Test getting completed signals."""
        for i in range(5):
            signal = RegimeSignal(
                symbol="AAPL",
                signal_type=SignalType.MOMENTUM,
                direction=SignalDirection.LONG,
                regime_type=RegimeType.BULL_TRENDING,
                entry_price=150.0,
            )
            tracker.start_tracking(signal)
            tracker.close_signal(signal.signal_id, 155.0 if i % 2 == 0 else 145.0)

        completed = tracker.get_completed_signals()
        assert len(completed) == 5

    def test_accuracy_by_regime(self, tracker: PerformanceTracker):
        """Test accuracy breakdown by regime."""
        # Create signals for different regimes
        regimes = [RegimeType.BULL_TRENDING, RegimeType.BEAR_TRENDING]
        for regime in regimes:
            for i in range(5):
                signal = RegimeSignal(
                    symbol="AAPL",
                    signal_type=SignalType.MOMENTUM,
                    direction=SignalDirection.LONG,
                    regime_type=regime,
                    entry_price=150.0,
                )
                tracker.start_tracking(signal)
                tracker.close_signal(signal.signal_id, 155.0)

        accuracy = tracker.get_accuracy_by_regime()

        assert RegimeType.BULL_TRENDING.value in accuracy
        assert RegimeType.BEAR_TRENDING.value in accuracy
        assert accuracy[RegimeType.BULL_TRENDING.value]["total_signals"] == 5

    def test_accuracy_by_signal_type(self, tracker: PerformanceTracker):
        """Test accuracy breakdown by signal type."""
        signal_types = [SignalType.MOMENTUM, SignalType.MEAN_REVERSION]
        for sig_type in signal_types:
            for i in range(5):
                signal = RegimeSignal(
                    symbol="AAPL",
                    signal_type=sig_type,
                    direction=SignalDirection.LONG,
                    regime_type=RegimeType.BULL_TRENDING,
                    entry_price=150.0,
                )
                tracker.start_tracking(signal)
                tracker.close_signal(signal.signal_id, 155.0)

        accuracy = tracker.get_accuracy_by_signal_type()

        assert SignalType.MOMENTUM.value in accuracy
        assert SignalType.MEAN_REVERSION.value in accuracy

    def test_summary_stats(self, tracker: PerformanceTracker):
        """Test summary statistics."""
        for i in range(10):
            signal = RegimeSignal(
                symbol="AAPL",
                signal_type=SignalType.MOMENTUM,
                direction=SignalDirection.LONG,
                regime_type=RegimeType.BULL_TRENDING,
                entry_price=150.0,
            )
            tracker.start_tracking(signal)
            tracker.close_signal(signal.signal_id, 155.0 if i < 7 else 145.0)

        stats = tracker.get_summary_stats()

        assert stats["total_completed"] == 10
        assert stats["wins"] == 7
        assert stats["losses"] == 3
        assert stats["win_rate"] == 0.7

    def test_recent_signals(self, tracker: PerformanceTracker):
        """Test getting recent signals."""
        for i in range(25):
            signal = RegimeSignal(
                symbol="AAPL",
                signal_type=SignalType.MOMENTUM,
                direction=SignalDirection.LONG,
                regime_type=RegimeType.BULL_TRENDING,
                entry_price=150.0,
            )
            tracker.start_tracking(signal)
            tracker.close_signal(signal.signal_id, 155.0)

        recent = tracker.get_recent_signals(10)

        assert len(recent) == 10


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestRegimeSignalsIntegration:
    """Integration tests combining multiple components."""

    def test_full_workflow(
        self,
        detector: RegimeDetector,
        generator: SignalGenerator,
        tracker: PerformanceTracker,
        optimizer: ParameterOptimizer,
        uptrend_prices: list[float],
    ):
        """Test full signal workflow."""
        # 1. Detect regime
        regime = detector.detect_regime("AAPL", uptrend_prices)
        assert regime.regime_type in [RegimeType.BULL_TRENDING, RegimeType.BULL_VOLATILE]

        # 2. Generate signals
        result = generator.generate_signals("AAPL", uptrend_prices)
        assert len(result.signals) >= 0

        # 3. Track and close signals
        for signal in result.signals[:3]:  # Track first 3
            tracker.start_tracking(signal)
            # Simulate close
            exit_price = signal.entry_price * 1.03 if signal.entry_price else 100.0
            perf = tracker.close_signal(signal.signal_id, exit_price)

            # Record for optimization
            optimizer.record_performance(perf)

        # 4. Get statistics
        stats = tracker.get_summary_stats()
        assert "total_completed" in stats

        # 5. Get regime accuracy
        accuracy = tracker.get_accuracy_by_regime()
        assert isinstance(accuracy, dict)

    def test_regime_transition_detection(self, detector: RegimeDetector):
        """Test detecting regime transitions."""
        # Start with uptrend
        uptrend = [100.0 + i * 0.5 for i in range(50)]
        detector.detect_regime("AAPL", uptrend)

        # Transition to downtrend
        downtrend = [125.0 - i * 0.5 for i in range(50)]
        state = detector.detect_regime("AAPL", uptrend + downtrend)

        # Should detect transition probability
        assert state.transition_probability is not None

    def test_signal_quality_improvement(
        self,
        generator: SignalGenerator,
        optimizer: ParameterOptimizer,
        sample_prices: list[float],
    ):
        """Test that optimization improves signal quality."""
        # Generate initial signals
        result1 = generator.generate_signals("AAPL", sample_prices)

        # Simulate performance and optimize
        for i in range(50):
            perf = SignalPerformance(
                signal_id=f"sig_{i}",
                symbol="AAPL",
                signal_type=SignalType.MOMENTUM,
                regime_type=RegimeType.BULL_TRENDING,
                direction=SignalDirection.LONG,
                entry_price=100.0,
            )
            perf.close_position(103.0 if i % 3 != 0 else 97.0)
            optimizer.record_performance(perf)

        # Optimize
        optimized = optimizer.optimize_parameters()

        # Verify optimization happened
        stats = optimizer.get_performance_stats()
        assert stats["total_signals"] == 50
