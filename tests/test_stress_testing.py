"""Tests for PRD-65: Portfolio Stress Testing.

Covers shock propagation, drawdown analysis, recovery estimation,
and scenario building.
"""

import pytest
import numpy as np

from src.risk.shock_propagation import (
    FactorShock,
    PropagatedShock,
    PortfolioShockResult,
    ContagionPath,
    ShockPropagationEngine,
)
from src.risk.drawdown_analysis import (
    DrawdownEvent,
    DrawdownMetrics,
    UnderwaterCurve,
    ConditionalDrawdown,
    DrawdownAnalyzer,
)
from src.risk.recovery_estimation import (
    RecoveryEstimate,
    RecoveryPath,
    RecoveryAnalysis,
    BreakevenAnalysis,
    RecoveryEstimator,
)
from src.risk.scenario_builder import (
    MacroShock,
    SectorRotation,
    CorrelationShift,
    CustomScenario,
    ScenarioTemplate,
    ScenarioBuilder,
    SCENARIO_TEMPLATES,
)


# ===================================================================
# Shock Propagation Tests
# ===================================================================
class TestFactorShock:
    def test_negative_shock(self):
        fs = FactorShock(factor="market", shock_magnitude=-0.15)
        assert fs.is_negative
        assert fs.severity == "moderate"

    def test_severe_shock(self):
        fs = FactorShock(factor="market", shock_magnitude=-0.25)
        assert fs.severity == "severe"

    def test_mild_shock(self):
        fs = FactorShock(factor="growth", shock_magnitude=-0.06)
        assert fs.severity == "mild"


class TestPropagatedShock:
    def test_amplification(self):
        ps = PropagatedShock(
            symbol="AAPL",
            direct_impact=-0.10,
            indirect_impact=-0.05,
            total_impact=-0.15,
        )
        assert ps.amplification_ratio == pytest.approx(1.5)

    def test_no_direct_impact(self):
        ps = PropagatedShock(direct_impact=0.0, indirect_impact=-0.05, total_impact=-0.05)
        assert ps.amplification_ratio == 1.0


class TestPortfolioShockResult:
    def test_systemic(self):
        impacts = [PropagatedShock(symbol=f"SYM{i}", total_impact=-0.1) for i in range(10)]
        result = PortfolioShockResult(position_impacts=impacts)
        assert result.is_systemic

    def test_not_systemic(self):
        impacts = [PropagatedShock(symbol=f"SYM{i}", total_impact=-0.1 if i < 5 else 0.0) for i in range(10)]
        result = PortfolioShockResult(position_impacts=impacts)
        assert not result.is_systemic

    def test_n_positions_affected(self):
        impacts = [
            PropagatedShock(symbol="A", total_impact=-0.1),
            PropagatedShock(symbol="B", total_impact=0.0),
            PropagatedShock(symbol="C", total_impact=-0.05),
        ]
        result = PortfolioShockResult(position_impacts=impacts)
        assert result.n_positions_affected == 2


class TestShockPropagationEngine:
    def setup_method(self):
        self.engine = ShockPropagationEngine()

    def test_get_correlation(self):
        corr = self.engine.get_correlation("market", "growth")
        assert corr == 0.6
        # Symmetric
        assert self.engine.get_correlation("growth", "market") == 0.6

    def test_self_correlation(self):
        assert self.engine.get_correlation("market", "market") == 1.0

    def test_unknown_correlation(self):
        assert self.engine.get_correlation("unknown1", "unknown2") == 0.0

    def test_propagate_shock_basic(self):
        shocks = [FactorShock(factor="market", shock_magnitude=-0.10)]
        exposures = {
            "AAPL": {"market": 1.2, "growth": 0.5},
            "XOM": {"market": 0.8, "value": 0.6},
        }
        values = {"AAPL": 50000, "XOM": 50000}

        result = self.engine.propagate_shock(shocks, exposures, values, 100000)
        assert result.total_impact_pct < 0
        assert len(result.position_impacts) == 2

    def test_propagate_shock_with_indirect(self):
        shocks = [FactorShock(factor="market", shock_magnitude=-0.10)]
        exposures = {
            "AAPL": {"market": 1.0, "growth": 1.0},  # Growth gets indirect shock
        }
        values = {"AAPL": 100000}

        result = self.engine.propagate_shock(shocks, exposures, values, 100000, max_hops=2)
        # Should have both direct (market) and indirect (growth via correlation) impacts
        assert result.position_impacts[0].direct_impact != 0

    def test_trace_contagion(self):
        paths = self.engine.trace_contagion("market", -0.10, max_hops=2)
        assert len(paths) > 0
        # Check that paths include correlated factors
        target_factors = {p.target_factor for p in paths}
        assert "growth" in target_factors  # Market is correlated with growth

    def test_sensitivity_analysis(self):
        exposures = {
            "AAPL": {"market": 1.2, "growth": 0.8},
            "MSFT": {"market": 1.1, "value": 0.4},
        }
        values = {"AAPL": 50000, "MSFT": 50000}

        result = self.engine.sensitivity_analysis(
            exposures, values, 100000, shock_range=(-0.10, 0.10), n_points=3
        )
        assert "sensitivities" in result
        assert "factor_betas" in result
        assert "most_sensitive" in result


# ===================================================================
# Drawdown Analysis Tests
# ===================================================================
class TestDrawdownEvent:
    def test_ongoing(self):
        de = DrawdownEvent(end_idx=None)
        assert de.is_ongoing

    def test_completed(self):
        de = DrawdownEvent(end_idx=100)
        assert not de.is_ongoing

    def test_severity_levels(self):
        assert DrawdownEvent(drawdown_pct=-0.35).severity == "severe"
        assert DrawdownEvent(drawdown_pct=-0.18).severity == "significant"
        assert DrawdownEvent(drawdown_pct=-0.08).severity == "moderate"
        assert DrawdownEvent(drawdown_pct=-0.03).severity == "minor"

    def test_recovery_ratio(self):
        de = DrawdownEvent(duration_to_trough=10, recovery_duration=20)
        assert de.recovery_ratio == 2.0


class TestDrawdownMetrics:
    def test_is_underwater(self):
        dm = DrawdownMetrics(current_drawdown=-0.05)
        assert dm.is_underwater

    def test_not_underwater(self):
        dm = DrawdownMetrics(current_drawdown=0.0)
        assert not dm.is_underwater

    def test_risk_score(self):
        dm = DrawdownMetrics(max_drawdown=-0.20, avg_duration=30, n_drawdowns=5)
        assert 0 <= dm.drawdown_risk_score <= 100


class TestDrawdownAnalyzer:
    def setup_method(self):
        self.analyzer = DrawdownAnalyzer()

    def test_underwater_curve(self):
        values = [100, 105, 110, 108, 95, 100, 110, 115]
        curve = self.analyzer.compute_underwater_curve(values, symbol="TEST")
        assert curve.n_periods == 8
        assert curve.max_drawdown < 0
        assert len(curve.drawdowns) == 8

    def test_underwater_curve_empty(self):
        curve = self.analyzer.compute_underwater_curve([], symbol="EMPTY")
        assert curve.n_periods == 0

    def test_identify_drawdown_events(self):
        # Create a series with a drawdown and recovery
        values = [100, 105, 110, 100, 90, 85, 90, 100, 110, 115]
        events = self.analyzer.identify_drawdown_events(values, symbol="TEST")
        assert len(events) >= 1
        # First event should be the decline from 110 to 85
        assert events[0].drawdown_pct < -0.10

    def test_ongoing_drawdown(self):
        values = [100, 105, 110, 100, 90, 85]  # Ends in drawdown
        events = self.analyzer.identify_drawdown_events(values, symbol="TEST")
        assert any(e.is_ongoing for e in events)

    def test_compute_metrics(self):
        values = [100 + np.random.normal(0, 5) for _ in range(100)]
        values = np.maximum.accumulate(values).tolist()[:50] + [v * 0.9 for v in values[50:60]] + values[60:]
        metrics = self.analyzer.compute_metrics(values, symbol="TEST")
        assert metrics.max_drawdown <= 0
        assert metrics.n_drawdowns >= 0

    def test_conditional_drawdown(self):
        np.random.seed(42)
        values = [100]
        for _ in range(200):
            values.append(values[-1] * (1 + np.random.normal(0.0005, 0.015)))
        cdd = self.analyzer.conditional_drawdown(values, symbol="TEST")
        assert cdd.cvar_5 <= 0  # CVaR should be negative

    def test_compare_drawdowns(self):
        metrics = [
            DrawdownMetrics(symbol="A", max_drawdown=-0.10, avg_duration=20),
            DrawdownMetrics(symbol="B", max_drawdown=-0.20, avg_duration=30),
        ]
        comp = self.analyzer.compare_drawdowns(metrics)
        assert comp["best"] == "A"  # Less negative
        assert comp["worst"] == "B"


# ===================================================================
# Recovery Estimation Tests
# ===================================================================
class TestRecoveryEstimate:
    def test_quick_recovery(self):
        re = RecoveryEstimate(expected_days=20)
        assert re.is_quick_recovery

    def test_slow_recovery(self):
        re = RecoveryEstimate(expected_days=60)
        assert not re.is_quick_recovery

    def test_confidence_levels(self):
        assert RecoveryEstimate(probability_90d=0.85).recovery_confidence == "high"
        assert RecoveryEstimate(probability_90d=0.60).recovery_confidence == "medium"
        assert RecoveryEstimate(probability_90d=0.30).recovery_confidence == "low"


class TestBreakevenAnalysis:
    def test_deep_hole(self):
        ba = BreakevenAnalysis(days_to_breakeven=100, compound_effect=25)
        assert ba.is_deep_hole

    def test_not_deep_hole(self):
        ba = BreakevenAnalysis(days_to_breakeven=100, compound_effect=5)
        assert not ba.is_deep_hole


class TestRecoveryEstimator:
    def setup_method(self):
        self.estimator = RecoveryEstimator(n_simulations=100, max_days=200)

    def test_analytical_no_drawdown(self):
        result = self.estimator.analytical_estimate(0.0, symbol="TEST")
        assert result.expected_days == 0.0

    def test_analytical_with_drawdown(self):
        result = self.estimator.analytical_estimate(-0.10, symbol="TEST")
        assert result.expected_days > 0
        assert result.probability_30d >= 0
        assert result.probability_90d >= result.probability_30d

    def test_monte_carlo_no_drawdown(self):
        result = self.estimator.monte_carlo_estimate(0.0, symbol="TEST")
        assert result.expected_days == 0.0

    def test_monte_carlo_with_drawdown(self):
        result = self.estimator.monte_carlo_estimate(-0.10, symbol="TEST")
        assert result.expected_days > 0
        assert result.method == "monte_carlo"

    def test_historical_estimate(self):
        hist = [30, 45, 60, 25, 50]
        result = self.estimator.historical_estimate(hist, -0.10, symbol="TEST")
        assert result.expected_days == pytest.approx(42, abs=1)
        assert result.method == "historical"

    def test_historical_estimate_empty(self):
        result = self.estimator.historical_estimate([], -0.10, symbol="TEST")
        assert result.expected_days == 0.0

    def test_breakeven_analysis(self):
        result = self.estimator.breakeven_analysis(80, 100)
        assert result.required_gain_pct == pytest.approx(0.25)
        assert result.days_to_breakeven > 0

    def test_breakeven_no_drawdown(self):
        result = self.estimator.breakeven_analysis(100, 100)
        assert result.required_gain_pct == 0.0

    def test_comprehensive_analysis(self):
        result = self.estimator.comprehensive_analysis(
            current_drawdown=-0.15,
            historical_recovery_days=[30, 50, 40],
            symbol="TEST",
        )
        assert result.estimate is not None
        assert result.has_historical_data


# ===================================================================
# Scenario Builder Tests
# ===================================================================
class TestMacroShock:
    def test_signed_magnitude_up(self):
        ms = MacroShock(variable="rates", magnitude=0.02, direction="up")
        assert ms.signed_magnitude == 0.02

    def test_signed_magnitude_down(self):
        ms = MacroShock(variable="growth", magnitude=0.03, direction="down")
        assert ms.signed_magnitude == -0.03


class TestSectorRotation:
    def test_positive(self):
        sr = SectorRotation(sector="Energy", impact_pct=0.15)
        assert sr.is_positive

    def test_negative(self):
        sr = SectorRotation(sector="Technology", impact_pct=-0.20)
        assert not sr.is_positive


class TestCorrelationShift:
    def test_contagion(self):
        cs = CorrelationShift(from_correlation=0.3, to_correlation=0.7)
        assert cs.is_contagion

    def test_not_contagion(self):
        cs = CorrelationShift(from_correlation=0.7, to_correlation=0.3)
        assert not cs.is_contagion


class TestCustomScenario:
    def test_n_components(self):
        scn = CustomScenario(
            macro_shocks=[MacroShock(), MacroShock()],
            sector_rotations=[SectorRotation()],
            factor_shocks={"growth": -0.1},
        )
        assert scn.n_components == 4

    def test_severity_score(self):
        scn = CustomScenario(market_shock=-0.20)
        assert scn.severity_score > 0

    def test_is_severe(self):
        scn = CustomScenario(market_shock=-0.31, volatility_multiplier=2.0)
        assert scn.is_severe


class TestScenarioBuilder:
    def setup_method(self):
        self.builder = ScenarioBuilder()

    def test_from_template_recession(self):
        scn = self.builder.from_template("recession")
        assert scn.market_shock < 0
        assert len(scn.macro_shocks) > 0

    def test_from_template_unknown(self):
        scn = self.builder.from_template("unknown_template")
        assert scn.description == "Unknown template"

    def test_from_template_with_severity(self):
        scn1 = self.builder.from_template("recession", severity_multiplier=1.0)
        scn2 = self.builder.from_template("recession", severity_multiplier=2.0)
        assert scn2.market_shock < scn1.market_shock  # More severe

    def test_from_macro_shocks(self):
        shocks = [
            MacroShock(variable="interest_rates", magnitude=0.02, direction="up"),
            MacroShock(variable="growth", magnitude=0.02, direction="down"),
        ]
        scn = self.builder.from_macro_shocks(shocks, name="Custom")
        assert scn.name == "Custom"
        assert len(scn.sector_rotations) > 0

    def test_combine_scenarios(self):
        scn1 = CustomScenario(
            name="A",
            market_shock=-0.10,
            sector_rotations=[SectorRotation(sector="Tech", impact_pct=-0.15)],
        )
        scn2 = CustomScenario(
            name="B",
            market_shock=-0.20,
            sector_rotations=[SectorRotation(sector="Tech", impact_pct=-0.25)],
        )
        combined = self.builder.combine_scenarios([scn1, scn2], name="Combined")
        assert combined.market_shock == pytest.approx(-0.15)  # Average

    def test_add_correlation_shift(self):
        scn = CustomScenario(name="Base")
        scn = self.builder.add_correlation_shift(scn, 0.3, 0.8, "Crisis contagion")
        assert scn.correlation_shift is not None
        assert scn.correlation_shift.is_contagion

    def test_list_templates(self):
        templates = self.builder.list_templates()
        assert len(templates) > 0
        assert any(t["name"] == "Recession" for t in templates)

    def test_validate_scenario_valid(self):
        scn = CustomScenario(
            market_shock=-0.10,
            volatility_multiplier=1.3,
            sector_rotations=[SectorRotation(sector="Tech", impact_pct=-0.15)],
        )
        result = self.builder.validate_scenario(scn)
        assert result["valid"]

    def test_validate_scenario_inconsistent(self):
        # Severe market decline but many positive sectors
        scn = CustomScenario(
            market_shock=-0.20,
            volatility_multiplier=1.0,  # Too low for severe shock
            sector_rotations=[
                SectorRotation(sector=f"Sector{i}", impact_pct=0.10)
                for i in range(8)
            ],
        )
        result = self.builder.validate_scenario(scn)
        assert len(result["issues"]) > 0

    def test_scenario_templates_exist(self):
        assert "recession" in SCENARIO_TEMPLATES
        assert "rate_shock" in SCENARIO_TEMPLATES
        assert "tech_correction" in SCENARIO_TEMPLATES
