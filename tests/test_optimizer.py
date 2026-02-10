"""Tests for Portfolio Optimization & Construction (PRD-08)."""

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------
class TestOptimizationConfig:
    def test_defaults(self):
        from src.optimizer.config import OptimizationConfig
        cfg = OptimizationConfig()
        assert cfg.risk_aversion == 2.5
        assert cfg.tau == 0.05
        assert cfg.max_iterations == 1000
        assert cfg.risk_free_rate == 0.05

    def test_constraint_config_defaults(self):
        from src.optimizer.config import ConstraintConfig
        cfg = ConstraintConfig()
        assert cfg.max_weight == 0.15
        assert cfg.min_positions == 10
        assert cfg.max_sector_pct == 0.35
        assert cfg.max_turnover == 0.30

    def test_tax_config_defaults(self):
        from src.optimizer.config import TaxConfig
        cfg = TaxConfig()
        assert cfg.short_term_rate == 0.37
        assert cfg.long_term_rate == 0.20
        assert cfg.wash_sale_window_days == 30

    def test_portfolio_config_nesting(self):
        from src.optimizer.config import PortfolioConfig
        cfg = PortfolioConfig()
        assert cfg.optimization.risk_aversion == 2.5
        assert cfg.constraints.max_weight == 0.15
        assert cfg.tax.short_term_rate == 0.37


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_cov(n=5, seed=42):
    """Create a valid positive-definite covariance matrix."""
    rng = np.random.RandomState(seed)
    A = rng.randn(n, n) * 0.01
    cov = A @ A.T + np.eye(n) * 0.001
    symbols = [f"S{i}" for i in range(n)]
    return pd.DataFrame(cov, index=symbols, columns=symbols)


# Default weight bounds that are feasible for n=5 (5 * 0.30 = 1.50 > 1.0)
_DEFAULT_MAX_WEIGHT = 0.40


def _make_returns(n=5, periods=100, seed=42):
    """Create random return series."""
    rng = np.random.RandomState(seed)
    symbols = [f"S{i}" for i in range(n)]
    data = rng.randn(periods, n) * 0.02 + 0.0005
    return pd.DataFrame(data, columns=symbols)


def _make_expected_returns(n=5, seed=42):
    rng = np.random.RandomState(seed)
    symbols = [f"S{i}" for i in range(n)]
    return pd.Series(rng.rand(n) * 0.15 + 0.05, index=symbols)


# ---------------------------------------------------------------------------
# Mean-Variance Optimizer
# ---------------------------------------------------------------------------
class TestMeanVarianceOptimizer:
    def test_max_sharpe(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        er = _make_expected_returns()
        result = opt.max_sharpe(er, cov, max_weight=_DEFAULT_MAX_WEIGHT)
        assert result.converged
        assert result.method == "max_sharpe"
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4
        assert result.sharpe_ratio > 0

    def test_min_variance(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        result = opt.min_variance(cov, max_weight=_DEFAULT_MAX_WEIGHT)
        assert result.converged
        assert result.method == "min_variance"
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4
        assert result.expected_volatility > 0

    def test_optimize_target_return(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        er = _make_expected_returns()
        result = opt.optimize(er, cov, target_return=0.08, max_weight=_DEFAULT_MAX_WEIGHT)
        assert result.converged
        assert result.method == "mean_variance"
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4

    def test_optimize_none_target_calls_max_sharpe(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        er = _make_expected_returns()
        result = opt.optimize(er, cov, target_return=None)
        assert result.method == "max_sharpe"

    def test_weight_bounds(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        er = _make_expected_returns()
        result = opt.max_sharpe(er, cov, min_weight=0.05, max_weight=0.30)
        for w in result.weights.values():
            assert w >= 0.05 - 1e-6
            assert w <= 0.30 + 1e-6

    def test_efficient_frontier(self):
        from src.optimizer.objectives import MeanVarianceOptimizer
        opt = MeanVarianceOptimizer()
        cov = _make_cov()
        er = _make_expected_returns()
        frontier = opt.efficient_frontier(er, cov, n_points=5, max_weight=_DEFAULT_MAX_WEIGHT)
        assert len(frontier) >= 2
        for pt in frontier:
            assert pt.converged

    def test_result_to_dict(self):
        from src.optimizer.objectives import OptimizationResult
        r = OptimizationResult(weights={"A": 0.5, "B": 0.5}, method="test")
        d = r.to_dict()
        assert "weights" in d
        assert d["method"] == "test"

    def test_result_to_series(self):
        from src.optimizer.objectives import OptimizationResult
        r = OptimizationResult(weights={"A": 0.6, "B": 0.4})
        s = r.to_series()
        assert isinstance(s, pd.Series)
        assert abs(s.sum() - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Risk Parity
# ---------------------------------------------------------------------------
class TestRiskParityOptimizer:
    def test_optimize(self):
        from src.optimizer.objectives import RiskParityOptimizer
        opt = RiskParityOptimizer()
        cov = _make_cov()
        result = opt.optimize(cov)
        assert result.converged
        assert result.method == "risk_parity"
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4

    def test_risk_contributions_approx_equal(self):
        from src.optimizer.objectives import RiskParityOptimizer
        opt = RiskParityOptimizer()
        cov = _make_cov()
        result = opt.optimize(cov)
        weights = pd.Series(result.weights)
        rc = opt.get_risk_contributions(weights, cov)
        # All risk contributions should be roughly equal
        assert rc.std() < 0.15  # Loose bound

    def test_get_risk_contributions_sum_to_one(self):
        from src.optimizer.objectives import RiskParityOptimizer
        opt = RiskParityOptimizer()
        cov = _make_cov()
        weights = pd.Series(1.0 / len(cov), index=cov.index)
        rc = opt.get_risk_contributions(weights, cov)
        assert abs(rc.sum() - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# HRP
# ---------------------------------------------------------------------------
class TestHRPOptimizer:
    def test_optimize(self):
        from src.optimizer.objectives import HRPOptimizer
        opt = HRPOptimizer()
        returns = _make_returns()
        result = opt.optimize(returns)
        assert result.method == "hrp"
        assert result.converged
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4

    def test_all_weights_positive(self):
        from src.optimizer.objectives import HRPOptimizer
        opt = HRPOptimizer()
        returns = _make_returns()
        result = opt.optimize(returns)
        for w in result.weights.values():
            assert w > 0

    def test_hrp_volatility(self):
        from src.optimizer.objectives import HRPOptimizer
        opt = HRPOptimizer()
        returns = _make_returns()
        result = opt.optimize(returns)
        assert result.expected_volatility > 0


# ---------------------------------------------------------------------------
# Black-Litterman
# ---------------------------------------------------------------------------
class TestBlackLitterman:
    def test_implied_equilibrium(self):
        from src.optimizer.black_litterman import BlackLittermanModel
        bl = BlackLittermanModel()
        cov = _make_cov()
        mkt_w = pd.Series(1.0 / len(cov), index=cov.index)
        pi = bl.implied_equilibrium_returns(cov, mkt_w)
        assert len(pi) == len(cov)
        assert all(np.isfinite(pi))

    def test_posterior_no_views(self):
        from src.optimizer.black_litterman import BlackLittermanModel
        bl = BlackLittermanModel()
        cov = _make_cov()
        mkt_w = pd.Series(1.0 / len(cov), index=cov.index)
        result = bl.compute_posterior(cov, mkt_w, views=[])
        assert len(result.posterior_returns) == len(cov)
        # With no views, posterior == prior
        pd.testing.assert_series_equal(result.prior_returns, result.posterior_returns)

    def test_posterior_with_absolute_view(self):
        from src.optimizer.black_litterman import BlackLittermanModel, View
        bl = BlackLittermanModel()
        cov = _make_cov()
        mkt_w = pd.Series(1.0 / len(cov), index=cov.index)
        views = [View(assets=["S0"], weights=[1], expected_return=0.20, confidence=0.9)]
        result = bl.compute_posterior(cov, mkt_w, views)
        # With a bullish view on S0, posterior for S0 should be > prior
        assert result.posterior_returns["S0"] > result.prior_returns["S0"]

    def test_posterior_with_relative_view(self):
        from src.optimizer.black_litterman import BlackLittermanModel, View
        bl = BlackLittermanModel()
        cov = _make_cov()
        mkt_w = pd.Series(1.0 / len(cov), index=cov.index)
        views = [View(assets=["S0", "S1"], weights=[1, -1], expected_return=0.05, confidence=0.7)]
        result = bl.compute_posterior(cov, mkt_w, views)
        # S0 should have higher posterior than S1 (relative to prior spread)
        prior_spread = result.prior_returns["S0"] - result.prior_returns["S1"]
        post_spread = result.posterior_returns["S0"] - result.posterior_returns["S1"]
        assert post_spread > prior_spread

    def test_bl_result_to_dict(self):
        from src.optimizer.black_litterman import BLResult
        r = BLResult(
            prior_returns=pd.Series({"A": 0.1}),
            posterior_returns=pd.Series({"A": 0.12}),
        )
        d = r.to_dict()
        assert "prior_returns" in d
        assert "posterior_returns" in d

    def test_high_confidence_view_dominates(self):
        from src.optimizer.black_litterman import BlackLittermanModel, View
        bl = BlackLittermanModel()
        cov = _make_cov()
        mkt_w = pd.Series(1.0 / len(cov), index=cov.index)

        # Very high confidence view
        views = [View(assets=["S0"], weights=[1], expected_return=0.50, confidence=0.99)]
        result = bl.compute_posterior(cov, mkt_w, views)
        # Posterior should be much closer to view than prior
        assert result.posterior_returns["S0"] > result.prior_returns["S0"] * 2


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------
class TestConstraints:
    def test_position_constraint_satisfied(self):
        from src.optimizer.constraints import PositionConstraint
        c = PositionConstraint(max_pct=0.20)
        w = pd.Series({"A": 0.15, "B": 0.15, "C": 0.70})
        assert not c.check(w)  # C > 0.20

    def test_position_constraint_passed(self):
        from src.optimizer.constraints import PositionConstraint
        c = PositionConstraint(max_pct=0.40)
        w = pd.Series({"A": 0.30, "B": 0.30, "C": 0.40})
        assert c.check(w)

    def test_position_constraint_violation(self):
        from src.optimizer.constraints import PositionConstraint
        c = PositionConstraint(max_pct=0.20)
        w = pd.Series({"A": 0.50, "B": 0.50})
        v = c.violation(w)
        assert v > 0

    def test_sector_constraint(self):
        from src.optimizer.constraints import SectorConstraint
        c = SectorConstraint(max_pct=0.40)
        w = pd.Series({"A": 0.30, "B": 0.30, "C": 0.40})
        sectors = {"A": "Tech", "B": "Tech", "C": "Health"}
        assert not c.check(w, sectors=sectors)  # Tech = 60% > 40%

    def test_sector_constraint_satisfied(self):
        from src.optimizer.constraints import SectorConstraint
        c = SectorConstraint(max_pct=0.60)
        w = pd.Series({"A": 0.20, "B": 0.20, "C": 0.20, "D": 0.20, "E": 0.20})
        sectors = {"A": "Tech", "B": "Tech", "C": "Health", "D": "Fin", "E": "Energy"}
        assert c.check(w, sectors=sectors)

    def test_turnover_constraint(self):
        from src.optimizer.constraints import TurnoverConstraint
        c = TurnoverConstraint(max_one_way=0.10)
        new = pd.Series({"A": 0.30, "B": 0.70})
        old = pd.Series({"A": 0.50, "B": 0.50})
        assert not c.check(new, current_weights=old)  # 20% one-way > 10%

    def test_turnover_constraint_no_previous(self):
        from src.optimizer.constraints import TurnoverConstraint
        c = TurnoverConstraint(max_one_way=0.10)
        w = pd.Series({"A": 0.50, "B": 0.50})
        assert c.check(w)

    def test_count_constraint(self):
        from src.optimizer.constraints import CountConstraint
        c = CountConstraint(min_n=3, max_n=5)
        w = pd.Series({"A": 0.5, "B": 0.5})  # Only 2
        assert not c.check(w)

    def test_count_constraint_satisfied(self):
        from src.optimizer.constraints import CountConstraint
        c = CountConstraint(min_n=2, max_n=5)
        w = pd.Series({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})
        assert c.check(w)

    def test_constraint_engine_validate(self):
        from src.optimizer.constraints import ConstraintEngine, PositionConstraint
        engine = ConstraintEngine()
        engine.add(PositionConstraint(name="pos_limit", max_pct=0.20))
        w = pd.Series({"A": 0.50, "B": 0.50})
        violations = engine.validate(w)
        assert len(violations) == 1
        assert violations[0]["type"] == "position"

    def test_constraint_engine_is_feasible(self):
        from src.optimizer.constraints import ConstraintEngine, PositionConstraint
        engine = ConstraintEngine()
        engine.add(PositionConstraint(max_pct=0.60))
        w = pd.Series({"A": 0.50, "B": 0.50})
        assert engine.is_feasible(w)

    def test_constraint_engine_defaults(self):
        from src.optimizer.constraints import ConstraintEngine
        engine = ConstraintEngine()
        engine.add_default_constraints()
        constraints = engine.get_constraints()
        assert len(constraints) == 4
        types = {c.constraint_type for c in constraints}
        assert types == {"position", "sector", "count", "turnover"}

    def test_inactive_constraint_skipped(self):
        from src.optimizer.constraints import PositionConstraint, ConstraintEngine
        c = PositionConstraint(max_pct=0.10, active=False)
        engine = ConstraintEngine()
        engine.add(c)
        w = pd.Series({"A": 0.50, "B": 0.50})
        assert engine.is_feasible(w)  # Inactive, so no violation


# ---------------------------------------------------------------------------
# Tax-Loss Harvesting
# ---------------------------------------------------------------------------
class TestTaxLossHarvester:
    def _make_positions(self):
        from src.optimizer.tax import Position
        return [
            Position(symbol="AAPL", shares=100, cost_basis=180, current_price=150, purchase_date="2025-03-01", sector="Tech"),
            Position(symbol="MSFT", shares=50, cost_basis=300, current_price=320, purchase_date="2024-06-01", sector="Tech"),
            Position(symbol="XOM", shares=200, cost_basis=110, current_price=90, purchase_date="2025-09-01", sector="Energy"),
        ]

    def test_identify_candidates(self):
        from src.optimizer.tax import TaxLossHarvester
        harvester = TaxLossHarvester()
        positions = self._make_positions()
        candidates = harvester.identify_candidates(positions)
        # AAPL: -3000 loss, XOM: -4000 loss. MSFT has gain.
        assert len(candidates) == 2
        symbols = {c.position.symbol for c in candidates}
        assert "MSFT" not in symbols

    def test_candidates_sorted_by_savings(self):
        from src.optimizer.tax import TaxLossHarvester
        harvester = TaxLossHarvester()
        positions = self._make_positions()
        candidates = harvester.identify_candidates(positions)
        if len(candidates) >= 2:
            assert candidates[0].estimated_tax_savings >= candidates[1].estimated_tax_savings

    def test_wash_sale_detection(self):
        from src.optimizer.tax import TaxLossHarvester
        harvester = TaxLossHarvester()
        positions = self._make_positions()
        candidates = harvester.identify_candidates(positions, recent_sales=["AAPL"])
        aapl_cand = [c for c in candidates if c.position.symbol == "AAPL"]
        assert len(aapl_cand) == 1
        assert aapl_cand[0].wash_sale_risk is True

    def test_position_properties(self):
        from src.optimizer.tax import Position
        pos = Position(symbol="TEST", shares=100, cost_basis=100, current_price=120)
        assert pos.market_value == 12000
        assert pos.unrealized_pnl == 2000
        assert abs(pos.unrealized_pnl_pct - 0.20) < 1e-6
        assert pos.holding_days == 0  # No purchase date

    def test_position_long_term(self):
        from src.optimizer.tax import Position
        pos = Position(symbol="TEST", shares=10, cost_basis=50, current_price=60, purchase_date="2024-01-01")
        assert pos.is_long_term  # > 365 days

    def test_position_short_term(self):
        from src.optimizer.tax import Position
        pos = Position(symbol="TEST", shares=10, cost_basis=50, current_price=60, purchase_date="2025-12-01")
        assert not pos.is_long_term

    def test_estimate_annual_savings(self):
        from src.optimizer.tax import TaxLossHarvester
        harvester = TaxLossHarvester()
        positions = self._make_positions()
        candidates = harvester.identify_candidates(positions)
        savings = harvester.estimate_annual_savings(candidates)
        assert savings["total_tax_savings"] > 0
        assert savings["num_candidates"] == len(candidates)

    def test_find_replacement_same_sector(self):
        from src.optimizer.tax import TaxLossHarvester, Position
        harvester = TaxLossHarvester()
        pos = Position(symbol="AAPL", sector="Tech")
        universe = pd.DataFrame(
            {"sector": ["Tech", "Tech", "Health"]},
            index=["MSFT", "GOOG", "JNJ"],
        )
        replacement = harvester.find_replacement(pos, universe)
        assert replacement in ["MSFT", "GOOG"]

    def test_find_replacement_no_peers(self):
        from src.optimizer.tax import TaxLossHarvester, Position
        harvester = TaxLossHarvester()
        pos = Position(symbol="AAPL", sector="Tech")
        universe = pd.DataFrame(
            {"sector": ["Health", "Health"]},
            index=["JNJ", "PFE"],
        )
        # No tech peers in universe, returns empty string
        replacement = harvester.find_replacement(pos, universe)
        assert replacement == ""

    def test_harvest_candidate_to_dict(self):
        from src.optimizer.tax import HarvestCandidate, Position
        hc = HarvestCandidate(
            position=Position(symbol="X"),
            unrealized_loss=-500,
            estimated_tax_savings=185,
        )
        d = hc.to_dict()
        assert d["symbol"] == "X"
        assert d["unrealized_loss"] == -500


# ---------------------------------------------------------------------------
# Tax-Aware Rebalancer
# ---------------------------------------------------------------------------
class TestTaxAwareRebalancer:
    def test_generate_trades(self):
        from src.optimizer.tax import TaxAwareRebalancer, Position
        rebalancer = TaxAwareRebalancer()
        current = pd.Series({"A": 0.40, "B": 0.30, "C": 0.30})
        target = pd.Series({"A": 0.30, "B": 0.40, "C": 0.30})
        positions = [
            Position(symbol="A", shares=40, cost_basis=100, current_price=90, purchase_date="2025-06-01"),
            Position(symbol="B", shares=30, cost_basis=80, current_price=100, purchase_date="2025-01-01"),
            Position(symbol="C", shares=30, cost_basis=100, current_price=100, purchase_date="2025-01-01"),
        ]
        trades = rebalancer.generate_trades(current, target, positions)
        assert len(trades) == 2  # A sell, B buy
        actions = {t.symbol: t.action for t in trades}
        assert actions["A"] == "sell"
        assert actions["B"] == "buy"

    def test_sell_losers_first_priority(self):
        from src.optimizer.tax import TaxAwareRebalancer, Position
        rebalancer = TaxAwareRebalancer()
        current = pd.Series({"LOSER": 0.30, "WINNER": 0.30, "NEW": 0.0, "HOLD": 0.40})
        target = pd.Series({"LOSER": 0.10, "WINNER": 0.10, "NEW": 0.40, "HOLD": 0.40})
        positions = [
            Position(symbol="LOSER", shares=30, cost_basis=100, current_price=80, purchase_date="2025-06-01"),
            Position(symbol="WINNER", shares=30, cost_basis=50, current_price=80, purchase_date="2024-06-01"),
        ]
        trades = rebalancer.generate_trades(current, target, positions)
        sells = [t for t in trades if t.action == "sell"]
        assert len(sells) == 2
        # Loser should have lower priority number (execute first)
        loser_t = [t for t in sells if t.symbol == "LOSER"][0]
        winner_t = [t for t in sells if t.symbol == "WINNER"][0]
        assert loser_t.priority < winner_t.priority

    def test_estimate_rebalance_tax(self):
        from src.optimizer.tax import TaxAwareRebalancer, RebalanceTrade
        rebalancer = TaxAwareRebalancer()
        trades = [
            RebalanceTrade(symbol="A", action="sell", value=1000, tax_impact=100),
            RebalanceTrade(symbol="B", action="sell", value=500, tax_impact=-50),
            RebalanceTrade(symbol="C", action="buy", value=1500, tax_impact=0),
        ]
        summary = rebalancer.estimate_rebalance_tax(trades)
        assert summary["net_tax_impact"] == 50
        assert summary["tax_cost"] == 100
        assert summary["tax_benefit"] == 50
        assert summary["num_sell_trades"] == 2
        assert summary["num_buy_trades"] == 1

    def test_rebalance_trade_to_dict(self):
        from src.optimizer.tax import RebalanceTrade
        t = RebalanceTrade(symbol="X", action="buy", value=1000)
        d = t.to_dict()
        assert d["symbol"] == "X"
        assert d["action"] == "buy"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
class TestTemplates:
    def test_all_templates_defined(self):
        from src.optimizer.templates import TEMPLATES
        expected = {
            "aggressive_alpha", "balanced_factor", "quality_income",
            "momentum_rider", "value_contrarian", "low_volatility",
            "risk_parity", "all_weather",
        }
        assert set(TEMPLATES.keys()) == expected

    def test_template_spec_to_dict(self):
        from src.optimizer.templates import TEMPLATES
        spec = TEMPLATES["aggressive_alpha"]
        d = spec.to_dict()
        assert d["name"] == "Aggressive Alpha"
        assert d["optimization_method"] == "max_sharpe"

    def test_portfolio_template_select_universe(self):
        from src.optimizer.templates import PortfolioTemplate, TEMPLATES
        template = PortfolioTemplate(TEMPLATES["aggressive_alpha"])
        factor_scores = pd.DataFrame({
            "momentum": [0.8, 0.6, 0.4, 0.9, 0.7, 0.3, 0.5, 0.2, 0.1, 0.95,
                          0.85, 0.65, 0.45, 0.35, 0.55],
            "quality": [0.7, 0.8, 0.5, 0.6, 0.9, 0.4, 0.3, 0.6, 0.2, 0.75,
                         0.65, 0.55, 0.45, 0.35, 0.25],
            "growth": [0.5, 0.7, 0.9, 0.4, 0.6, 0.8, 0.3, 0.5, 0.7, 0.45,
                        0.55, 0.65, 0.75, 0.85, 0.35],
            "value": [0.6, 0.5, 0.3, 0.7, 0.4, 0.6, 0.8, 0.3, 0.5, 0.55,
                       0.45, 0.35, 0.65, 0.75, 0.25],
        }, index=[f"S{i}" for i in range(15)])
        selected, scores = template.select_universe(factor_scores)
        assert 10 <= len(selected) <= 15

    def test_generate_initial_weights(self):
        from src.optimizer.templates import PortfolioTemplate, TEMPLATES
        # balanced_factor has max_weight=0.06, needs 17+ stocks to be feasible
        template = PortfolioTemplate(TEMPLATES["balanced_factor"])
        selected = [f"S{i}" for i in range(25)]
        scores = pd.Series([0.9 - i * 0.02 for i in range(25)], index=selected)
        weights = template.generate_initial_weights(selected, scores)
        assert abs(weights.sum() - 1.0) < 1e-6
        assert all(w <= template.spec.max_weight + 1e-6 for w in weights)

    def test_generate_weights_empty(self):
        from src.optimizer.templates import PortfolioTemplate, TemplateSpec
        template = PortfolioTemplate(TemplateSpec())
        weights = template.generate_initial_weights([], pd.Series(dtype=float))
        assert len(weights) == 0


class TestStrategyBlender:
    def test_blend(self):
        from src.optimizer.templates import StrategyBlender
        blender = StrategyBlender()
        w1 = pd.Series({"A": 0.5, "B": 0.5})
        w2 = pd.Series({"B": 0.5, "C": 0.5})
        combined = blender.blend([("s1", w1, 0.6), ("s2", w2, 0.4)])
        assert abs(combined.sum() - 1.0) < 1e-6
        assert "A" in combined.index
        assert "C" in combined.index

    def test_analyze_blend(self):
        from src.optimizer.templates import StrategyBlender
        blender = StrategyBlender()
        w1 = pd.Series({"A": 0.5, "B": 0.5})
        w2 = pd.Series({"C": 0.5, "D": 0.5})
        analysis = blender.analyze_blend([("s1", w1, 0.5), ("s2", w2, 0.5)])
        assert analysis["num_positions"] == 4
        assert analysis["effective_n"] > 0

    def test_blend_from_templates(self):
        from src.optimizer.templates import StrategyBlender
        blender = StrategyBlender()
        factor_scores = pd.DataFrame({
            "momentum": np.random.rand(20),
            "quality": np.random.rand(20),
            "value": np.random.rand(20),
            "growth": np.random.rand(20),
            "volatility": np.random.rand(20),
        }, index=[f"S{i}" for i in range(20)])
        combined = blender.blend_from_templates(
            [("aggressive_alpha", 0.6), ("quality_income", 0.4)],
            factor_scores,
        )
        assert abs(combined.sum() - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
class TestPortfolioAnalytics:
    def test_compute_xray_basic(self):
        from src.optimizer.analytics import PortfolioAnalytics
        analytics = PortfolioAnalytics()
        weights = pd.Series({"A": 0.3, "B": 0.3, "C": 0.4})
        xray = analytics.compute_xray(weights)
        assert xray.num_positions == 3
        assert abs(xray.total_weight - 1.0) < 1e-6

    def test_xray_with_cov(self):
        from src.optimizer.analytics import PortfolioAnalytics
        analytics = PortfolioAnalytics()
        cov = _make_cov(3)
        weights = pd.Series(1.0 / 3, index=cov.index)
        xray = analytics.compute_xray(weights, cov_matrix=cov)
        assert xray.portfolio_volatility > 0
        assert xray.var_95 < 0

    def test_xray_sectors(self):
        from src.optimizer.analytics import PortfolioAnalytics
        analytics = PortfolioAnalytics()
        weights = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
        sectors = {"A": "Tech", "B": "Tech", "C": "Health"}
        xray = analytics.compute_xray(weights, sectors=sectors)
        assert xray.sector_weights["Tech"] == pytest.approx(0.8, abs=1e-6)
        assert xray.sector_weights["Health"] == pytest.approx(0.2, abs=1e-6)

    def test_xray_concentration(self):
        from src.optimizer.analytics import PortfolioAnalytics
        analytics = PortfolioAnalytics()
        weights = pd.Series([0.30, 0.25, 0.20, 0.15, 0.05, 0.05], index=[f"S{i}" for i in range(6)])
        xray = analytics.compute_xray(weights)
        assert xray.top5_weight == pytest.approx(0.95, abs=1e-6)
        assert xray.hhi > 0
        assert xray.effective_n > 0

    def test_xray_to_dict(self):
        from src.optimizer.analytics import PortfolioXRay
        xray = PortfolioXRay(num_positions=10, portfolio_volatility=0.15)
        d = xray.to_dict()
        assert d["num_positions"] == 10
        assert d["portfolio_volatility"] == 0.15

    def test_compute_risk_contribution(self):
        from src.optimizer.analytics import PortfolioAnalytics
        analytics = PortfolioAnalytics()
        cov = _make_cov(3)
        weights = pd.Series(1.0 / 3, index=cov.index)
        rc = analytics.compute_risk_contribution(weights, cov)
        assert abs(rc.sum() - 1.0) < 1e-6


class TestWhatIfAnalyzer:
    def test_analyze_basic(self):
        from src.optimizer.analytics import WhatIfAnalyzer
        analyzer = WhatIfAnalyzer()
        weights = pd.Series({"A": 0.5, "B": 0.5})
        result = analyzer.analyze(weights, changes={"A": -0.1, "B": 0.1})
        # Should have some impact info
        assert isinstance(result.risk_change, float)

    def test_analyze_with_cov(self):
        from src.optimizer.analytics import WhatIfAnalyzer
        analyzer = WhatIfAnalyzer()
        cov = _make_cov(3)
        weights = pd.Series(1.0 / 3, index=cov.index)
        result = analyzer.analyze(
            weights,
            changes={"S0": 0.1, "S1": -0.1},
            cov_matrix=cov,
        )
        assert result.new_volatility > 0

    def test_analyze_with_returns(self):
        from src.optimizer.analytics import WhatIfAnalyzer
        analyzer = WhatIfAnalyzer()
        cov = _make_cov(3)
        er = _make_expected_returns(3)
        weights = pd.Series(1.0 / 3, index=cov.index)
        result = analyzer.analyze(
            weights,
            changes={"S0": 0.1, "S1": -0.1},
            cov_matrix=cov,
            expected_returns=er,
        )
        assert result.new_return > 0 or result.new_return <= 0  # Just not NaN
        assert np.isfinite(result.new_sharpe)

    def test_analyze_sector_impact(self):
        from src.optimizer.analytics import WhatIfAnalyzer
        analyzer = WhatIfAnalyzer()
        weights = pd.Series({"A": 0.5, "B": 0.5})
        sectors = {"A": "Tech", "B": "Health"}
        result = analyzer.analyze(
            weights,
            changes={"A": 0.1, "B": -0.1},
            sectors=sectors,
        )
        assert len(result.sector_impact) > 0

    def test_whatif_result_to_dict(self):
        from src.optimizer.analytics import WhatIfResult
        r = WhatIfResult(risk_change=0.01, return_change=-0.005)
        d = r.to_dict()
        assert d["risk_change"] == 0.01
        assert d["return_change"] == -0.005


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
class TestOptimizerModuleImports:
    def test_import_all(self):
        from src.optimizer import (
            OptimizationConfig,
            ConstraintConfig,
            TaxConfig,
            PortfolioConfig,
            MeanVarianceOptimizer,
            RiskParityOptimizer,
            HRPOptimizer,
            OptimizationResult,
            BlackLittermanModel,
            View,
            BLResult,
            ConstraintEngine,
            PositionConstraint,
            SectorConstraint,
            TurnoverConstraint,
            CountConstraint,
            TaxLossHarvester,
            TaxAwareRebalancer,
            Position,
            HarvestCandidate,
            RebalanceTrade,
            PortfolioTemplate,
            StrategyBlender,
            TemplateSpec,
            TEMPLATES,
            PortfolioAnalytics,
            PortfolioXRay,
            WhatIfAnalyzer,
            WhatIfResult,
        )
        assert OptimizationConfig is not None
        assert len(TEMPLATES) == 8
