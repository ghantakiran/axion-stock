"""Tests for PRD-59: Performance Attribution Extensions."""

import numpy as np
import pytest

from src.attribution.multi_period import (
    PeriodAttribution,
    LinkedAttribution,
    CumulativeEffect,
    MultiPeriodAttribution,
)
from src.attribution.fama_french import (
    FFFactorExposure,
    FFModelResult,
    FFComparison,
    FamaFrenchAnalyzer,
)
from src.attribution.geographic import (
    CountryAttribution,
    RegionAttribution,
    GeographicAttribution,
    GeographicAnalyzer,
)
from src.attribution.risk_adjusted import (
    RiskAdjustedMetrics,
    MetricComparison,
    RiskAdjustedReport,
    RiskAdjustedAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _daily_returns(n: int = 252, mu: float = 0.0004, sigma: float = 0.015, seed: int = 42):
    return list(np.random.RandomState(seed).normal(mu, sigma, n))


def _benchmark_returns(n: int = 252, seed: int = 99):
    return list(np.random.RandomState(seed).normal(0.0003, 0.012, n))


def _ff_factors(n: int = 252, seed: int = 42):
    rng = np.random.RandomState(seed)
    mkt = rng.normal(0.0004, 0.012, n)
    smb = rng.normal(0.0001, 0.006, n)
    hml = rng.normal(0.0001, 0.005, n)
    rmw = rng.normal(0.0001, 0.004, n)
    cma = rng.normal(0.00005, 0.003, n)
    # Portfolio = factor exposure + noise
    port = 0.001 + 1.1 * mkt + 0.3 * smb - 0.2 * hml + rng.normal(0, 0.005, n)
    return {
        "portfolio": list(port),
        "mkt_rf": list(mkt),
        "smb": list(smb),
        "hml": list(hml),
        "rmw": list(rmw),
        "cma": list(cma),
    }


def _period_data():
    """Multi-period attribution test data."""
    return {
        "p_returns": [0.02, 0.01, -0.005, 0.015],
        "b_returns": [0.015, 0.008, -0.002, 0.01],
        "allocs": [0.003, 0.001, -0.001, 0.002],
        "selects": [0.001, 0.001, -0.002, 0.002],
        "inters": [0.001, 0.0, -0.0, 0.001],
        "labels": ["Q1", "Q2", "Q3", "Q4"],
    }


# ---------------------------------------------------------------------------
# PeriodAttribution / LinkedAttribution
# ---------------------------------------------------------------------------
class TestPeriodAttribution:
    def test_total_effect(self):
        p = PeriodAttribution(
            allocation_effect=0.003, selection_effect=0.001, interaction_effect=0.001
        )
        assert p.total_effect == pytest.approx(0.005)


class TestLinkedAttribution:
    def test_linked_total(self):
        la = LinkedAttribution(
            linked_allocation=0.005, linked_selection=0.003, linked_interaction=0.001
        )
        assert la.linked_total == pytest.approx(0.009)

    def test_residual(self):
        la = LinkedAttribution(
            total_active_return=0.01,
            linked_allocation=0.005, linked_selection=0.003, linked_interaction=0.001
        )
        assert la.residual == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# MultiPeriodAttribution
# ---------------------------------------------------------------------------
class TestMultiPeriodAttribution:
    def test_carino_linking(self):
        data = _period_data()
        mpa = MultiPeriodAttribution()
        result = mpa.link_carino(
            data["p_returns"], data["b_returns"],
            data["allocs"], data["selects"], data["inters"],
            data["labels"],
        )
        assert result.n_periods == 4
        assert result.linking_method == "carino"
        assert len(result.periods) == 4
        assert result.periods[0].period_label == "Q1"
        # Linked effects should approximately sum to active return
        assert abs(result.residual) < 0.01

    def test_geometric_linking(self):
        data = _period_data()
        mpa = MultiPeriodAttribution()
        result = mpa.link_geometric(
            data["p_returns"], data["b_returns"],
            data["allocs"], data["selects"], data["inters"],
        )
        assert result.n_periods == 4
        assert result.linking_method == "geometric"
        assert result.linked_allocation != 0

    def test_empty_periods(self):
        mpa = MultiPeriodAttribution()
        result = mpa.link_carino([], [], [], [], [])
        assert result.n_periods == 0

    def test_single_period(self):
        mpa = MultiPeriodAttribution()
        result = mpa.link_carino([0.05], [0.03], [0.01], [0.005], [0.005])
        assert result.n_periods == 1
        assert result.total_active_return == pytest.approx(0.02, abs=0.001)

    def test_cumulative_effects(self):
        data = _period_data()
        mpa = MultiPeriodAttribution()
        linked = mpa.link_carino(
            data["p_returns"], data["b_returns"],
            data["allocs"], data["selects"], data["inters"],
            data["labels"],
        )
        cum = mpa.cumulative_effects(linked)
        assert len(cum.period_labels) == 4
        assert len(cum.cumulative_allocation) == 4
        # Cumulative should be monotonically building
        assert cum.cumulative_allocation[-1] == pytest.approx(
            sum(data["allocs"]), abs=0.001
        )

    def test_compound_return(self):
        assert MultiPeriodAttribution._compound_return([0.1, 0.1]) == pytest.approx(0.21)
        assert MultiPeriodAttribution._compound_return([]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# FFFactorExposure / FFModelResult
# ---------------------------------------------------------------------------
class TestFFFactorExposure:
    def test_is_significant(self):
        assert FFFactorExposure(t_statistic=2.5).is_significant is True
        assert FFFactorExposure(t_statistic=1.0).is_significant is False


class TestFFModelResult:
    def test_alpha_significant(self):
        assert FFModelResult(alpha_t_stat=3.0).alpha_is_significant is True
        assert FFModelResult(alpha_t_stat=1.5).alpha_is_significant is False

    def test_total_factor_return(self):
        r = FFModelResult(factors=[
            FFFactorExposure(contribution=0.01),
            FFFactorExposure(contribution=0.005),
        ])
        assert r.total_factor_return == pytest.approx(0.015)


class TestFFComparison:
    def test_r_squared_improvement(self):
        comp = FFComparison(
            ff3=FFModelResult(r_squared=0.85),
            ff5=FFModelResult(r_squared=0.90),
        )
        assert comp.r_squared_improvement == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# FamaFrenchAnalyzer
# ---------------------------------------------------------------------------
class TestFamaFrenchAnalyzer:
    def test_fit_ff3(self):
        data = _ff_factors()
        analyzer = FamaFrenchAnalyzer()
        result = analyzer.fit_ff3(
            data["portfolio"], data["mkt_rf"], data["smb"], data["hml"]
        )
        assert result.model_name == "ff3"
        assert len(result.factors) == 3
        assert result.r_squared > 0.3  # Should explain a decent portion
        assert result.n_observations == 252
        # Market beta should be close to 1.1
        mkt_beta = result.factors[0].beta
        assert 0.5 < mkt_beta < 2.0

    def test_fit_ff5(self):
        data = _ff_factors()
        analyzer = FamaFrenchAnalyzer()
        result = analyzer.fit_ff5(
            data["portfolio"], data["mkt_rf"], data["smb"],
            data["hml"], data["rmw"], data["cma"]
        )
        assert result.model_name == "ff5"
        assert len(result.factors) == 5

    def test_compare_models(self):
        data = _ff_factors()
        analyzer = FamaFrenchAnalyzer()
        comp = analyzer.compare_models(
            data["portfolio"], data["mkt_rf"], data["smb"],
            data["hml"], data["rmw"], data["cma"]
        )
        assert comp.preferred_model in ("ff3", "ff5")
        assert comp.reason != ""
        assert comp.ff3.r_squared > 0
        assert comp.ff5.r_squared > 0

    def test_alpha_summary(self):
        data = _ff_factors()
        analyzer = FamaFrenchAnalyzer()
        result = analyzer.fit_ff3(
            data["portfolio"], data["mkt_rf"], data["smb"], data["hml"]
        )
        summary = analyzer.alpha_summary(result)
        assert "alpha_daily" in summary
        assert "alpha_annualized" in summary
        assert "r_squared" in summary

    def test_insufficient_data(self):
        analyzer = FamaFrenchAnalyzer()
        result = analyzer.fit_ff3([0.01] * 5, [0.01] * 5, [0.0] * 5, [0.0] * 5)
        assert result.r_squared == 0.0


# ---------------------------------------------------------------------------
# CountryAttribution / GeographicAttribution
# ---------------------------------------------------------------------------
class TestCountryAttribution:
    def test_total_effect(self):
        ca = CountryAttribution(
            allocation_effect=0.002, selection_effect=0.001,
            interaction_effect=0.0005, currency_effect=0.001
        )
        assert ca.total_effect == pytest.approx(0.0045)

    def test_active_weight(self):
        ca = CountryAttribution(portfolio_weight=0.3, benchmark_weight=0.2)
        assert ca.active_weight == pytest.approx(0.1)


class TestRegionAttribution:
    def test_n_countries(self):
        ra = RegionAttribution(countries=[CountryAttribution(), CountryAttribution()])
        assert ra.n_countries == 2


class TestGeographicAttribution:
    def test_attribution_sum(self):
        ga = GeographicAttribution(
            total_allocation=0.01, total_selection=0.005,
            total_interaction=0.002, total_currency=0.001
        )
        assert ga.attribution_sum == pytest.approx(0.018)


# ---------------------------------------------------------------------------
# GeographicAnalyzer
# ---------------------------------------------------------------------------
class TestGeographicAnalyzer:
    def test_analyze_basic(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze(
            portfolio_weights={"US": 0.6, "GB": 0.25, "JP": 0.15},
            benchmark_weights={"US": 0.5, "GB": 0.3, "JP": 0.2},
            portfolio_returns={"US": 0.08, "GB": 0.05, "JP": 0.03},
            benchmark_returns={"US": 0.07, "GB": 0.04, "JP": 0.02},
        )
        assert result.n_countries == 3
        assert result.n_regions > 0
        assert result.portfolio_return != 0
        assert result.active_return != 0

    def test_analyze_with_currency(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze(
            portfolio_weights={"US": 0.5, "GB": 0.5},
            benchmark_weights={"US": 0.5, "GB": 0.5},
            portfolio_returns={"US": 0.05, "GB": 0.04},
            benchmark_returns={"US": 0.05, "GB": 0.04},
            currency_effects={"US": 0.0, "GB": -0.02},
        )
        assert result.total_currency != 0

    def test_analyze_empty(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze({}, {}, {}, {})
        assert result.n_countries == 0

    def test_region_aggregation(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze(
            portfolio_weights={"US": 0.4, "CA": 0.1, "GB": 0.3, "JP": 0.2},
            benchmark_weights={"US": 0.35, "CA": 0.15, "GB": 0.25, "JP": 0.25},
            portfolio_returns={"US": 0.06, "CA": 0.04, "GB": 0.03, "JP": 0.02},
            benchmark_returns={"US": 0.05, "CA": 0.03, "GB": 0.035, "JP": 0.025},
        )
        # Should have North America, Europe, Asia Pacific
        region_names = [r.region for r in result.regions]
        assert "North America" in region_names
        assert "Europe" in region_names
        assert "Asia Pacific" in region_names

    def test_top_contributors(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze(
            portfolio_weights={"US": 0.5, "GB": 0.3, "JP": 0.2},
            benchmark_weights={"US": 0.4, "GB": 0.35, "JP": 0.25},
            portfolio_returns={"US": 0.10, "GB": 0.03, "JP": 0.02},
            benchmark_returns={"US": 0.06, "GB": 0.04, "JP": 0.03},
        )
        top = analyzer.top_contributors(result, n=2)
        assert len(top) == 2

    def test_bottom_contributors(self):
        analyzer = GeographicAnalyzer()
        result = analyzer.analyze(
            portfolio_weights={"US": 0.5, "GB": 0.3, "JP": 0.2},
            benchmark_weights={"US": 0.4, "GB": 0.35, "JP": 0.25},
            portfolio_returns={"US": 0.10, "GB": 0.01, "JP": -0.01},
            benchmark_returns={"US": 0.06, "GB": 0.04, "JP": 0.03},
        )
        bottom = analyzer.bottom_contributors(result, n=2)
        assert len(bottom) == 2


# ---------------------------------------------------------------------------
# RiskAdjustedMetrics
# ---------------------------------------------------------------------------
class TestRiskAdjustedMetrics:
    def test_composite_score(self):
        m = RiskAdjustedMetrics(
            sharpe_ratio=1.5, omega_ratio=1.8,
            pain_ratio=2.0, tail_ratio=1.5,
        )
        assert 0 < m.composite_score <= 100


class TestMetricComparison:
    def test_structure(self):
        mc = MetricComparison(strategy_name="test", rank=1, composite_score=85)
        assert mc.strategy_name == "test"


class TestRiskAdjustedReport:
    def test_n_strategies(self):
        r = RiskAdjustedReport(strategies=[
            MetricComparison(), MetricComparison()
        ])
        assert r.n_strategies == 2


# ---------------------------------------------------------------------------
# RiskAdjustedAnalyzer
# ---------------------------------------------------------------------------
class TestRiskAdjustedAnalyzer:
    def test_compute_basic(self):
        returns = _daily_returns()
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        assert metrics.sharpe_ratio != 0
        assert metrics.sortino_ratio != 0
        assert metrics.omega_ratio > 0
        assert metrics.ulcer_index > 0

    def test_compute_with_benchmark(self):
        returns = _daily_returns()
        bm = _benchmark_returns()
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns, benchmark_returns=bm)
        assert metrics.treynor_ratio != 0
        assert metrics.m_squared != 0

    def test_m_squared_no_benchmark(self):
        returns = _daily_returns()
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        assert metrics.m_squared == 0.0

    def test_calmar_positive(self):
        rng = np.random.RandomState(42)
        returns = list(rng.normal(0.001, 0.01, 252))
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        assert metrics.calmar_ratio > 0

    def test_omega_all_positive(self):
        returns = [0.01] * 100
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        assert metrics.omega_ratio >= 10.0  # Capped

    def test_short_data(self):
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute([0.01] * 5)
        assert metrics.sharpe_ratio == 0.0

    def test_tail_ratio(self):
        returns = _daily_returns()
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        assert metrics.tail_ratio > 0

    def test_compare_strategies(self):
        analyzer = RiskAdjustedAnalyzer()
        strategies = {
            "aggressive": _daily_returns(mu=0.0008, sigma=0.025, seed=1),
            "conservative": _daily_returns(mu=0.0003, sigma=0.008, seed=2),
            "balanced": _daily_returns(mu=0.0005, sigma=0.015, seed=3),
        }
        report = analyzer.compare_strategies(strategies)
        assert report.n_strategies == 3
        assert report.best_strategy != ""
        assert report.strategies[0].rank == 1
        assert report.strategies[0].composite_score >= report.strategies[-1].composite_score

    def test_compare_empty(self):
        analyzer = RiskAdjustedAnalyzer()
        report = analyzer.compare_strategies({})
        assert report.n_strategies == 0

    def test_pain_and_martin_ratio(self):
        returns = _daily_returns()
        analyzer = RiskAdjustedAnalyzer()
        metrics = analyzer.compute(returns)
        # Pain and Martin ratios should be computed
        assert isinstance(metrics.pain_ratio, float)
        assert isinstance(metrics.martin_ratio, float)
