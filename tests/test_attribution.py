"""Tests for PRD-15: Performance Attribution System."""

import pytest
import numpy as np
import pandas as pd
from datetime import date

from src.attribution.config import (
    AttributionMethod,
    AttributionLevel,
    BenchmarkType,
    TimePeriod,
    RiskMetricType,
    STANDARD_FACTORS,
    COMMON_BENCHMARKS,
    TRADING_DAYS_PER_YEAR,
    RISK_FREE_RATE,
    BenchmarkDefinition,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)
from src.attribution.models import (
    SectorAttribution,
    BrinsonAttribution,
    FactorContribution,
    FactorAttribution,
    BenchmarkComparison,
    DrawdownPeriod,
    PerformanceMetrics,
    MonthlyReturns,
    TearSheet,
)
from src.attribution.brinson import BrinsonAnalyzer
from src.attribution.factor_attribution import FactorAnalyzer
from src.attribution.benchmark import BenchmarkAnalyzer
from src.attribution.metrics import MetricsCalculator
from src.attribution.tearsheet import TearSheetGenerator


def _make_returns(n=252, mean=0.0004, std=0.015, seed=42):
    """Generate synthetic daily returns."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    returns = rng.normal(mean, std, n)
    return pd.Series(returns, index=dates)


def _make_benchmark_returns(n=252, mean=0.0003, std=0.012, seed=99):
    """Generate synthetic benchmark returns."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    returns = rng.normal(mean, std, n)
    return pd.Series(returns, index=dates)


class TestAttributionConfig:
    """Test configuration."""

    def test_attribution_methods(self):
        assert len(AttributionMethod) == 3
        assert AttributionMethod.BRINSON_FACHLER.value == "brinson_fachler"

    def test_time_periods(self):
        assert len(TimePeriod) == 10
        assert TimePeriod.YTD.value == "ytd"

    def test_risk_metrics(self):
        assert len(RiskMetricType) == 10
        assert RiskMetricType.SHARPE_RATIO.value == "sharpe_ratio"

    def test_standard_factors(self):
        assert "market" in STANDARD_FACTORS
        assert "value" in STANDARD_FACTORS
        assert "momentum" in STANDARD_FACTORS
        assert len(STANDARD_FACTORS) == 7

    def test_common_benchmarks(self):
        assert "SPY" in COMMON_BENCHMARKS
        assert COMMON_BENCHMARKS["SPY"]["name"] == "S&P 500"

    def test_config_defaults(self):
        config = AttributionConfig()
        assert config.default_benchmark == "SPY"
        assert config.trading_days_per_year == 252
        assert config.risk_free_rate == RISK_FREE_RATE

    def test_benchmark_definition(self):
        bd = BenchmarkDefinition(
            benchmark_id="60_40",
            name="60/40",
            benchmark_type=BenchmarkType.BLENDED,
            components={"SPY": 0.6, "AGG": 0.4},
        )
        assert bd.components["SPY"] == 0.6


class TestBrinsonAttribution:
    """Test Brinson-Fachler attribution model."""

    def test_basic_attribution(self):
        analyzer = BrinsonAnalyzer()

        portfolio_weights = {"Tech": 0.40, "Healthcare": 0.30, "Finance": 0.30}
        benchmark_weights = {"Tech": 0.30, "Healthcare": 0.35, "Finance": 0.35}
        portfolio_returns = {"Tech": 0.15, "Healthcare": 0.08, "Finance": 0.05}
        benchmark_returns = {"Tech": 0.12, "Healthcare": 0.06, "Finance": 0.04}

        result = analyzer.analyze(
            portfolio_weights, benchmark_weights,
            portfolio_returns, benchmark_returns,
        )

        assert len(result.sectors) == 3
        assert result.portfolio_return > 0
        assert result.benchmark_return > 0

        # Active return = sum of effects
        assert abs(result.active_return - result.attribution_sum) < 1e-10

    def test_zero_active_return(self):
        analyzer = BrinsonAnalyzer()

        weights = {"Tech": 0.50, "Finance": 0.50}
        returns = {"Tech": 0.10, "Finance": 0.05}

        result = analyzer.analyze(weights, weights, returns, returns)

        assert abs(result.active_return) < 1e-10
        assert abs(result.total_allocation) < 1e-10
        assert abs(result.total_selection) < 1e-10

    def test_allocation_effect(self):
        """Overweight in outperforming sector should produce positive allocation."""
        analyzer = BrinsonAnalyzer()

        # Portfolio overweights Tech (which outperforms)
        result = analyzer.analyze(
            portfolio_weights={"Tech": 0.70, "Staples": 0.30},
            benchmark_weights={"Tech": 0.50, "Staples": 0.50},
            portfolio_returns={"Tech": 0.10, "Staples": 0.02},
            benchmark_returns={"Tech": 0.10, "Staples": 0.02},
        )

        # Allocation effect should be positive (overweight outperformer)
        assert result.total_allocation > 0
        # Selection should be ~0 (same returns)
        assert abs(result.total_selection) < 1e-10

    def test_selection_effect(self):
        """Better stock picking should produce positive selection."""
        analyzer = BrinsonAnalyzer()

        result = analyzer.analyze(
            portfolio_weights={"Tech": 0.50, "Finance": 0.50},
            benchmark_weights={"Tech": 0.50, "Finance": 0.50},
            portfolio_returns={"Tech": 0.15, "Finance": 0.08},
            benchmark_returns={"Tech": 0.10, "Finance": 0.05},
        )

        # Same weights, better returns = positive selection
        assert result.total_selection > 0
        assert abs(result.total_allocation) < 1e-10

    def test_from_holdings(self):
        analyzer = BrinsonAnalyzer()

        port = pd.DataFrame({
            "sector": ["Tech", "Tech", "Finance"],
            "weight": [0.30, 0.20, 0.50],
            "return": [0.15, 0.10, 0.05],
        })
        bm = pd.DataFrame({
            "sector": ["Tech", "Finance", "Finance"],
            "weight": [0.40, 0.30, 0.30],
            "return": [0.12, 0.06, 0.04],
        })

        result = analyzer.analyze_from_holdings(port, bm)
        assert len(result.sectors) == 2
        assert abs(result.active_return - result.attribution_sum) < 1e-10

    def test_attribution_sum_property(self):
        ba = BrinsonAttribution(
            total_allocation=0.01,
            total_selection=0.02,
            total_interaction=0.005,
        )
        assert abs(ba.attribution_sum - 0.035) < 1e-10


class TestFactorAttribution:
    """Test factor attribution."""

    def test_basic_factor_attribution(self):
        analyzer = FactorAnalyzer()

        result = analyzer.analyze(
            portfolio_return=0.10,
            factor_exposures={"market": 1.1, "value": 0.3, "momentum": -0.2},
            factor_returns={"market": 0.08, "value": 0.03, "momentum": -0.02},
        )

        assert len(result.factors) == 3
        assert abs(result.portfolio_return - 0.10) < 1e-10
        assert abs(
            result.factor_return_total + result.specific_return - result.portfolio_return
        ) < 1e-10

    def test_factor_contributions(self):
        analyzer = FactorAnalyzer()

        result = analyzer.analyze(
            portfolio_return=0.10,
            factor_exposures={"market": 1.0},
            factor_returns={"market": 0.08},
        )

        # Market contribution = 1.0 * 0.08 = 0.08
        assert abs(result.factors[0].contribution - 0.08) < 1e-10
        # Specific = 0.10 - 0.08 = 0.02
        assert abs(result.specific_return - 0.02) < 1e-10

    def test_regression_based_attribution(self):
        analyzer = FactorAnalyzer()

        port = _make_returns(100, mean=0.001, std=0.02, seed=10)
        factors = pd.DataFrame({
            "market": _make_returns(100, mean=0.0008, std=0.015, seed=20).values,
            "value": _make_returns(100, mean=0.0002, std=0.008, seed=30).values,
        }, index=port.index)

        result = analyzer.analyze_from_returns(port, factors)
        assert len(result.factors) == 2
        assert result.r_squared >= 0

    def test_empty_returns(self):
        analyzer = FactorAnalyzer()
        port = pd.Series([], dtype=float)
        factors = pd.DataFrame()
        result = analyzer.analyze_from_returns(port, factors)
        assert result.portfolio_return == 0.0


class TestBenchmarkAnalyzer:
    """Test benchmark comparison."""

    def test_basic_comparison(self):
        analyzer = BenchmarkAnalyzer()

        port = _make_returns(252, mean=0.0005, std=0.015)
        bm = _make_benchmark_returns(252)

        result = analyzer.compare(port, bm)
        assert result.benchmark_id == "SPY"
        assert result.tracking_error > 0
        assert result.correlation != 0

    def test_tracking_error_zero_for_same(self):
        analyzer = BenchmarkAnalyzer()
        returns = _make_returns(100)
        result = analyzer.compare(returns, returns)
        assert abs(result.tracking_error) < 1e-10
        assert abs(result.active_return) < 1e-10

    def test_capture_ratios(self):
        analyzer = BenchmarkAnalyzer()
        port = _make_returns(252, mean=0.0005)
        bm = _make_benchmark_returns(252)
        result = analyzer.compare(port, bm)

        # Capture ratios should be non-zero
        assert result.up_capture != 0
        assert result.down_capture != 0

    def test_active_share(self):
        active = BenchmarkAnalyzer._active_share(
            {"AAPL": 0.30, "MSFT": 0.20, "GOOGL": 0.50},
            {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.50},
        )
        # |0.30-0.25| + |0.20-0.25| + |0.50-0.50| = 0.10
        # Active share = 0.5 * 0.10 = 0.05
        assert abs(active - 0.05) < 1e-10

    def test_active_share_identical(self):
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        active = BenchmarkAnalyzer._active_share(weights, weights)
        assert abs(active) < 1e-10

    def test_short_history(self):
        analyzer = BenchmarkAnalyzer()
        port = pd.Series([0.01])
        bm = pd.Series([0.02])
        result = analyzer.compare(port, bm)
        assert result.tracking_error == 0


class TestMetricsCalculator:
    """Test metrics calculator."""

    def test_compute_basic(self):
        calc = MetricsCalculator()
        returns = _make_returns(252)
        metrics = calc.compute(returns)

        assert metrics.total_return != 0
        assert metrics.annualized_return != 0
        assert metrics.volatility > 0
        assert metrics.total_days == 252
        assert metrics.positive_days + metrics.negative_days <= metrics.total_days

    def test_sharpe_ratio(self):
        calc = MetricsCalculator()
        # Positive mean returns should produce positive Sharpe (usually)
        returns = _make_returns(252, mean=0.001, std=0.01)
        metrics = calc.compute(returns)
        assert metrics.sharpe_ratio > 0

    def test_max_drawdown(self):
        calc = MetricsCalculator()
        returns = _make_returns(252)
        metrics = calc.compute(returns)
        assert metrics.max_drawdown <= 0

    def test_win_rate(self):
        calc = MetricsCalculator()
        returns = _make_returns(100)
        metrics = calc.compute(returns)
        assert 0 <= metrics.win_rate <= 1

    def test_var_cvar(self):
        calc = MetricsCalculator()
        returns = _make_returns(252)
        metrics = calc.compute(returns)
        assert metrics.var_95 < 0  # Should be negative
        assert metrics.cvar_95 <= metrics.var_95  # CVaR is worse than VaR

    def test_empty_returns(self):
        calc = MetricsCalculator()
        metrics = calc.compute(pd.Series([], dtype=float))
        assert metrics.total_return == 0.0
        assert metrics.total_days == 0

    def test_compute_drawdowns(self):
        calc = MetricsCalculator()
        returns = _make_returns(252)
        drawdowns = calc.compute_drawdowns(returns)

        assert len(drawdowns) > 0
        assert drawdowns[0].depth < 0  # Sorted by depth
        assert drawdowns[0].start_date is not None

    def test_compute_monthly_returns(self):
        calc = MetricsCalculator()
        port = _make_returns(252)
        bm = _make_benchmark_returns(252)

        monthly = calc.compute_monthly_returns(port, bm)
        assert len(monthly) > 0
        assert monthly[0].year > 0
        assert 1 <= monthly[0].month <= 12

    def test_compute_monthly_returns_no_benchmark(self):
        calc = MetricsCalculator()
        port = _make_returns(100)
        monthly = calc.compute_monthly_returns(port)
        assert len(monthly) > 0
        assert all(m.benchmark_return == 0.0 for m in monthly)

    def test_rolling_metrics(self):
        calc = MetricsCalculator()
        returns = _make_returns(252)
        sharpe_data, vol_data = calc.compute_rolling(returns, window=63)

        assert len(sharpe_data) > 0
        assert len(vol_data) > 0
        # Each data point is (date, value) tuple
        assert len(sharpe_data[0]) == 2
        assert isinstance(sharpe_data[0][1], float)

    def test_rolling_insufficient_data(self):
        calc = MetricsCalculator()
        returns = _make_returns(10)
        sharpe_data, vol_data = calc.compute_rolling(returns, window=63)
        assert len(sharpe_data) == 0
        assert len(vol_data) == 0


class TestTearSheetGenerator:
    """Test tear sheet generation."""

    def test_basic_tear_sheet(self):
        gen = TearSheetGenerator()
        port = _make_returns(252)
        bm = _make_benchmark_returns(252)

        sheet = gen.generate(
            portfolio_returns=port,
            benchmark_returns=bm,
            name="Test Portfolio",
        )

        assert sheet.name == "Test Portfolio"
        assert sheet.metrics.total_days == 252
        assert sheet.benchmark_comparison is not None
        assert sheet.benchmark_comparison.tracking_error > 0
        assert len(sheet.monthly_returns) > 0
        assert len(sheet.top_drawdowns) > 0

    def test_tear_sheet_with_brinson(self):
        gen = TearSheetGenerator()
        port = _make_returns(252)

        sheet = gen.generate(
            portfolio_returns=port,
            portfolio_sector_weights={"Tech": 0.40, "Finance": 0.30, "Health": 0.30},
            benchmark_sector_weights={"Tech": 0.30, "Finance": 0.35, "Health": 0.35},
            portfolio_sector_returns={"Tech": 0.15, "Finance": 0.08, "Health": 0.05},
            benchmark_sector_returns={"Tech": 0.12, "Finance": 0.06, "Health": 0.04},
        )

        assert sheet.brinson is not None
        assert len(sheet.brinson.sectors) == 3
        assert abs(sheet.brinson.active_return - sheet.brinson.attribution_sum) < 1e-10

    def test_tear_sheet_with_factors(self):
        gen = TearSheetGenerator()
        port = _make_returns(252)

        sheet = gen.generate(
            portfolio_returns=port,
            factor_exposures={"market": 1.1, "value": 0.3},
            factor_returns_dict={"market": 0.08, "value": 0.03},
        )

        assert sheet.factor_attribution is not None
        assert len(sheet.factor_attribution.factors) == 2

    def test_tear_sheet_minimal(self):
        gen = TearSheetGenerator()
        port = _make_returns(50)

        sheet = gen.generate(portfolio_returns=port)
        assert sheet.metrics.total_days == 50
        assert sheet.benchmark_comparison is None
        assert sheet.brinson is None
        assert sheet.factor_attribution is None

    def test_generate_summary(self):
        gen = TearSheetGenerator()
        port = _make_returns(252)
        bm = _make_benchmark_returns(252)

        sheet = gen.generate(
            portfolio_returns=port,
            benchmark_returns=bm,
        )
        summary = gen.generate_summary(sheet)

        assert "total_return" in summary
        assert "sharpe_ratio" in summary
        assert "benchmark" in summary
        assert "tracking_error" in summary


class TestAttributionFullWorkflow:
    """Integration tests."""

    def test_complete_attribution_workflow(self):
        """End-to-end: metrics, brinson, factors, benchmark, tear sheet."""
        port = _make_returns(252, mean=0.0005, std=0.015)
        bm = _make_benchmark_returns(252)

        # 1. Compute metrics
        calc = MetricsCalculator()
        metrics = calc.compute(port)
        assert metrics.total_return != 0
        assert metrics.sharpe_ratio != 0

        # 2. Brinson attribution
        brinson = BrinsonAnalyzer()
        ba = brinson.analyze(
            {"Tech": 0.40, "Finance": 0.30, "Health": 0.30},
            {"Tech": 0.30, "Finance": 0.35, "Health": 0.35},
            {"Tech": 0.15, "Finance": 0.08, "Health": 0.05},
            {"Tech": 0.12, "Finance": 0.06, "Health": 0.04},
        )
        assert abs(ba.active_return - ba.attribution_sum) < 1e-10

        # 3. Factor attribution
        factor = FactorAnalyzer()
        fa = factor.analyze(
            metrics.total_return,
            {"market": 1.05, "value": 0.2, "momentum": -0.1},
            {"market": 0.08, "value": 0.02, "momentum": -0.01},
        )
        assert abs(
            fa.factor_return_total + fa.specific_return - fa.portfolio_return
        ) < 1e-10

        # 4. Benchmark comparison
        benchmark = BenchmarkAnalyzer()
        bc = benchmark.compare(port, bm)
        assert bc.tracking_error > 0

        # 5. Tear sheet
        gen = TearSheetGenerator()
        sheet = gen.generate(
            portfolio_returns=port,
            benchmark_returns=bm,
            portfolio_sector_weights={"Tech": 0.40, "Finance": 0.30, "Health": 0.30},
            benchmark_sector_weights={"Tech": 0.30, "Finance": 0.35, "Health": 0.35},
            portfolio_sector_returns={"Tech": 0.15, "Finance": 0.08, "Health": 0.05},
            benchmark_sector_returns={"Tech": 0.12, "Finance": 0.06, "Health": 0.04},
            factor_exposures={"market": 1.05, "value": 0.2},
            factor_returns_dict={"market": 0.08, "value": 0.02},
            name="Full Report",
        )

        assert sheet.metrics.total_days == 252
        assert sheet.benchmark_comparison is not None
        assert sheet.brinson is not None
        assert sheet.factor_attribution is not None
        assert len(sheet.monthly_returns) > 0
        assert len(sheet.top_drawdowns) > 0
        assert len(sheet.rolling_sharpe) > 0


class TestAttributionModuleImports:
    """Test module exports."""

    def test_top_level_imports(self):
        from src.attribution import (
            AttributionMethod, AttributionLevel, BenchmarkType,
            TimePeriod, RiskMetricType,
            STANDARD_FACTORS, COMMON_BENCHMARKS,
            BenchmarkDefinition, AttributionConfig,
            SectorAttribution, BrinsonAttribution,
            FactorContribution, FactorAttribution,
            BenchmarkComparison, DrawdownPeriod,
            PerformanceMetrics, MonthlyReturns, TearSheet,
            BrinsonAnalyzer, FactorAnalyzer,
            BenchmarkAnalyzer, MetricsCalculator,
            TearSheetGenerator,
        )
