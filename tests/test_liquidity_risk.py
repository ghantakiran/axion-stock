"""Tests for PRD-54: Liquidity Risk Management."""

import numpy as np
import pytest

from src.liquidity.redemption import (
    RedemptionScenario,
    LiquidityBuffer,
    LiquidationItem,
    LiquidationSchedule,
    RedemptionRiskModeler,
)
from src.liquidity.lavar import (
    VaRResult,
    LiquidityCost,
    PositionLaVaR,
    LaVaR,
    LaVaRCalculator,
)


# ---------------------------------------------------------------------------
# RedemptionScenario dataclass
# ---------------------------------------------------------------------------
class TestRedemptionScenario:
    def test_defaults(self):
        s = RedemptionScenario()
        assert s.name == "normal"
        assert s.redemption_pct == 0.0

    def test_is_covered(self):
        s = RedemptionScenario(coverage_ratio=1.5)
        assert s.is_covered is True
        s2 = RedemptionScenario(coverage_ratio=0.8)
        assert s2.is_covered is False

    def test_has_shortfall(self):
        s = RedemptionScenario(shortfall=100.0)
        assert s.has_shortfall is True
        s2 = RedemptionScenario(shortfall=0.0)
        assert s2.has_shortfall is False


# ---------------------------------------------------------------------------
# LiquidityBuffer dataclass
# ---------------------------------------------------------------------------
class TestLiquidityBuffer:
    def test_is_adequate(self):
        buf = LiquidityBuffer(coverage_ratio=1.2)
        assert buf.is_adequate is True

    def test_buffer_pct(self):
        buf = LiquidityBuffer(total_aum=1_000_000, required_buffer=50_000)
        assert buf.buffer_pct == pytest.approx(0.05)

    def test_buffer_pct_zero_aum(self):
        buf = LiquidityBuffer(total_aum=0, required_buffer=50_000)
        assert buf.buffer_pct == 0.0


# ---------------------------------------------------------------------------
# RedemptionRiskModeler
# ---------------------------------------------------------------------------
class TestRedemptionProbability:
    def test_no_history(self):
        m = RedemptionRiskModeler()
        assert m.estimate_redemption_probability([]) == 0.0

    def test_all_outflows(self):
        flows = [-0.10, -0.08, -0.06, -0.07]
        m = RedemptionRiskModeler()
        prob = m.estimate_redemption_probability(flows, threshold_pct=0.05)
        assert prob == 1.0

    def test_no_outflows(self):
        flows = [0.02, 0.03, 0.01, 0.05]
        m = RedemptionRiskModeler()
        prob = m.estimate_redemption_probability(flows, threshold_pct=0.05)
        assert prob == 0.0

    def test_mixed_flows(self):
        flows = [-0.10, 0.02, -0.06, 0.01, -0.03, 0.04]
        m = RedemptionRiskModeler()
        prob = m.estimate_redemption_probability(flows, threshold_pct=0.05)
        # -0.10 and -0.06 exceed -0.05 threshold → 2/6
        assert prob == pytest.approx(2 / 6)


class TestComputeBuffer:
    def test_basic_buffer(self):
        m = RedemptionRiskModeler()
        buf = m.compute_buffer(
            total_aum=10_000_000,
            cash=200_000,
            liquid_asset_value=300_000,
            expected_redemption_pct=0.05,
            buffer_multiplier=1.5,
        )
        assert buf.expected_redemption == 500_000
        assert buf.required_buffer == 750_000
        assert buf.buffer_deficit == 250_000
        assert buf.is_adequate is False

    def test_adequate_buffer(self):
        m = RedemptionRiskModeler()
        buf = m.compute_buffer(
            total_aum=10_000_000,
            cash=500_000,
            liquid_asset_value=500_000,
            expected_redemption_pct=0.05,
            buffer_multiplier=1.5,
        )
        assert buf.buffer_deficit == 0.0
        assert buf.is_adequate is True
        assert buf.coverage_ratio > 1.0


class TestStressScenarios:
    def test_three_scenarios(self):
        m = RedemptionRiskModeler()
        results = m.stress_scenarios(
            total_aum=10_000_000,
            cash=500_000,
            liquid_asset_value=500_000,
        )
        assert len(results) == 3
        assert results[0].name == "normal"
        assert results[1].name == "stressed"
        assert results[2].name == "crisis"

    def test_normal_covered(self):
        m = RedemptionRiskModeler()
        results = m.stress_scenarios(
            total_aum=10_000_000,
            cash=300_000,
            liquid_asset_value=300_000,
        )
        normal = results[0]
        assert normal.redemption_pct == 0.05
        assert normal.redemption_amount == 500_000
        assert normal.is_covered is True

    def test_crisis_shortfall(self):
        m = RedemptionRiskModeler()
        results = m.stress_scenarios(
            total_aum=10_000_000,
            cash=200_000,
            liquid_asset_value=200_000,
        )
        crisis = results[2]
        assert crisis.redemption_pct == 0.30
        assert crisis.has_shortfall is True
        assert crisis.shortfall > 0

    def test_days_to_meet_with_positions(self):
        m = RedemptionRiskModeler()
        positions = [
            {"symbol": "AAPL", "value": 5_000_000, "adv_usd": 10_000_000},
            {"symbol": "MSFT", "value": 3_000_000, "adv_usd": 8_000_000},
        ]
        results = m.stress_scenarios(
            total_aum=10_000_000,
            cash=100_000,
            liquid_asset_value=100_000,
            positions=positions,
        )
        crisis = results[2]
        assert crisis.days_to_meet > 0


class TestLiquidationSchedule:
    def test_basic_schedule(self):
        m = RedemptionRiskModeler()
        positions = [
            {"symbol": "AAPL", "value": 1_000_000, "adv_usd": 10_000_000, "spread_bps": 2.0},
            {"symbol": "ILLQ", "value": 500_000, "adv_usd": 100_000, "spread_bps": 50.0},
        ]
        sched = m.liquidation_schedule(positions)
        assert sched.total_value == 1_500_000
        assert len(sched.items) == 2

    def test_priority_ordering(self):
        m = RedemptionRiskModeler()
        positions = [
            {"symbol": "ILLQ", "value": 500_000, "adv_usd": 100_000, "spread_bps": 50.0},
            {"symbol": "AAPL", "value": 1_000_000, "adv_usd": 10_000_000, "spread_bps": 2.0},
        ]
        sched = m.liquidation_schedule(positions)
        # AAPL is more liquid so should be priority 1
        assert sched.items[0].symbol == "AAPL"
        assert sched.items[0].priority == 1
        assert sched.items[1].symbol == "ILLQ"
        assert sched.items[1].priority == 2

    def test_dtl_computation(self):
        m = RedemptionRiskModeler(max_participation=0.10)
        positions = [
            {"symbol": "A", "value": 1_000_000, "adv_usd": 1_000_000, "spread_bps": 5.0},
        ]
        sched = m.liquidation_schedule(positions)
        item = sched.items[0]
        # DTL = 1M / (1M * 0.10) = 10 days
        assert item.days_to_liquidate == 10.0

    def test_pct_liquid_timeframes(self):
        m = RedemptionRiskModeler(max_participation=0.10)
        positions = [
            {"symbol": "LIQ", "value": 100_000, "adv_usd": 5_000_000, "spread_bps": 2.0},
            {"symbol": "MED", "value": 400_000, "adv_usd": 1_000_000, "spread_bps": 10.0},
            {"symbol": "ILLQ", "value": 500_000, "adv_usd": 100_000, "spread_bps": 50.0},
        ]
        sched = m.liquidation_schedule(positions)
        # LIQ: DTL = 100k / 500k = 0.2d → liquid in 1d
        # MED: DTL = 400k / 100k = 4.0d → liquid in 5d
        # ILLQ: DTL = 500k / 10k = 50.0d → NOT liquid in 20d
        assert sched.pct_liquid_1d > 0
        assert sched.pct_liquid_5d > sched.pct_liquid_1d
        assert sched.pct_liquid_20d >= sched.pct_liquid_5d

    def test_impact_cost_capped(self):
        m = RedemptionRiskModeler()
        positions = [
            {"symbol": "TINY", "value": 10_000_000, "adv_usd": 1000, "spread_bps": 5.0},
        ]
        sched = m.liquidation_schedule(positions)
        # Impact should be capped at 500 bps
        assert sched.items[0].liquidation_cost_bps <= 500.0


# ---------------------------------------------------------------------------
# VaRResult dataclass
# ---------------------------------------------------------------------------
class TestVaRResult:
    def test_var_bps(self):
        v = VaRResult(var_pct=0.02)
        assert v.var_bps == 200.0

    def test_defaults(self):
        v = VaRResult()
        assert v.confidence == 0.95
        assert v.method == "historical"


# ---------------------------------------------------------------------------
# LiquidityCost dataclass
# ---------------------------------------------------------------------------
class TestLiquidityCost:
    def test_total_bps(self):
        lc = LiquidityCost(total_cost_pct=0.005)
        assert lc.total_bps == 50.0


# ---------------------------------------------------------------------------
# LaVaR dataclass
# ---------------------------------------------------------------------------
class TestLaVaRDataclass:
    def test_liquidity_share(self):
        lv = LaVaR(var_pct=0.02, liquidity_cost_pct=0.005, lavar_pct=0.025)
        assert lv.liquidity_share == pytest.approx(0.2)

    def test_lavar_bps(self):
        lv = LaVaR(lavar_pct=0.03)
        assert lv.lavar_bps == 300.0


# ---------------------------------------------------------------------------
# LaVaRCalculator
# ---------------------------------------------------------------------------
class TestHistoricalVaR:
    def test_empty_returns(self):
        calc = LaVaRCalculator()
        result = calc.historical_var([], 1_000_000)
        assert result.var_pct == 0.0

    def test_basic_var(self):
        np.random.seed(42)
        returns = list(np.random.normal(0.0005, 0.02, 500))
        calc = LaVaRCalculator()
        result = calc.historical_var(returns, 1_000_000, confidence=0.95)
        assert result.var_pct > 0
        assert result.var_dollar > 0
        assert result.method == "historical"

    def test_horizon_scaling(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        calc = LaVaRCalculator()
        var_1d = calc.historical_var(returns, 1_000_000, horizon_days=1)
        var_10d = calc.historical_var(returns, 1_000_000, horizon_days=10)
        # 10-day VaR should be ~sqrt(10) times 1-day VaR
        ratio = var_10d.var_pct / var_1d.var_pct
        assert 2.5 < ratio < 4.0  # ~3.16 expected


class TestParametricVaR:
    def test_empty_returns(self):
        calc = LaVaRCalculator()
        result = calc.parametric_var([], 1_000_000)
        assert result.var_pct == 0.0
        assert result.method == "parametric"

    def test_basic_parametric(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        calc = LaVaRCalculator()
        result = calc.parametric_var(returns, 1_000_000, confidence=0.95)
        assert result.var_pct > 0
        assert result.var_dollar > 0

    def test_higher_confidence_larger_var(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        calc = LaVaRCalculator()
        var95 = calc.parametric_var(returns, 1_000_000, confidence=0.95)
        var99 = calc.parametric_var(returns, 1_000_000, confidence=0.99)
        assert var99.var_pct > var95.var_pct


class TestLiquidityCostCalc:
    def test_empty_positions(self):
        calc = LaVaRCalculator()
        lc = calc.compute_liquidity_cost([], 1_000_000)
        assert lc.total_cost_pct == 0.0

    def test_basic_cost(self):
        calc = LaVaRCalculator()
        positions = [
            {"symbol": "AAPL", "value": 500_000, "adv_usd": 5_000_000, "spread_bps": 2.0},
            {"symbol": "MSFT", "value": 500_000, "adv_usd": 5_000_000, "spread_bps": 3.0},
        ]
        lc = calc.compute_liquidity_cost(positions, 1_000_000)
        assert lc.spread_cost_pct > 0
        assert lc.impact_cost_pct > 0
        assert lc.total_cost_pct > 0

    def test_illiquid_higher_cost(self):
        calc = LaVaRCalculator()
        liquid_pos = [
            {"symbol": "LIQ", "value": 1_000_000, "adv_usd": 100_000_000, "spread_bps": 1.0},
        ]
        illiquid_pos = [
            {"symbol": "ILLQ", "value": 1_000_000, "adv_usd": 50_000, "spread_bps": 100.0},
        ]
        lc_liq = calc.compute_liquidity_cost(liquid_pos, 1_000_000)
        lc_illiq = calc.compute_liquidity_cost(illiquid_pos, 1_000_000)
        assert lc_illiq.total_cost_pct > lc_liq.total_cost_pct


class TestComputeLaVaR:
    def test_lavar_greater_than_var(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        positions = [
            {"symbol": "AAPL", "value": 500_000, "adv_usd": 5_000_000, "spread_bps": 5.0},
            {"symbol": "MSFT", "value": 500_000, "adv_usd": 3_000_000, "spread_bps": 8.0},
        ]
        calc = LaVaRCalculator()
        result = calc.compute_lavar(returns, positions, 1_000_000)
        assert result.lavar_pct > result.var_pct
        assert result.lavar_dollar > result.var_dollar
        assert result.liquidity_cost_pct > 0

    def test_parametric_method(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        positions = [
            {"symbol": "A", "value": 1_000_000, "adv_usd": 10_000_000, "spread_bps": 3.0},
        ]
        calc = LaVaRCalculator()
        result = calc.compute_lavar(
            returns, positions, 1_000_000, method="parametric"
        )
        assert result.method == "parametric"
        assert result.lavar_pct > 0

    def test_position_decomposition(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        positions = [
            {"symbol": "AAPL", "value": 600_000, "adv_usd": 10_000_000, "spread_bps": 2.0},
            {"symbol": "ILLQ", "value": 400_000, "adv_usd": 50_000, "spread_bps": 80.0},
        ]
        calc = LaVaRCalculator()
        result = calc.compute_lavar(returns, positions, 1_000_000)
        assert len(result.positions) == 2
        # ILLQ should have higher LaVaR contribution (illiquid)
        illq = [p for p in result.positions if p.symbol == "ILLQ"][0]
        aapl = [p for p in result.positions if p.symbol == "AAPL"][0]
        assert illq.liquidity_cost_pct > aapl.liquidity_cost_pct

    def test_liquidity_share(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        positions = [
            {"symbol": "A", "value": 1_000_000, "adv_usd": 1_000_000, "spread_bps": 20.0},
        ]
        calc = LaVaRCalculator()
        result = calc.compute_lavar(returns, positions, 1_000_000)
        assert 0 < result.liquidity_share < 1.0

    def test_multi_day_horizon(self):
        np.random.seed(42)
        returns = list(np.random.normal(0, 0.02, 500))
        positions = [
            {"symbol": "A", "value": 1_000_000, "adv_usd": 5_000_000, "spread_bps": 5.0},
        ]
        calc = LaVaRCalculator()
        lavar_1d = calc.compute_lavar(returns, positions, 1_000_000, horizon_days=1)
        lavar_10d = calc.compute_lavar(returns, positions, 1_000_000, horizon_days=10)
        assert lavar_10d.lavar_pct > lavar_1d.lavar_pct
