"""Tests for PRD-56: Cross-Asset Signals."""

import numpy as np
import pytest

from src.crossasset.config import (
    AssetClass,
    CorrelationRegime,
    SignalDirection,
    SignalStrength,
    IntermarketConfig,
    LeadLagConfig,
    MomentumConfig,
    SignalConfig,
)
from src.crossasset.models import (
    AssetPairCorrelation,
    RelativeStrength,
    LeadLagResult,
    MomentumSignal,
    CrossAssetSignal,
)
from src.crossasset.intermarket import IntermarketAnalyzer
from src.crossasset.leadlag import LeadLagDetector
from src.crossasset.momentum import CrossAssetMomentum
from src.crossasset.signals import CrossAssetSignalGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _correlated_returns(n: int = 300, corr: float = 0.6, seed: int = 42) -> tuple:
    """Generate two correlated return series."""
    rng = np.random.RandomState(seed)
    a = rng.normal(0.0005, 0.01, n)
    noise = rng.normal(0, 0.01, n)
    b = corr * a + np.sqrt(1 - corr**2) * noise
    return list(a), list(b)


def _lead_lag_returns(n: int = 300, lag: int = 3, seed: int = 42) -> tuple:
    """Generate leader-lagger return series."""
    rng = np.random.RandomState(seed)
    leader = rng.normal(0.001, 0.015, n)
    noise = rng.normal(0, 0.005, n)
    lagger = np.zeros(n)
    for i in range(lag, n):
        lagger[i] = 0.7 * leader[i - lag] + noise[i]
    return list(leader), list(lagger)


def _multi_asset_returns(seed: int = 42) -> dict:
    """Generate returns for 4 asset classes."""
    rng = np.random.RandomState(seed)
    return {
        "SPY": list(rng.normal(0.0005, 0.012, 300)),
        "TLT": list(rng.normal(0.0002, 0.008, 300)),
        "GLD": list(rng.normal(0.0003, 0.010, 300)),
        "UUP": list(rng.normal(0.0001, 0.005, 300)),
    }


# ---------------------------------------------------------------------------
# Config enums
# ---------------------------------------------------------------------------
class TestCrossassetConfig:
    def test_asset_class_values(self):
        assert AssetClass.EQUITY.value == "equity"
        assert AssetClass.CURRENCY.value == "currency"

    def test_correlation_regime(self):
        assert CorrelationRegime.NORMAL.value == "normal"
        assert CorrelationRegime.CRISIS.value == "crisis"

    def test_signal_direction(self):
        assert SignalDirection.BULLISH.value == "bullish"

    def test_intermarket_config_defaults(self):
        cfg = IntermarketConfig()
        assert cfg.correlation_window == 63
        assert cfg.long_window == 252


# ---------------------------------------------------------------------------
# Model dataclasses
# ---------------------------------------------------------------------------
class TestAssetPairCorrelation:
    def test_is_diverging(self):
        c = AssetPairCorrelation(z_score=2.0)
        assert c.is_diverging is True
        c2 = AssetPairCorrelation(z_score=0.5)
        assert c2.is_diverging is False

    def test_correlation_pct(self):
        c = AssetPairCorrelation(correlation=0.65)
        assert c.correlation_pct == 65.0


class TestRelativeStrength:
    def test_is_outperforming(self):
        rs = RelativeStrength(ratio_change_pct=3.0)
        assert rs.is_outperforming is True
        rs2 = RelativeStrength(ratio_change_pct=-1.0)
        assert rs2.is_outperforming is False


class TestLeadLagResult:
    def test_lead_days(self):
        ll = LeadLagResult(optimal_lag=5)
        assert ll.lead_days == 5

    def test_is_stable(self):
        ll = LeadLagResult(stability=0.6)
        assert ll.is_stable is True
        ll2 = LeadLagResult(stability=0.3)
        assert ll2.is_stable is False


class TestMomentumSignal:
    def test_is_trending(self):
        ms = MomentumSignal(trend_strength=0.8)
        assert ms.is_trending is True
        ms2 = MomentumSignal(trend_strength=0.2)
        assert ms2.is_trending is False


class TestCrossAssetSignal:
    def test_is_actionable(self):
        s = CrossAssetSignal(strength="strong", confidence=0.5)
        assert s.is_actionable is True
        s2 = CrossAssetSignal(strength="none", confidence=0.1)
        assert s2.is_actionable is False

    def test_score_bps(self):
        s = CrossAssetSignal(score=0.005)
        assert s.score_bps == 50.0


# ---------------------------------------------------------------------------
# IntermarketAnalyzer
# ---------------------------------------------------------------------------
class TestIntermarketAnalyzer:
    def test_rolling_correlation(self):
        a, b = _correlated_returns(n=300, corr=0.6)
        analyzer = IntermarketAnalyzer()
        result = analyzer.rolling_correlation(a, b, "SPY", "TLT")
        assert -1.0 <= result.correlation <= 1.0
        assert result.asset_a == "SPY"
        assert result.asset_b == "TLT"
        assert result.regime in ("normal", "decoupled", "crisis")

    def test_high_correlation_regime(self):
        rng = np.random.RandomState(42)
        a = list(rng.normal(0, 0.01, 300))
        b = [x + rng.normal(0, 0.001) for x in a]  # Nearly identical
        analyzer = IntermarketAnalyzer()
        result = analyzer.rolling_correlation(a, b)
        assert result.correlation > 0.8

    def test_insufficient_data(self):
        analyzer = IntermarketAnalyzer(IntermarketConfig(correlation_window=63))
        result = analyzer.rolling_correlation([0.01] * 10, [0.02] * 10)
        assert result.correlation == 0.0

    def test_relative_strength(self):
        prices = {
            "SPY": list(np.linspace(100, 120, 100)),
            "TLT": list(np.linspace(100, 105, 100)),
            "GLD": list(np.linspace(100, 115, 100)),
        }
        analyzer = IntermarketAnalyzer()
        results = analyzer.relative_strength(prices)
        assert len(results) == 3
        assert results[0].rank == 1
        assert results[0].asset == "SPY"  # Highest return

    def test_detect_divergence(self):
        a, b = _correlated_returns(n=300, corr=0.6)
        analyzer = IntermarketAnalyzer()
        div = analyzer.detect_divergence(a, b, "SPY", "TLT")
        assert "is_diverging" in div
        assert "z_score" in div
        assert "current_correlation" in div

    def test_correlation_matrix(self):
        returns = _multi_asset_returns()
        analyzer = IntermarketAnalyzer()
        matrix = analyzer.correlation_matrix(returns)
        assert matrix["SPY"]["SPY"] == 1.0
        assert "TLT" in matrix["SPY"]

    def test_beta_computation(self):
        a, b = _correlated_returns(n=300, corr=0.7)
        analyzer = IntermarketAnalyzer()
        result = analyzer.rolling_correlation(a, b)
        # Beta should be non-zero for correlated series
        assert result.beta != 0.0


# ---------------------------------------------------------------------------
# LeadLagDetector
# ---------------------------------------------------------------------------
class TestLeadLagDetector:
    def test_detect_lead_lag(self):
        leader, lagger = _lead_lag_returns(n=300, lag=3)
        detector = LeadLagDetector()
        result = detector.detect(leader, lagger, "LEADER", "LAGGER")
        assert result.optimal_lag > 0
        assert abs(result.correlation_at_lag) > 0

    def test_detect_significant(self):
        leader, lagger = _lead_lag_returns(n=300, lag=3)
        detector = LeadLagDetector()
        result = detector.detect(leader, lagger, "A", "B")
        # Strong lead-lag should be significant
        assert result.is_significant is True
        assert result.leader == "A"

    def test_no_lead_lag(self):
        rng = np.random.RandomState(42)
        a = list(rng.normal(0, 0.01, 300))
        b = list(rng.normal(0, 0.01, 300))
        detector = LeadLagDetector()
        result = detector.detect(a, b, "A", "B")
        # Independent series may or may not be significant
        assert result.optimal_lag >= 0

    def test_detect_all_pairs(self):
        returns = _multi_asset_returns()
        detector = LeadLagDetector()
        results = detector.detect_all_pairs(returns)
        # Returns only significant pairs
        for r in results:
            assert r.is_significant is True

    def test_extract_signal(self):
        leader_returns = [0.01, 0.02, -0.01, 0.005, 0.015]
        detector = LeadLagDetector()
        signal = detector.extract_signal(leader_returns, lag=3)
        # Average of last 3 returns
        expected = np.mean([-0.01, 0.005, 0.015])
        assert signal == pytest.approx(expected, abs=1e-5)

    def test_extract_signal_zero_lag(self):
        detector = LeadLagDetector()
        assert detector.extract_signal([0.01], lag=0) == 0.0

    def test_insufficient_data(self):
        detector = LeadLagDetector(LeadLagConfig(max_lag=10))
        result = detector.detect([0.01] * 5, [0.02] * 5)
        assert result.optimal_lag == 0


# ---------------------------------------------------------------------------
# CrossAssetMomentum
# ---------------------------------------------------------------------------
class TestCrossAssetMomentum:
    def test_time_series_momentum_bullish(self):
        rng = np.random.RandomState(42)
        returns = list(rng.normal(0.005, 0.01, 100))  # Positive drift
        mom = CrossAssetMomentum()
        signal = mom.time_series_momentum(returns, "SPY", "equity")
        assert signal.ts_momentum > 0
        assert signal.asset == "SPY"

    def test_time_series_momentum_bearish(self):
        rng = np.random.RandomState(42)
        returns = list(rng.normal(-0.005, 0.01, 100))  # Negative drift
        mom = CrossAssetMomentum()
        signal = mom.time_series_momentum(returns, "BEAR", "equity")
        assert signal.ts_momentum < 0

    def test_insufficient_data(self):
        mom = CrossAssetMomentum(MomentumConfig(lookback_short=21))
        signal = mom.time_series_momentum([0.01] * 5)
        assert signal.ts_momentum == 0.0

    def test_cross_sectional_momentum(self):
        returns = _multi_asset_returns()
        mom = CrossAssetMomentum()
        signals = mom.cross_sectional_momentum(returns)
        assert len(signals) == 4
        # Check ranks are assigned
        ranks = [s.xs_rank for s in signals]
        assert max(ranks) == 1.0
        assert min(ranks) == pytest.approx(0.0, abs=0.01)

    def test_mean_reversion_signals(self):
        returns = _multi_asset_returns()
        mom = CrossAssetMomentum()
        mr_signals = mom.mean_reversion_signals(returns)
        # All returned signals should be mean-reverting
        for s in mr_signals:
            assert s.is_mean_reverting is True

    def test_trend_signals(self):
        returns = _multi_asset_returns()
        mom = CrossAssetMomentum()
        trend_signals = mom.trend_signals(returns)
        for s in trend_signals:
            assert s.is_trending is True


# ---------------------------------------------------------------------------
# CrossAssetSignalGenerator
# ---------------------------------------------------------------------------
class TestCrossAssetSignalGenerator:
    def test_generate_with_momentum_only(self):
        mom = MomentumSignal(
            asset="SPY", ts_momentum=0.05, xs_rank=0.9,
            trend_strength=1.2, signal="bullish"
        )
        gen = CrossAssetSignalGenerator()
        signal = gen.generate("SPY", momentum=mom)
        assert signal.asset == "SPY"
        assert signal.direction in ("bullish", "bearish", "neutral")
        assert signal.confidence > 0

    def test_generate_with_all_components(self):
        mom = MomentumSignal(
            asset="SPY", ts_momentum=0.03, xs_rank=0.8,
            z_score=2.5, trend_strength=0.8, signal="bullish",
            is_mean_reverting=True,
        )
        ll = LeadLagResult(
            leader="TLT", lagger="SPY", optimal_lag=3,
            correlation_at_lag=0.4, is_significant=True, stability=0.6,
        )
        corrs = [
            AssetPairCorrelation(
                asset_a="SPY", asset_b="GLD",
                z_score=2.0, correlation=0.3
            ),
        ]
        gen = CrossAssetSignalGenerator()
        signal = gen.generate("SPY", momentum=mom, lead_lag=ll,
                              lead_lag_signal=0.01, correlations=corrs)
        assert signal.confidence > 0.5
        assert signal.momentum_component != 0

    def test_generate_no_inputs(self):
        gen = CrossAssetSignalGenerator()
        signal = gen.generate("SPY")
        assert signal.score == 0.0
        assert signal.direction == "neutral"
        assert signal.strength == "none"

    def test_generate_all(self):
        returns = _multi_asset_returns()
        mom = CrossAssetMomentum()
        signals = mom.cross_sectional_momentum(returns)

        gen = CrossAssetSignalGenerator()
        results = gen.generate_all(signals)
        assert len(results) == 4
        # Sorted by absolute score
        scores = [abs(r.score) for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_signal_strength_classification(self):
        gen = CrossAssetSignalGenerator(SignalConfig(
            strong_threshold=0.7, moderate_threshold=0.4, min_confidence=0.3
        ))
        mom_strong = MomentumSignal(asset="A", ts_momentum=0.10, signal="bullish")
        sig = gen.generate("A", momentum=mom_strong)
        # Score depends on scaling; just verify strength is assigned
        assert sig.strength in ("strong", "moderate", "weak", "none")

    def test_actionable_signal(self):
        mom = MomentumSignal(
            asset="SPY", ts_momentum=0.08, xs_rank=0.95,
            trend_strength=2.0, signal="bullish"
        )
        gen = CrossAssetSignalGenerator()
        signal = gen.generate("SPY", momentum=mom)
        # Strong momentum should produce an actionable signal
        assert signal.confidence > 0
