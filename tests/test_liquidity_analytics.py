"""Tests for PRD-62: Liquidity Risk Analytics."""

import pytest
import numpy as np

from src.liquidity.spread_model import (
    RollSpreadEstimate,
    SpreadDecomposition,
    SpreadForecast,
    SpreadRegimeProfile,
    SpreadModeler,
)
from src.liquidity.depth_analyzer import (
    DepthSnapshot,
    DepthResilience,
    TopOfBookImbalance,
    DepthProfile,
    MarketDepthAnalyzer,
)
from src.liquidity.liquidity_premium import (
    AmihudRatio,
    PastorStambaughFactor,
    IlliquidityPremium,
    CrossSectionalPremium,
    IlliquidityPremiumEstimator,
)
from src.liquidity.concentration import (
    PositionLiquidity,
    ConcentrationMetrics,
    LiquidityLimit,
    LiquidityRiskReport,
    LiquidityConcentrationAnalyzer,
)
from src.liquidity.cost_curve import (
    CostPoint,
    CostCurve,
    CostComparison,
    OptimalExecution,
    CostCurveBuilder,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _prices(n=100, start=100.0, vol=0.02, seed=42):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, vol, n)
    prices = [start]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices


def _order_book():
    mid = 150.0
    bids = [
        {"price": mid - 0.01 * (i + 1), "quantity": 500 + i * 100}
        for i in range(5)
    ]
    asks = [
        {"price": mid + 0.01 * (i + 1), "quantity": 400 + i * 100}
        for i in range(5)
    ]
    return bids, asks, mid


def _holdings():
    return [
        {"symbol": "AAPL", "value": 5_000_000, "adv_usd": 8_000_000_000},
        {"symbol": "MSFT", "value": 3_000_000, "adv_usd": 5_000_000_000},
        {"symbol": "ILLQ", "value": 2_000_000, "adv_usd": 1_000_000},
    ]


# ---------------------------------------------------------------------------
# Spread Model
# ---------------------------------------------------------------------------
class TestRollSpreadEstimate:
    def test_spread_bps(self):
        r = RollSpreadEstimate(estimated_spread=0.001)
        assert r.spread_bps == pytest.approx(10.0)

    def test_is_liquid(self):
        assert RollSpreadEstimate(estimated_spread=0.0005).is_liquid is True
        assert RollSpreadEstimate(estimated_spread=0.005).is_liquid is False


class TestSpreadDecomposition:
    def test_information_share(self):
        s = SpreadDecomposition(adverse_selection_pct=0.6)
        assert s.information_share == 0.6
        assert s.is_information_driven is True


class TestSpreadForecast:
    def test_is_widening(self):
        f = SpreadForecast(current_spread_bps=5.0, forecast_spread_bps=6.0)
        assert f.is_widening is True
        f2 = SpreadForecast(current_spread_bps=5.0, forecast_spread_bps=5.0)
        assert f2.is_widening is False


class TestSpreadModeler:
    def test_roll_estimate(self):
        modeler = SpreadModeler()
        prices = _prices(200, vol=0.015)
        result = modeler.roll_estimate(prices, "AAPL")
        assert result.n_observations > 0
        # Roll model may or may not be valid depending on returns
        assert isinstance(result.is_valid, bool)

    def test_roll_insufficient_data(self):
        modeler = SpreadModeler(min_observations=50)
        result = modeler.roll_estimate([100, 101, 102], "X")
        assert result.is_valid is False

    def test_decompose_spread(self):
        modeler = SpreadModeler()
        spreads = [0.02, 0.03, 0.015, 0.025, 0.02]
        sizes = [1000, 5000, 2000, 3000, 1500]
        impacts = [0.005, -0.003, 0.002, -0.004, 0.001]
        result = modeler.decompose_spread(spreads, sizes, impacts, "AAPL")
        assert result.total_spread > 0
        total_pct = (
            result.adverse_selection_pct
            + result.order_processing_pct
            + result.inventory_pct
        )
        assert total_pct == pytest.approx(1.0, abs=0.01)

    def test_decompose_empty(self):
        modeler = SpreadModeler()
        result = modeler.decompose_spread([], [], [], "X")
        assert result.total_spread == 0.0

    def test_forecast_spread(self):
        modeler = SpreadModeler()
        spreads = [2.0, 2.5, 1.8, 2.2, 3.0, 2.1, 2.4]
        result = modeler.forecast_spread(
            spreads, current_volatility=0.025, avg_volatility=0.02,
            horizon_days=5, symbol="AAPL",
        )
        assert result.forecast_spread_bps > 0
        assert result.confidence > 0

    def test_forecast_empty(self):
        modeler = SpreadModeler()
        result = modeler.forecast_spread([], symbol="X")
        assert result.forecast_spread_bps == 0.0

    def test_regime_profile(self):
        modeler = SpreadModeler()
        rng = np.random.default_rng(42)
        spreads = list(rng.uniform(1, 5, 100))
        vols = list(rng.uniform(10, 30, 100))
        result = modeler.regime_profile(spreads, vols, "AAPL")
        assert result.avg_spread_normal > 0
        assert result.spread_stress_ratio > 0

    def test_regime_profile_empty(self):
        modeler = SpreadModeler()
        result = modeler.regime_profile([], [], "X")
        assert result.avg_spread_normal == 0.0


# ---------------------------------------------------------------------------
# Market Depth
# ---------------------------------------------------------------------------
class TestDepthSnapshot:
    def test_depth_imbalance(self):
        s = DepthSnapshot(total_bid_depth=1000, total_ask_depth=500)
        assert s.depth_imbalance == pytest.approx(0.333, abs=0.01)
        assert s.is_bid_heavy is True

    def test_total_depth(self):
        s = DepthSnapshot(total_bid_depth=500, total_ask_depth=500)
        assert s.total_depth == 1000


class TestDepthResilience:
    def test_is_resilient(self):
        assert DepthResilience(resilience_score=70).is_resilient is True
        assert DepthResilience(resilience_score=40).is_resilient is False

    def test_depth_drop(self):
        d = DepthResilience(depth_before=1000, depth_after=600)
        assert d.depth_drop_pct == pytest.approx(0.4)


class TestTopOfBookImbalance:
    def test_is_strong_signal(self):
        t = TopOfBookImbalance(imbalance_ratio=0.6)
        assert t.is_strong_signal is True
        t2 = TopOfBookImbalance(imbalance_ratio=0.1)
        assert t2.is_strong_signal is False


class TestMarketDepthAnalyzer:
    def test_compute_depth(self):
        analyzer = MarketDepthAnalyzer()
        bids, asks, mid = _order_book()
        snapshot = analyzer.compute_depth(bids, asks, mid, "AAPL")
        assert snapshot.total_bid_depth > 0
        assert snapshot.total_ask_depth > 0
        assert snapshot.n_bid_levels == 5

    def test_compute_depth_empty(self):
        analyzer = MarketDepthAnalyzer()
        snapshot = analyzer.compute_depth([], [], 0, "X")
        assert snapshot.total_depth == 0

    def test_compute_resilience(self):
        analyzer = MarketDepthAnalyzer()
        res = analyzer.compute_resilience(
            depth_before=1000, depth_after=400,
            recovery_depth=800, recovery_time_seconds=30,
            symbol="AAPL",
        )
        assert res.resilience_score > 0
        assert res.depth_recovery_pct > 0.5

    def test_top_of_book_imbalance(self):
        analyzer = MarketDepthAnalyzer()
        imb = analyzer.top_of_book_imbalance(1000, 200, "AAPL")
        assert imb.predicted_direction == "up"
        assert imb.is_strong_signal is True

    def test_top_of_book_balanced(self):
        analyzer = MarketDepthAnalyzer()
        imb = analyzer.top_of_book_imbalance(500, 500, "AAPL")
        assert imb.predicted_direction == "neutral"

    def test_depth_profile(self):
        analyzer = MarketDepthAnalyzer()
        bids, asks, mid = _order_book()
        snapshots = [
            analyzer.compute_depth(bids, asks, mid, "AAPL")
            for _ in range(5)
        ]
        profile = analyzer.depth_profile(snapshots, [70, 80, 75, 85, 72], "AAPL")
        assert profile.depth_score > 0
        assert profile.depth_stability > 0

    def test_depth_profile_empty(self):
        analyzer = MarketDepthAnalyzer()
        profile = analyzer.depth_profile([], symbol="X")
        assert profile.depth_score == 0.0


# ---------------------------------------------------------------------------
# Illiquidity Premium
# ---------------------------------------------------------------------------
class TestAmihudRatio:
    def test_is_illiquid(self):
        assert AmihudRatio(illiquidity_ratio=0.01).is_illiquid is True
        assert AmihudRatio(illiquidity_ratio=0.0001).is_illiquid is False

    def test_rank_score(self):
        a = AmihudRatio(illiquidity_ratio=0.0005)
        assert 0 <= a.illiquidity_rank_score <= 1.0


class TestIlliquidityPremiumEstimator:
    def test_amihud_ratio(self):
        est = IlliquidityPremiumEstimator()
        rng = np.random.default_rng(42)
        returns = list(rng.normal(0, 0.02, 100))
        dvols = list(rng.uniform(1e6, 1e8, 100))
        result = est.amihud_ratio(returns, dvols, "AAPL")
        assert result.illiquidity_ratio > 0
        assert result.n_observations == 100

    def test_amihud_empty(self):
        est = IlliquidityPremiumEstimator()
        result = est.amihud_ratio([], [], "X")
        assert result.n_observations == 0

    def test_pastor_stambaugh(self):
        est = IlliquidityPremiumEstimator(min_observations=20)
        rng = np.random.default_rng(42)
        returns = list(rng.normal(0, 0.02, 100))
        volumes = list(rng.uniform(-1e6, 1e6, 100))
        result = est.pastor_stambaugh_factor(returns, volumes, symbol="AAPL")
        assert result.n_observations > 0

    def test_pastor_stambaugh_insufficient(self):
        est = IlliquidityPremiumEstimator(min_observations=100)
        result = est.pastor_stambaugh_factor([0.01, 0.02], [1e6, 2e6])
        assert result.n_observations == 2

    def test_estimate_premium(self):
        est = IlliquidityPremiumEstimator()
        amihud = AmihudRatio(symbol="AAPL", illiquidity_ratio=0.0005,
                             n_observations=100, log_illiquidity=6.2)
        premium = est.estimate_premium(amihud)
        assert premium.estimated_premium_annual_pct > 0
        assert 1 <= premium.liquidity_quintile <= 5

    def test_cross_sectional(self):
        est = IlliquidityPremiumEstimator()
        premiums = [
            IlliquidityPremium(symbol=f"S{i}", amihud_ratio=i * 0.001,
                               estimated_premium_annual_pct=i * 0.01)
            for i in range(1, 11)
        ]
        result = est.cross_sectional_analysis(premiums)
        assert result.n_securities == 10
        assert result.premium_spread_pct > 0
        assert len(result.quintile_returns) == 5

    def test_cross_sectional_empty(self):
        est = IlliquidityPremiumEstimator()
        result = est.cross_sectional_analysis([])
        assert result.n_securities == 0


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------
class TestPositionLiquidity:
    def test_is_concentrated(self):
        assert PositionLiquidity(days_to_liquidate=10).is_concentrated is True
        assert PositionLiquidity(days_to_liquidate=2).is_concentrated is False

    def test_is_liquid(self):
        assert PositionLiquidity(days_to_liquidate=0.5).is_liquid is True


class TestConcentrationMetrics:
    def test_concentration_level(self):
        assert ConcentrationMetrics(hhi_liquidity=0.30).concentration_level == "high"
        assert ConcentrationMetrics(hhi_liquidity=0.15).concentration_level == "moderate"
        assert ConcentrationMetrics(hhi_liquidity=0.05).concentration_level == "low"

    def test_is_portfolio_liquid(self):
        assert ConcentrationMetrics(pct_liquid_5d=0.95).is_portfolio_liquid is True
        assert ConcentrationMetrics(pct_liquid_5d=0.80).is_portfolio_liquid is False


class TestLiquidityConcentrationAnalyzer:
    def test_assess_position(self):
        analyzer = LiquidityConcentrationAnalyzer()
        pos = analyzer.assess_position("AAPL", 5e6, 100e6, 8e9)
        assert pos.days_to_liquidate < 1.0
        assert pos.liquidity_score > 80

    def test_assess_illiquid_position(self):
        analyzer = LiquidityConcentrationAnalyzer()
        pos = analyzer.assess_position("ILLQ", 2e6, 100e6, 1e6)
        assert pos.days_to_liquidate > 5
        assert pos.is_concentrated is True

    def test_concentration_metrics(self):
        analyzer = LiquidityConcentrationAnalyzer()
        positions = [
            analyzer.assess_position("AAPL", 5e6, 10e6, 8e9),
            analyzer.assess_position("ILLQ", 5e6, 10e6, 1e6),
        ]
        metrics = analyzer.concentration_metrics(positions, 10e6)
        assert metrics.n_positions == 2
        assert metrics.pct_liquid_1d > 0

    def test_compute_limits(self):
        analyzer = LiquidityConcentrationAnalyzer()
        positions = [
            analyzer.assess_position("AAPL", 5e6, 100e6, 8e9),
        ]
        limits = analyzer.compute_limits(positions, 100e6)
        assert len(limits) == 1
        assert limits[0].max_position_usd > 0

    def test_generate_report(self):
        analyzer = LiquidityConcentrationAnalyzer()
        report = analyzer.generate_report(_holdings(), 10e6)
        assert report.overall_score > 0
        assert report.risk_level in ("low", "moderate", "high", "critical")
        assert len(report.positions) == 3
        assert len(report.limits) == 3

    def test_generate_report_empty(self):
        analyzer = LiquidityConcentrationAnalyzer()
        report = analyzer.generate_report([], 10e6)
        assert report.overall_score == 0


# ---------------------------------------------------------------------------
# Cost Curves
# ---------------------------------------------------------------------------
class TestCostPoint:
    def test_is_feasible(self):
        assert CostPoint(participation_rate=0.05).is_feasible is True
        assert CostPoint(participation_rate=0.15).is_feasible is False

    def test_total_cost_usd(self):
        pt = CostPoint(trade_size_usd=1e6, total_cost_bps=10)
        assert pt.total_cost_usd == pytest.approx(1000)


class TestCostCurveBuilder:
    def test_build_curve(self):
        builder = CostCurveBuilder()
        curve = builder.build_curve(
            avg_daily_volume=1e6, price=150.0, volatility=0.02,
            symbol="AAPL",
        )
        assert curve.n_points > 0
        assert curve.optimal_size_shares > 0
        # Cost should increase with size
        costs = [p.total_cost_bps for p in curve.points]
        assert costs[-1] >= costs[0]

    def test_build_curve_empty(self):
        builder = CostCurveBuilder()
        curve = builder.build_curve(0, 0, symbol="X")
        assert curve.n_points == 0

    def test_compare_curves(self):
        builder = CostCurveBuilder()
        curves = [
            builder.build_curve(1e6, 150, symbol="AAPL"),
            builder.build_curve(5e6, 300, symbol="MSFT"),
        ]
        comparison = builder.compare_curves(curves)
        assert comparison.n_symbols == 2

    def test_compare_empty(self):
        builder = CostCurveBuilder()
        comparison = builder.compare_curves([])
        assert comparison.n_symbols == 0

    def test_optimal_execution_single(self):
        builder = CostCurveBuilder()
        opt = builder.optimal_execution(
            target_shares=5000, avg_daily_volume=1e6,
            price=150, symbol="AAPL",
        )
        assert opt.strategy == "single"
        assert opt.recommended_slices == 1
        assert opt.expected_cost_bps > 0

    def test_optimal_execution_multi_day(self):
        builder = CostCurveBuilder()
        opt = builder.optimal_execution(
            target_shares=500_000, avg_daily_volume=100_000,
            price=150, symbol="ILLQ",
        )
        assert opt.strategy == "multi_day"
        assert opt.recommended_slices > 1
        assert opt.is_multi_day is True

    def test_optimal_execution_empty(self):
        builder = CostCurveBuilder()
        opt = builder.optimal_execution(0, 0, 0, symbol="X")
        assert opt.expected_cost_bps == 0
