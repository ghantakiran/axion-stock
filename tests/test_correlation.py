"""Tests for Correlation Analysis module (PRD-37)."""

import pytest
import numpy as np
import pandas as pd
from datetime import date, timedelta

from src.correlation.config import (
    CorrelationMethod,
    RegimeType,
    DiversificationLevel,
    WindowType,
    CorrelationConfig,
    RollingConfig,
    RegimeConfig,
    DiversificationConfig,
    CorrelationAnalysisConfig,
    STANDARD_WINDOWS,
    DEFAULT_CONFIG,
)
from src.correlation.models import (
    CorrelationMatrix,
    CorrelationPair,
    RollingCorrelation,
    CorrelationRegime,
    DiversificationScore,
)
from src.correlation.engine import CorrelationEngine
from src.correlation.regime import CorrelationRegimeDetector
from src.correlation.diversification import DiversificationAnalyzer


# =========================================================================
# Helpers
# =========================================================================


def _make_returns(n_days: int = 100, n_assets: int = 4, seed: int = 42) -> pd.DataFrame:
    """Generate random return data."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_assets)]
    # Correlated returns: common factor + idiosyncratic
    common = rng.normal(0, 0.01, n_days)
    data = {}
    for i, sym in enumerate(symbols):
        idio = rng.normal(0, 0.015, n_days)
        data[sym] = common * (0.5 + i * 0.1) + idio
    return pd.DataFrame(data, index=dates)


def _make_corr_matrix(correlations: np.ndarray, symbols: list[str]) -> CorrelationMatrix:
    """Create a CorrelationMatrix from a numpy array."""
    return CorrelationMatrix(
        symbols=symbols,
        values=correlations,
        n_periods=100,
        end_date=date.today(),
    )


# =========================================================================
# Config Tests
# =========================================================================


class TestCorrelationConfig:
    def test_correlation_methods(self):
        assert len(CorrelationMethod) == 3
        assert CorrelationMethod.PEARSON.value == "pearson"

    def test_regime_types(self):
        assert len(RegimeType) == 4

    def test_diversification_levels(self):
        assert len(DiversificationLevel) == 4

    def test_window_types(self):
        assert len(WindowType) == 3

    def test_standard_windows(self):
        assert STANDARD_WINDOWS["1Y"] == 252
        assert STANDARD_WINDOWS["3M"] == 63

    def test_correlation_config(self):
        cfg = CorrelationConfig()
        assert cfg.method == CorrelationMethod.PEARSON
        assert cfg.min_periods == 20

    def test_rolling_config(self):
        cfg = RollingConfig()
        assert cfg.window == 63
        assert cfg.window_type == WindowType.FIXED

    def test_regime_config(self):
        cfg = RegimeConfig()
        assert cfg.high_threshold == 0.65
        assert cfg.change_threshold == 0.15

    def test_diversification_config(self):
        cfg = DiversificationConfig()
        assert cfg.excellent_threshold == 1.5

    def test_top_level_config(self):
        cfg = CorrelationAnalysisConfig()
        assert isinstance(cfg.correlation, CorrelationConfig)
        assert isinstance(cfg.regime, RegimeConfig)

    def test_default_config(self):
        assert DEFAULT_CONFIG.correlation.method == CorrelationMethod.PEARSON


# =========================================================================
# Model Tests
# =========================================================================


class TestCorrelationModels:
    def test_correlation_matrix_properties(self):
        values = np.array([
            [1.0, 0.8, 0.3],
            [0.8, 1.0, 0.5],
            [0.3, 0.5, 1.0],
        ])
        matrix = _make_corr_matrix(values, ["A", "B", "C"])
        assert matrix.n_assets == 3
        assert matrix.avg_correlation == pytest.approx(
            (0.8 + 0.3 + 0.8 + 0.5 + 0.3 + 0.5) / 6
        )
        assert matrix.max_correlation == 0.8
        assert matrix.min_correlation == 0.3

    def test_correlation_matrix_get_pair(self):
        values = np.array([[1.0, 0.7], [0.7, 1.0]])
        matrix = _make_corr_matrix(values, ["AAPL", "MSFT"])
        assert matrix.get_pair("AAPL", "MSFT") == 0.7
        assert matrix.get_pair("MSFT", "AAPL") == 0.7
        assert matrix.get_pair("UNKNOWN", "AAPL") == 0.0

    def test_correlation_matrix_to_dict(self):
        values = np.array([[1.0, 0.5], [0.5, 1.0]])
        matrix = _make_corr_matrix(values, ["A", "B"])
        d = matrix.to_dict()
        assert d["n_assets"] == 2
        assert d["avg_correlation"] == 0.5

    def test_empty_matrix(self):
        matrix = CorrelationMatrix()
        assert matrix.n_assets == 0
        assert matrix.avg_correlation == 0.0

    def test_correlation_pair(self):
        pair = CorrelationPair(
            symbol_a="AAPL", symbol_b="MSFT", correlation=0.85,
        )
        assert pair.abs_correlation == 0.85
        assert pair.is_highly_correlated is True
        assert pair.is_negatively_correlated is False

    def test_negative_pair(self):
        pair = CorrelationPair(
            symbol_a="SPY", symbol_b="TLT", correlation=-0.45,
        )
        assert pair.is_negatively_correlated is True
        assert pair.is_highly_correlated is False

    def test_rolling_correlation(self):
        rc = RollingCorrelation(
            symbol_a="A", symbol_b="B",
            dates=[date(2026, 1, i) for i in range(1, 6)],
            values=[0.3, 0.4, 0.5, 0.6, 0.7],
        )
        assert rc.current == 0.7
        assert rc.mean == pytest.approx(0.5)
        assert rc.n_observations == 5
        assert rc.percentile == 100.0  # 0.7 is max

    def test_rolling_empty(self):
        rc = RollingCorrelation(symbol_a="A", symbol_b="B")
        assert rc.current == 0.0
        assert rc.mean == 0.0
        assert rc.percentile == 50.0

    def test_correlation_regime(self):
        regime = CorrelationRegime(
            regime=RegimeType.HIGH, avg_correlation=0.55,
        )
        assert regime.regime == RegimeType.HIGH

    def test_diversification_score(self):
        score = DiversificationScore(
            diversification_ratio=1.45,
            effective_n_bets=3.2,
            level=DiversificationLevel.GOOD,
        )
        d = score.to_dict()
        assert d["diversification_ratio"] == 1.45
        assert d["level"] == "good"


# =========================================================================
# Engine Tests
# =========================================================================


class TestCorrelationEngine:
    def test_compute_matrix(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 4)
        matrix = engine.compute_matrix(returns)

        assert matrix.n_assets == 4
        assert matrix.n_periods == 100
        assert matrix.values is not None
        assert matrix.values.shape == (4, 4)
        # Diagonal should be 1.0
        for i in range(4):
            assert matrix.values[i, i] == pytest.approx(1.0)

    def test_compute_spearman(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 3)
        matrix = engine.compute_matrix(returns, method=CorrelationMethod.SPEARMAN)
        assert matrix.method == CorrelationMethod.SPEARMAN
        assert matrix.n_assets == 3

    def test_compute_kendall(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 3)
        matrix = engine.compute_matrix(returns, method=CorrelationMethod.KENDALL)
        assert matrix.method == CorrelationMethod.KENDALL

    def test_dates_captured(self):
        engine = CorrelationEngine()
        returns = _make_returns(50, 2)
        matrix = engine.compute_matrix(returns)
        assert matrix.start_date is not None
        assert matrix.end_date is not None
        assert matrix.start_date < matrix.end_date

    def test_top_pairs_most_correlated(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 5)
        matrix = engine.compute_matrix(returns)
        pairs = engine.get_top_pairs(matrix, n=3, ascending=False)

        assert len(pairs) == 3
        # Should be sorted descending
        assert pairs[0].correlation >= pairs[1].correlation

    def test_top_pairs_least_correlated(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 5)
        matrix = engine.compute_matrix(returns)
        pairs = engine.get_top_pairs(matrix, n=3, ascending=True)

        assert len(pairs) == 3
        # Should be sorted ascending
        assert pairs[0].correlation <= pairs[1].correlation

    def test_highly_correlated(self):
        # Create perfectly correlated data
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2025-01-01", periods=100)
        base = rng.normal(0, 0.01, 100)
        returns = pd.DataFrame({
            "A": base,
            "B": base + rng.normal(0, 0.001, 100),  # Very similar
            "C": rng.normal(0, 0.01, 100),  # Independent
        }, index=dates)

        engine = CorrelationEngine()
        matrix = engine.compute_matrix(returns)
        pairs = engine.get_highly_correlated(matrix, threshold=0.90)

        # A-B should be highly correlated
        assert len(pairs) >= 1
        ab_pair = [p for p in pairs if set([p.symbol_a, p.symbol_b]) == {"A", "B"}]
        assert len(ab_pair) == 1

    def test_rolling_correlation(self):
        engine = CorrelationEngine(rolling_config=RollingConfig(window=30, min_periods=10))
        returns = _make_returns(100, 2)
        symbols = list(returns.columns)

        rolling = engine.compute_rolling(returns, symbols[0], symbols[1])
        assert rolling.n_observations > 0
        assert rolling.symbol_a == symbols[0]
        assert rolling.symbol_b == symbols[1]
        assert len(rolling.dates) == len(rolling.values)

    def test_rolling_missing_symbol(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 2)
        rolling = engine.compute_rolling(returns, "MISSING", "ALSO_MISSING")
        assert rolling.n_observations == 0

    def test_eigenvalues(self):
        engine = CorrelationEngine()
        returns = _make_returns(100, 4)
        matrix = engine.compute_matrix(returns)
        eigenvalues = engine.compute_eigenvalues(matrix)

        assert len(eigenvalues) == 4
        # Sorted descending
        assert eigenvalues[0] >= eigenvalues[1]
        # All positive for a valid correlation matrix
        assert all(ev > 0 for ev in eigenvalues)
        # Sum of eigenvalues = number of assets
        assert sum(eigenvalues) == pytest.approx(4.0, abs=0.01)

    def test_empty_returns(self):
        engine = CorrelationEngine()
        returns = pd.DataFrame()
        matrix = engine.compute_matrix(returns)
        assert matrix.n_assets == 0


# =========================================================================
# Regime Detection Tests
# =========================================================================


class TestCorrelationRegimeDetector:
    def _make_low_corr_matrix(self) -> CorrelationMatrix:
        values = np.array([
            [1.0, 0.1, 0.15],
            [0.1, 1.0, 0.2],
            [0.15, 0.2, 1.0],
        ])
        return _make_corr_matrix(values, ["A", "B", "C"])

    def _make_high_corr_matrix(self) -> CorrelationMatrix:
        values = np.array([
            [1.0, 0.8, 0.75],
            [0.8, 1.0, 0.85],
            [0.75, 0.85, 1.0],
        ])
        return _make_corr_matrix(values, ["A", "B", "C"])

    def test_detect_low_regime(self):
        detector = CorrelationRegimeDetector()
        regime = detector.detect(self._make_low_corr_matrix())
        assert regime.regime == RegimeType.LOW

    def test_detect_crisis_regime(self):
        detector = CorrelationRegimeDetector()
        regime = detector.detect(self._make_high_corr_matrix())
        assert regime.regime == RegimeType.CRISIS

    def test_regime_change_detection(self):
        detector = CorrelationRegimeDetector()
        detector.detect(self._make_low_corr_matrix())
        regime2 = detector.detect(self._make_high_corr_matrix())

        assert regime2.regime_changed is True
        assert regime2.prev_regime == RegimeType.LOW

    def test_no_regime_change(self):
        detector = CorrelationRegimeDetector()
        detector.detect(self._make_low_corr_matrix())
        regime2 = detector.detect(self._make_low_corr_matrix())

        assert regime2.regime_changed is False

    def test_dispersion(self):
        detector = CorrelationRegimeDetector()
        regime = detector.detect(self._make_high_corr_matrix())
        assert regime.dispersion > 0

    def test_significant_shift(self):
        detector = CorrelationRegimeDetector()
        low = self._make_low_corr_matrix()
        high = self._make_high_corr_matrix()
        assert detector.has_significant_shift(high, low) is True

    def test_no_significant_shift(self):
        detector = CorrelationRegimeDetector()
        low = self._make_low_corr_matrix()
        assert detector.has_significant_shift(low, low) is False

    def test_current_regime(self):
        detector = CorrelationRegimeDetector()
        assert detector.current_regime is None
        detector.detect(self._make_low_corr_matrix())
        assert detector.current_regime == RegimeType.LOW

    def test_history(self):
        detector = CorrelationRegimeDetector()
        detector.detect(self._make_low_corr_matrix())
        detector.detect(self._make_high_corr_matrix())
        assert len(detector.history) == 2

    def test_reset(self):
        detector = CorrelationRegimeDetector()
        detector.detect(self._make_low_corr_matrix())
        detector.reset()
        assert detector.current_regime is None
        assert len(detector.history) == 0


# =========================================================================
# Diversification Tests
# =========================================================================


class TestDiversificationAnalyzer:
    def test_well_diversified(self):
        # Low correlations = good diversification
        values = np.array([
            [1.0, 0.1, -0.1, 0.05],
            [0.1, 1.0, 0.15, -0.05],
            [-0.1, 0.15, 1.0, 0.1],
            [0.05, -0.05, 0.1, 1.0],
        ])
        matrix = _make_corr_matrix(values, ["A", "B", "C", "D"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)

        assert score.diversification_ratio > 1.0
        assert score.n_assets == 4
        assert score.level in (DiversificationLevel.GOOD, DiversificationLevel.EXCELLENT)

    def test_poorly_diversified(self):
        # High correlations = poor diversification
        values = np.array([
            [1.0, 0.95, 0.90],
            [0.95, 1.0, 0.92],
            [0.90, 0.92, 1.0],
        ])
        matrix = _make_corr_matrix(values, ["A", "B", "C"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)

        assert score.diversification_ratio < 1.2
        assert len(score.highly_correlated_pairs) > 0

    def test_max_pair_identified(self):
        values = np.array([
            [1.0, 0.3, 0.9],
            [0.3, 1.0, 0.2],
            [0.9, 0.2, 1.0],
        ])
        matrix = _make_corr_matrix(values, ["A", "B", "C"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)

        assert score.max_pair_correlation == pytest.approx(0.9)
        assert set(score.max_pair) == {"A", "C"}

    def test_custom_weights(self):
        values = np.array([[1.0, 0.5], [0.5, 1.0]])
        matrix = _make_corr_matrix(values, ["A", "B"])

        analyzer = DiversificationAnalyzer()
        score_equal = analyzer.score(matrix)
        score_concentrated = analyzer.score(
            matrix, weights={"A": 0.9, "B": 0.1},
        )

        # Concentrated portfolio should be less diversified
        assert score_concentrated.diversification_ratio <= score_equal.diversification_ratio

    def test_custom_volatilities(self):
        values = np.array([[1.0, 0.3], [0.3, 1.0]])
        matrix = _make_corr_matrix(values, ["A", "B"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(
            matrix,
            volatilities={"A": 0.30, "B": 0.15},
        )
        assert score.diversification_ratio > 1.0

    def test_to_dict(self):
        values = np.array([[1.0, 0.5], [0.5, 1.0]])
        matrix = _make_corr_matrix(values, ["A", "B"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)
        d = score.to_dict()

        assert "diversification_ratio" in d
        assert "level" in d
        assert "effective_n_bets" in d

    def test_single_asset(self):
        values = np.array([[1.0]])
        matrix = _make_corr_matrix(values, ["A"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)
        assert score.n_assets == 1

    def test_compare_portfolios(self):
        analyzer = DiversificationAnalyzer()

        low_corr = np.array([[1.0, 0.1], [0.1, 1.0]])
        high_corr = np.array([[1.0, 0.9], [0.9, 1.0]])

        score_good = analyzer.score(_make_corr_matrix(low_corr, ["A", "B"]))
        score_bad = analyzer.score(_make_corr_matrix(high_corr, ["C", "D"]))

        comparison = analyzer.compare_portfolios({
            "Good": score_good,
            "Bad": score_bad,
        })

        assert comparison["best"] == "Good"
        assert comparison["worst"] == "Bad"
        assert len(comparison["ranking"]) == 2

    def test_effective_n_bets(self):
        # Identity matrix = N independent bets
        values = np.eye(4)
        matrix = _make_corr_matrix(values, ["A", "B", "C", "D"])

        analyzer = DiversificationAnalyzer()
        score = analyzer.score(matrix)
        # Should be close to 4 (perfectly uncorrelated)
        assert score.effective_n_bets == pytest.approx(4.0, abs=0.1)


# =========================================================================
# Integration Tests
# =========================================================================


class TestCorrelationIntegration:
    def test_full_workflow(self):
        """Compute matrix, detect regime, score diversification."""
        engine = CorrelationEngine()
        detector = CorrelationRegimeDetector()
        analyzer = DiversificationAnalyzer()

        returns = _make_returns(200, 5)
        matrix = engine.compute_matrix(returns)

        # Get pairs
        top_pairs = engine.get_top_pairs(matrix, n=3)
        assert len(top_pairs) == 3

        # Detect regime
        regime = detector.detect(matrix)
        assert regime.regime in list(RegimeType)

        # Score diversification
        div_score = analyzer.score(matrix)
        assert div_score.n_assets == 5
        assert div_score.diversification_ratio > 0

    def test_rolling_then_regime(self):
        """Compute rolling correlations and track regime changes."""
        engine = CorrelationEngine()
        detector = CorrelationRegimeDetector()
        returns = _make_returns(200, 3)
        symbols = list(returns.columns)

        # Rolling correlation
        rolling = engine.compute_rolling(returns, symbols[0], symbols[1], window=30)
        assert rolling.n_observations > 0

        # Compute matrix at different windows
        for start in range(0, 150, 50):
            window_returns = returns.iloc[start:start + 50]
            if len(window_returns) >= 20:
                matrix = engine.compute_matrix(window_returns)
                detector.detect(matrix)

        assert len(detector.history) >= 2


# =========================================================================
# Module Import Test
# =========================================================================


class TestCorrelationModuleImports:
    def test_top_level_imports(self):
        from src.correlation import (
            CorrelationEngine,
            CorrelationRegimeDetector,
            DiversificationAnalyzer,
            CorrelationMatrix,
            CorrelationPair,
            RollingCorrelation,
            CorrelationRegime,
            DiversificationScore,
            CorrelationMethod,
            RegimeType,
            DiversificationLevel,
        )
        assert CorrelationEngine is not None
        assert CorrelationRegimeDetector is not None
        assert DiversificationAnalyzer is not None
