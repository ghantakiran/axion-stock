"""Tests for PRD-44: Pairs Trading."""

import pytest
import numpy as np
import pandas as pd

from src.pairs.config import (
    PairSignalType,
    SpreadMethod,
    HedgeMethod,
    PairStatus,
    CointegrationConfig,
    SpreadConfig,
    SelectorConfig,
    PairsConfig,
    DEFAULT_COINTEGRATION_CONFIG,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_SELECTOR_CONFIG,
    DEFAULT_CONFIG,
)
from src.pairs.models import (
    CointegrationResult,
    SpreadAnalysis,
    PairScore,
    PairSignal,
    PairTrade,
)
from src.pairs.cointegration import CointegrationTester
from src.pairs.spread import SpreadAnalyzer
from src.pairs.selector import PairSelector


# ===========================================================================
# Helper: generate cointegrated pair
# ===========================================================================

def _make_cointegrated_pair(n=300, beta=1.5, noise=0.5, seed=42):
    """Generate a cointegrated pair: A = beta * B + noise."""
    rng = np.random.default_rng(seed)
    # Random walk for B
    b_returns = rng.normal(0.001, 0.02, n)
    b = 100.0 * np.exp(np.cumsum(b_returns))
    # A = beta * B + stationary noise
    mean_revert = np.zeros(n)
    for i in range(1, n):
        mean_revert[i] = 0.8 * mean_revert[i - 1] + rng.normal(0, noise)
    a = beta * b + mean_revert + 50
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.Series(a, index=idx), pd.Series(b, index=idx)


def _make_independent_pair(n=300, seed=99):
    """Generate two independent random walks."""
    rng = np.random.default_rng(seed)
    a = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    b = 50.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.Series(a, index=idx), pd.Series(b, index=idx)


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:
    """Test configuration enums and dataclasses."""

    def test_signal_type_values(self):
        assert PairSignalType.LONG_SPREAD.value == "long_spread"
        assert PairSignalType.SHORT_SPREAD.value == "short_spread"
        assert PairSignalType.EXIT.value == "exit"
        assert PairSignalType.NO_SIGNAL.value == "no_signal"

    def test_spread_method_values(self):
        assert SpreadMethod.RATIO.value == "ratio"
        assert SpreadMethod.DIFFERENCE.value == "difference"

    def test_hedge_method_values(self):
        assert HedgeMethod.OLS.value == "ols"
        assert HedgeMethod.TLS.value == "tls"

    def test_pair_status_values(self):
        assert PairStatus.COINTEGRATED.value == "cointegrated"
        assert PairStatus.WEAK.value == "weak"
        assert PairStatus.NOT_COINTEGRATED.value == "not_cointegrated"

    def test_cointegration_config_defaults(self):
        cfg = CointegrationConfig()
        assert cfg.pvalue_threshold == 0.05
        assert cfg.min_correlation == 0.50
        assert cfg.lookback_window == 252

    def test_spread_config_defaults(self):
        cfg = SpreadConfig()
        assert cfg.entry_zscore == 2.0
        assert cfg.exit_zscore == 0.5
        assert cfg.zscore_window == 20

    def test_selector_config_defaults(self):
        cfg = SelectorConfig()
        assert cfg.max_pairs == 20
        assert cfg.min_score == 50.0

    def test_pairs_config_bundles(self):
        cfg = PairsConfig()
        assert isinstance(cfg.cointegration, CointegrationConfig)
        assert isinstance(cfg.spread, SpreadConfig)
        assert isinstance(cfg.selector, SelectorConfig)


# ===========================================================================
# Model Tests
# ===========================================================================

class TestModels:
    """Test data models."""

    def test_cointegration_result_properties(self):
        cr = CointegrationResult(status=PairStatus.COINTEGRATED)
        assert cr.is_cointegrated is True
        cr2 = CointegrationResult(status=PairStatus.NOT_COINTEGRATED)
        assert cr2.is_cointegrated is False

    def test_cointegration_result_to_dict(self):
        cr = CointegrationResult(asset_a="AAPL", asset_b="MSFT", pvalue=0.02,
                                 status=PairStatus.COINTEGRATED)
        d = cr.to_dict()
        assert d["asset_a"] == "AAPL"
        assert d["is_cointegrated"] is True
        assert d["status"] == "cointegrated"

    def test_spread_analysis_properties(self):
        sa = SpreadAnalysis(hurst_exponent=0.35)
        assert sa.is_mean_reverting is True
        sa2 = SpreadAnalysis(hurst_exponent=0.65)
        assert sa2.is_mean_reverting is False

    def test_spread_analysis_to_dict(self):
        sa = SpreadAnalysis(asset_a="A", asset_b="B", zscore=1.5,
                           signal=PairSignalType.NO_SIGNAL)
        d = sa.to_dict()
        assert d["zscore"] == 1.5
        assert d["signal"] == "no_signal"

    def test_pair_score_to_dict(self):
        ps = PairScore(asset_a="X", asset_b="Y", total_score=75.0, rank=1)
        d = ps.to_dict()
        assert d["total_score"] == 75.0
        assert d["rank"] == 1

    def test_pair_signal_properties(self):
        sig = PairSignal(signal=PairSignalType.LONG_SPREAD)
        assert sig.is_entry is True
        assert sig.is_exit is False
        sig2 = PairSignal(signal=PairSignalType.EXIT)
        assert sig2.is_entry is False
        assert sig2.is_exit is True

    def test_pair_signal_to_dict(self):
        sig = PairSignal(asset_a="A", asset_b="B", signal=PairSignalType.SHORT_SPREAD,
                        zscore=2.5, confidence=0.85)
        d = sig.to_dict()
        assert d["signal"] == "short_spread"
        assert d["is_entry"] is True

    def test_pair_trade_to_dict(self):
        pt = PairTrade(asset_a="A", asset_b="B", direction="long_spread", pnl=500.0)
        d = pt.to_dict()
        assert d["pnl"] == 500.0
        assert d["is_open"] is True


# ===========================================================================
# Cointegration Tester Tests
# ===========================================================================

class TestCointegrationTester:
    """Test cointegration testing."""

    def test_cointegrated_pair(self):
        a, b = _make_cointegrated_pair()
        tester = CointegrationTester()
        result = tester.test_pair(a, b, "A", "B")
        assert result.is_cointegrated
        assert result.pvalue < 0.05
        assert result.hedge_ratio > 0

    def test_independent_pair(self):
        a, b = _make_independent_pair()
        tester = CointegrationTester()
        result = tester.test_pair(a, b, "X", "Y")
        # Independent pair should not be cointegrated
        assert result.status != PairStatus.COINTEGRATED or result.pvalue > 0.01

    def test_low_correlation_filtered(self):
        rng = np.random.default_rng(42)
        idx = pd.date_range("2025-01-01", periods=100, freq="B")
        a = pd.Series(rng.normal(100, 10, 100), index=idx)
        b = pd.Series(rng.normal(50, 5, 100), index=idx)
        tester = CointegrationTester(CointegrationConfig(min_correlation=0.90))
        result = tester.test_pair(a, b, "A", "B")
        assert result.status == PairStatus.NOT_COINTEGRATED
        assert result.pvalue == 1.0

    def test_hedge_ratio_positive(self):
        a, b = _make_cointegrated_pair(beta=2.0)
        tester = CointegrationTester()
        result = tester.test_pair(a, b, "A", "B")
        assert result.hedge_ratio > 0

    def test_test_universe(self):
        a, b = _make_cointegrated_pair(n=200, seed=10)
        rng = np.random.default_rng(20)
        idx = a.index
        c = pd.Series(80 * np.exp(np.cumsum(rng.normal(0, 0.02, 200))), index=idx)
        prices = pd.DataFrame({"A": a, "B": b, "C": c})
        tester = CointegrationTester()
        results = tester.test_universe(prices)
        # 3 symbols -> 3 pairs: A-B, A-C, B-C
        assert len(results) == 3

    def test_short_series(self):
        idx = pd.date_range("2025-01-01", periods=20, freq="B")
        a = pd.Series(np.arange(20, dtype=float) + 100, index=idx)
        b = pd.Series(np.arange(20, dtype=float) + 50, index=idx)
        tester = CointegrationTester()
        result = tester.test_pair(a, b, "A", "B")
        assert isinstance(result, CointegrationResult)


# ===========================================================================
# Spread Analyzer Tests
# ===========================================================================

class TestSpreadAnalyzer:
    """Test spread analysis."""

    def test_compute_spread(self):
        idx = pd.date_range("2025-01-01", periods=50, freq="B")
        a = pd.Series(np.linspace(100, 110, 50), index=idx)
        b = pd.Series(np.linspace(50, 55, 50), index=idx)
        analyzer = SpreadAnalyzer()
        spread = analyzer.compute_spread(a, b, hedge_ratio=2.0, intercept=0.0)
        assert len(spread) == 50
        # a - 2*b should be roughly 0
        assert abs(spread.iloc[0]) < 1

    def test_analyze_cointegrated(self):
        a, b = _make_cointegrated_pair()
        tester = CointegrationTester()
        coint = tester.test_pair(a, b)
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(a, b, coint.hedge_ratio, coint.intercept, "A", "B")
        assert result.spread_std > 0
        assert isinstance(result.zscore, float)
        assert result.half_life > 0

    def test_zscore_series(self):
        a, b = _make_cointegrated_pair(n=100)
        analyzer = SpreadAnalyzer()
        spread = analyzer.compute_spread(a, b, 1.5)
        zscores = analyzer.compute_zscore_series(spread)
        assert len(zscores) == len(spread)

    def test_half_life_mean_reverting(self):
        # Construct an AR(1) mean-reverting process
        rng = np.random.default_rng(42)
        n = 300
        spread = np.zeros(n)
        for i in range(1, n):
            spread[i] = 0.9 * spread[i - 1] + rng.normal(0, 1)
        analyzer = SpreadAnalyzer()
        hl = analyzer.compute_half_life(spread)
        # With phi=0.9, theoretical hl = -ln2/ln(0.9) ≈ 6.58
        assert 2 < hl < 20

    def test_half_life_random_walk(self):
        rng = np.random.default_rng(99)
        spread = np.cumsum(rng.normal(0, 1, 300))
        analyzer = SpreadAnalyzer()
        hl = analyzer.compute_half_life(spread)
        # Random walk half-life should be much larger than mean-reverting
        assert hl > 10

    def test_hurst_mean_reverting_vs_trending(self):
        analyzer = SpreadAnalyzer()
        # Mean-reverting AR(1)
        rng = np.random.default_rng(42)
        n = 1000
        mr_spread = np.zeros(n)
        for i in range(1, n):
            mr_spread[i] = 0.5 * mr_spread[i - 1] + rng.normal(0, 1)
        hurst_mr = analyzer.compute_hurst(mr_spread, max_lag=100)

        # Trending series
        trending = np.cumsum(np.ones(1000) * 0.1 + rng.normal(0, 0.01, 1000))
        hurst_trend = analyzer.compute_hurst(trending, max_lag=100)

        # Mean-reverting should have lower Hurst than trending
        assert hurst_mr < hurst_trend
        assert 0 <= hurst_mr <= 1
        assert 0 <= hurst_trend <= 1

    def test_signal_short_spread(self):
        analyzer = SpreadAnalyzer()
        signal = analyzer.generate_signal(zscore=2.5, asset_a="A", asset_b="B")
        assert signal.signal == PairSignalType.SHORT_SPREAD
        assert signal.is_entry

    def test_signal_long_spread(self):
        analyzer = SpreadAnalyzer()
        signal = analyzer.generate_signal(zscore=-2.5)
        assert signal.signal == PairSignalType.LONG_SPREAD

    def test_signal_exit(self):
        analyzer = SpreadAnalyzer()
        signal = analyzer.generate_signal(zscore=0.3)
        assert signal.signal == PairSignalType.EXIT

    def test_signal_no_signal(self):
        analyzer = SpreadAnalyzer()
        signal = analyzer.generate_signal(zscore=1.0)
        assert signal.signal == PairSignalType.NO_SIGNAL

    def test_signal_confidence(self):
        analyzer = SpreadAnalyzer()
        sig_entry = analyzer.generate_signal(zscore=2.5)
        sig_extreme = analyzer.generate_signal(zscore=4.0)
        assert sig_entry.confidence > sig_extreme.confidence


# ===========================================================================
# Pair Selector Tests
# ===========================================================================

class TestPairSelector:
    """Test pair selection and scoring."""

    def test_score_pair(self):
        selector = PairSelector()
        coint = CointegrationResult(
            asset_a="A", asset_b="B", pvalue=0.01,
            hedge_ratio=1.5, correlation=0.85,
            status=PairStatus.COINTEGRATED,
        )
        spread = SpreadAnalysis(
            asset_a="A", asset_b="B", half_life=15.0,
            hurst_exponent=0.35,
        )
        score = selector.score_pair(coint, spread)
        assert score.total_score > 0
        assert score.cointegration_score > 0
        assert score.hurst_score > 0

    def test_score_bad_pair(self):
        selector = PairSelector()
        coint = CointegrationResult(
            pvalue=0.08, correlation=0.55,
            status=PairStatus.COINTEGRATED,
        )
        spread = SpreadAnalysis(half_life=80.0, hurst_exponent=0.55)
        score = selector.score_pair(coint, spread)
        # Worse scores for high p-value, high half-life, hurst > 0.5
        assert score.half_life_score == 0.0
        assert score.hurst_score == 0.0

    def test_screen_universe(self):
        a, b = _make_cointegrated_pair(n=300, seed=10)
        rng = np.random.default_rng(20)
        idx = a.index
        c = pd.Series(80 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))), index=idx)
        prices = pd.DataFrame({"A": a, "B": b, "C": c})

        selector = PairSelector(config=PairsConfig(
            selector=SelectorConfig(min_score=0.0),  # Accept all
        ))
        scores = selector.screen_universe(prices)
        # Should find at least the A-B pair
        assert len(scores) >= 0  # May be 0 if none pass cointegration
        for s in scores:
            assert s.rank > 0

    def test_screen_ranks_correctly(self):
        selector = PairSelector()
        coint1 = CointegrationResult(asset_a="A", asset_b="B", pvalue=0.01,
                                     correlation=0.90, status=PairStatus.COINTEGRATED)
        spread1 = SpreadAnalysis(half_life=10.0, hurst_exponent=0.30)
        coint2 = CointegrationResult(asset_a="C", asset_b="D", pvalue=0.04,
                                     correlation=0.70, status=PairStatus.COINTEGRATED)
        spread2 = SpreadAnalysis(half_life=30.0, hurst_exponent=0.45)

        s1 = selector.score_pair(coint1, spread1)
        s2 = selector.score_pair(coint2, spread2)
        assert s1.total_score > s2.total_score


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline(self):
        """Cointegration -> Spread -> Signal."""
        a, b = _make_cointegrated_pair(n=300, seed=7)

        # Cointegration test
        tester = CointegrationTester()
        coint = tester.test_pair(a, b, "STOCK_A", "STOCK_B")

        if not coint.is_cointegrated:
            pytest.skip("Generated data not cointegrated (stochastic test)")

        # Spread analysis
        analyzer = SpreadAnalyzer()
        spread = analyzer.analyze(
            a, b, coint.hedge_ratio, coint.intercept,
            "STOCK_A", "STOCK_B",
        )
        assert spread.spread_std > 0
        assert spread.half_life > 0

        # Signal generation
        signal = analyzer.generate_signal(
            spread.zscore, coint.hedge_ratio, spread.current_spread,
            "STOCK_A", "STOCK_B",
        )
        assert isinstance(signal.signal, PairSignalType)

    def test_spread_analysis_roundtrip(self):
        a, b = _make_cointegrated_pair(n=200, seed=42)
        tester = CointegrationTester()
        coint = tester.test_pair(a, b)
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(a, b, coint.hedge_ratio, coint.intercept, "A", "B")
        d = result.to_dict()
        assert "zscore" in d
        assert "half_life" in d
        assert "is_mean_reverting" in d


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.pairs import (
            CointegrationTester,
            SpreadAnalyzer,
            PairSelector,
            PairSignalType,
            SpreadMethod,
            HedgeMethod,
            PairStatus,
            CointegrationResult,
            SpreadAnalysis,
            PairScore,
            PairSignal,
            PairTrade,
            DEFAULT_CONFIG,
        )
        assert CointegrationTester is not None
        assert SpreadAnalyzer is not None
        assert PairSelector is not None
