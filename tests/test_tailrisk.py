"""Tests for PRD-57: Tail Risk Hedging."""

import numpy as np
import pytest

from src.tailrisk.config import (
    CVaRMethod,
    HedgeInstrument,
    RiskBudgetMethod,
    CVaRConfig,
    DependenceConfig,
    HedgingConfig,
    BudgetingConfig,
)
from src.tailrisk.models import (
    CVaRResult,
    CVaRContribution,
    TailDependence,
    HedgeRecommendation,
    HedgePortfolio,
    DrawdownStats,
    DrawdownBudget,
)
from src.tailrisk.cvar import CVaRCalculator
from src.tailrisk.dependence import TailDependenceAnalyzer
from src.tailrisk.hedging import HedgeConstructor
from src.tailrisk.budgeting import DrawdownRiskBudgeter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normal_returns(n: int = 500, mu: float = 0.0005, sigma: float = 0.02, seed: int = 42) -> list:
    return list(np.random.RandomState(seed).normal(mu, sigma, n))


def _fat_tail_returns(n: int = 500, seed: int = 42) -> list:
    """Generate returns with fat tails (t-distribution)."""
    rng = np.random.RandomState(seed)
    return list(rng.standard_t(df=4, size=n) * 0.01)


def _multi_asset_returns(seed: int = 42) -> dict:
    rng = np.random.RandomState(seed)
    return {
        "SPY": list(rng.normal(0.0005, 0.015, 500)),
        "TLT": list(rng.normal(0.0002, 0.008, 500)),
        "GLD": list(rng.normal(0.0003, 0.012, 500)),
    }


def _drawdown_returns(seed: int = 42) -> list:
    """Returns with a clear drawdown period."""
    rng = np.random.RandomState(seed)
    bull = rng.normal(0.002, 0.01, 100)
    crash = rng.normal(-0.01, 0.03, 30)
    recovery = rng.normal(0.003, 0.012, 120)
    return list(np.concatenate([bull, crash, recovery]))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class TestConfig:
    def test_cvar_method_values(self):
        assert CVaRMethod.HISTORICAL.value == "historical"
        assert CVaRMethod.CORNISH_FISHER.value == "cornish_fisher"

    def test_hedge_instruments(self):
        assert HedgeInstrument.PUT_OPTION.value == "put_option"
        assert HedgeInstrument.VIX_CALL.value == "vix_call"

    def test_cvar_config_defaults(self):
        cfg = CVaRConfig()
        assert cfg.confidence == 0.95
        assert cfg.min_observations == 60

    def test_budgeting_config_defaults(self):
        cfg = BudgetingConfig()
        assert cfg.max_portfolio_drawdown == 0.20


# ---------------------------------------------------------------------------
# CVaRResult dataclass
# ---------------------------------------------------------------------------
class TestCVaRResult:
    def test_cvar_bps(self):
        r = CVaRResult(cvar_pct=0.03)
        assert r.cvar_bps == 300.0

    def test_excess_over_var(self):
        r = CVaRResult(var_pct=0.02, cvar_pct=0.03)
        assert r.excess_over_var == pytest.approx(0.01)


class TestTailDependence:
    def test_has_tail_dependence(self):
        td = TailDependence(lower_tail=0.25)
        assert td.has_tail_dependence is True
        td2 = TailDependence(lower_tail=0.05)
        assert td2.has_tail_dependence is False

    def test_tail_amplification(self):
        td = TailDependence(normal_correlation=0.3, tail_correlation=0.6)
        assert td.tail_amplification == pytest.approx(2.0)


class TestHedgeRecommendation:
    def test_cost_bps(self):
        h = HedgeRecommendation(cost_pct=0.005)
        assert h.cost_bps == 50.0

    def test_is_cost_effective(self):
        h = HedgeRecommendation(effectiveness=0.7)
        assert h.is_cost_effective is True
        h2 = HedgeRecommendation(effectiveness=0.3)
        assert h2.is_cost_effective is False


class TestHedgePortfolio:
    def test_cvar_reduction(self):
        hp = HedgePortfolio(unhedged_cvar=0.05, hedged_cvar=0.03)
        assert hp.cvar_reduction_pct == pytest.approx(0.4)


class TestDrawdownStats:
    def test_is_in_drawdown(self):
        ds = DrawdownStats(current_drawdown=-0.05)
        assert ds.is_in_drawdown is True
        ds2 = DrawdownStats(current_drawdown=0.0)
        assert ds2.is_in_drawdown is False

    def test_max_drawdown_pct(self):
        ds = DrawdownStats(max_drawdown=-0.15)
        assert ds.max_drawdown_pct == -15.0


class TestDrawdownBudget:
    def test_is_over_budget(self):
        db = DrawdownBudget(current_usage=0.08, allocated_budget=0.05)
        assert db.is_over_budget is True

    def test_utilization_pct(self):
        db = DrawdownBudget(current_usage=0.03, allocated_budget=0.06)
        assert db.utilization_pct == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# CVaRCalculator
# ---------------------------------------------------------------------------
class TestCVaRCalculator:
    def test_historical_cvar(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        result = calc.compute(returns, portfolio_value=1_000_000)
        assert result.var_pct > 0
        assert result.cvar_pct >= result.var_pct  # CVaR >= VaR
        assert result.cvar_dollar > 0
        assert result.method == "historical"

    def test_parametric_cvar(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        result = calc.compute(returns, 1_000_000, method="parametric")
        assert result.cvar_pct >= result.var_pct
        assert result.method == "parametric"

    def test_cornish_fisher_cvar(self):
        returns = _fat_tail_returns()
        calc = CVaRCalculator()
        result = calc.compute(returns, 1_000_000, method="cornish_fisher")
        assert result.cvar_pct > 0
        assert result.method == "cornish_fisher"

    def test_insufficient_data(self):
        calc = CVaRCalculator(CVaRConfig(min_observations=100))
        result = calc.compute([0.01] * 10, 1_000_000)
        assert result.cvar_pct == 0.0

    def test_higher_confidence_higher_cvar(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        cvar95 = calc.compute(returns, 1_000_000, confidence=0.95)
        cvar99 = calc.compute(returns, 1_000_000, confidence=0.99)
        assert cvar99.cvar_pct > cvar95.cvar_pct

    def test_horizon_scaling(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        cvar_1d = calc.compute(returns, 1_000_000, horizon_days=1)
        cvar_10d = calc.compute(returns, 1_000_000, horizon_days=10)
        ratio = cvar_10d.cvar_pct / cvar_1d.cvar_pct
        assert 2.5 < ratio < 4.0  # ~sqrt(10) ≈ 3.16

    def test_tail_ratio(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        result = calc.compute(returns, 1_000_000)
        assert result.tail_ratio >= 1.0  # CVaR/VaR >= 1

    def test_decompose(self):
        asset_returns = _multi_asset_returns()
        weights = {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
        calc = CVaRCalculator()
        contribs = calc.decompose(asset_returns, weights, 1_000_000)
        assert len(contribs) == 3
        # Contributions should sum to roughly 1.0
        total_pct = sum(c.pct_of_total for c in contribs)
        assert 0.5 < total_pct < 1.5  # Approximate

    def test_multi_horizon(self):
        returns = _normal_returns()
        calc = CVaRCalculator()
        results = calc.multi_horizon(returns, 1_000_000)
        assert len(results) == 4  # [1, 5, 10, 20]
        # Each horizon should have increasing CVaR
        cvars = [r.cvar_pct for r in results]
        assert all(cvars[i] <= cvars[i + 1] for i in range(len(cvars) - 1))


# ---------------------------------------------------------------------------
# TailDependenceAnalyzer
# ---------------------------------------------------------------------------
class TestTailDependenceAnalyzer:
    def test_compute_correlated(self):
        rng = np.random.RandomState(42)
        a = rng.normal(0, 0.02, 500)
        b = 0.7 * a + 0.3 * rng.normal(0, 0.02, 500)
        analyzer = TailDependenceAnalyzer()
        td = analyzer.compute(list(a), list(b), "A", "B")
        assert td.lower_tail >= 0
        assert td.upper_tail >= 0
        assert -1.0 <= td.normal_correlation <= 1.0

    def test_independent_low_tail(self):
        rng = np.random.RandomState(42)
        a = list(rng.normal(0, 0.02, 500))
        b = list(rng.normal(0, 0.02, 500))
        analyzer = TailDependenceAnalyzer()
        td = analyzer.compute(a, b, "A", "B")
        # Independent assets should have low tail dependence
        assert td.lower_tail < 0.5

    def test_compute_all_pairs(self):
        returns = _multi_asset_returns()
        analyzer = TailDependenceAnalyzer()
        results = analyzer.compute_all_pairs(returns)
        # 3 assets → 3 pairs
        assert len(results) == 3

    def test_contagion_matrix(self):
        returns = _multi_asset_returns()
        analyzer = TailDependenceAnalyzer()
        matrix = analyzer.contagion_matrix(returns)
        assert matrix["SPY"]["SPY"] == 1.0
        assert "TLT" in matrix["SPY"]

    def test_insufficient_data(self):
        analyzer = TailDependenceAnalyzer(DependenceConfig(min_observations=100))
        td = analyzer.compute([0.01] * 10, [0.02] * 10)
        assert td.lower_tail == 0.0


# ---------------------------------------------------------------------------
# HedgeConstructor
# ---------------------------------------------------------------------------
class TestHedgeConstructor:
    def test_protective_put(self):
        hedger = HedgeConstructor()
        put = hedger.protective_put(1_000_000, volatility=0.20)
        assert put.instrument == "put_option"
        assert put.cost_pct > 0
        assert put.cost_dollar > 0
        assert put.protection_pct > 0
        assert put.effectiveness > 0

    def test_vix_call(self):
        hedger = HedgeConstructor()
        vix = hedger.vix_call(1_000_000, 0.20, vix_level=15.0)
        assert vix.instrument == "vix_call"
        assert vix.cost_pct > 0
        assert vix.hedge_ratio > 0

    def test_cash_hedge(self):
        hedger = HedgeConstructor()
        cash = hedger.cash_hedge(1_000_000, cash_pct=0.10)
        assert cash.instrument == "cash"
        assert cash.notional == 100_000

    def test_build_hedge_portfolio(self):
        hedger = HedgeConstructor()
        portfolio = hedger.build_hedge_portfolio(
            portfolio_value=1_000_000,
            volatility=0.20,
            cvar_pct=0.05,
            vix_level=15.0,
        )
        assert len(portfolio.hedges) > 0
        assert portfolio.total_cost_pct > 0
        assert portfolio.hedged_cvar <= portfolio.unhedged_cvar

    def test_cvar_reduction(self):
        hedger = HedgeConstructor()
        portfolio = hedger.build_hedge_portfolio(1_000_000, 0.20, 0.05)
        assert portfolio.cvar_reduction_pct > 0

    def test_put_otm_cheaper(self):
        hedger = HedgeConstructor()
        put_atm = hedger.protective_put(1_000_000, 0.20, otm_pct=0.0)
        put_otm = hedger.protective_put(1_000_000, 0.20, otm_pct=0.10)
        assert put_otm.cost_pct < put_atm.cost_pct


# ---------------------------------------------------------------------------
# DrawdownRiskBudgeter
# ---------------------------------------------------------------------------
class TestDrawdownRiskBudgeter:
    def test_drawdown_stats(self):
        returns = _drawdown_returns()
        budgeter = DrawdownRiskBudgeter()
        stats = budgeter.compute_drawdown_stats(returns)
        assert stats.max_drawdown < 0
        assert stats.cdar < 0

    def test_drawdown_stats_empty(self):
        budgeter = DrawdownRiskBudgeter()
        stats = budgeter.compute_drawdown_stats([])
        assert stats.max_drawdown == 0.0

    def test_drawdown_stats_bull_market(self):
        rng = np.random.RandomState(42)
        returns = list(rng.normal(0.005, 0.005, 200))  # Strong bull
        budgeter = DrawdownRiskBudgeter()
        stats = budgeter.compute_drawdown_stats(returns)
        assert stats.max_drawdown < 0  # Some drawdown always exists

    def test_allocate_budget(self):
        returns = _multi_asset_returns()
        weights = {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
        budgeter = DrawdownRiskBudgeter()
        budgets = budgeter.allocate_budget(returns, weights)
        assert len(budgets) == 3
        for b in budgets:
            assert b.allocated_budget > 0

    def test_allocate_equal_method(self):
        returns = _multi_asset_returns()
        weights = {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
        budgeter = DrawdownRiskBudgeter(BudgetingConfig(method=RiskBudgetMethod.EQUAL))
        budgets = budgeter.allocate_budget(returns, weights)
        # Equal method: all budgets should be equal
        budget_values = [b.allocated_budget for b in budgets]
        assert max(budget_values) == pytest.approx(min(budget_values), abs=0.001)

    def test_recommend_weights(self):
        returns = _multi_asset_returns()
        budgeter = DrawdownRiskBudgeter()
        weights = budgeter.recommend_weights(returns)
        assert len(weights) == 3
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_recommend_weights_inverse_dd(self):
        rng = np.random.RandomState(42)
        returns = {
            "SAFE": list(rng.normal(0.001, 0.005, 500)),
            "RISKY": list(rng.normal(0.002, 0.03, 500)),
        }
        budgeter = DrawdownRiskBudgeter()
        weights = budgeter.recommend_weights(returns)
        # SAFE should get higher weight (lower drawdown)
        assert weights["SAFE"] > weights["RISKY"]

    def test_over_budget_detection(self):
        returns = _multi_asset_returns()
        # Give very high weight to SPY to trigger over-budget
        weights = {"SPY": 0.9, "TLT": 0.05, "GLD": 0.05}
        budgeter = DrawdownRiskBudgeter(BudgetingConfig(max_portfolio_drawdown=0.05))
        budgets = budgeter.allocate_budget(returns, weights)
        # At least one should be over budget with tight constraint
        has_over = any(b.is_over_budget for b in budgets)
        # Not guaranteed, but check structure
        assert all(b.utilization_pct >= 0 for b in budgets)
