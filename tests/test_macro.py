"""Tests for Macro Regime Analysis module."""

import numpy as np
import pytest

from src.macro.config import (
    RegimeType,
    CurveShape,
    IndicatorType,
    MacroFactor,
    IndicatorConfig,
    YieldCurveConfig,
    RegimeConfig,
    FactorConfig,
    MacroConfig,
    DEFAULT_CONFIG,
)
from src.macro.models import (
    EconomicIndicator,
    IndicatorSummary,
    YieldCurveSnapshot,
    RegimeState,
    MacroFactorResult,
)
from src.macro.indicators import IndicatorTracker
from src.macro.yieldcurve import YieldCurveAnalyzer
from src.macro.regime import RegimeDetector
from src.macro.factors import MacroFactorModel


# ── Helpers ──────────────────────────────────────────────────


def _make_indicators(n=12, trend=0.1):
    """Generate synthetic economic indicators over time."""
    rng = np.random.RandomState(42)
    indicators = []
    for i in range(n):
        val = 50 + trend * i + rng.randn() * 2
        prev = 50 + trend * (i - 1) + rng.randn() * 2 if i > 0 else 50
        indicators.append(EconomicIndicator(
            name="ISM_PMI", value=val, previous=prev,
            consensus=val - rng.randn() * 1,
            indicator_type=IndicatorType.LEADING,
            date=f"2025-{i + 1:02d}-01",
        ))
    return indicators


def _make_normal_curve():
    """Normal upward-sloping yield curve."""
    return {
        "3M": 4.00, "6M": 4.10, "1Y": 4.20, "2Y": 4.30,
        "3Y": 4.40, "5Y": 4.50, "7Y": 4.60, "10Y": 4.70,
        "20Y": 4.85, "30Y": 5.00,
    }


def _make_inverted_curve():
    """Inverted yield curve."""
    return {
        "3M": 5.00, "6M": 4.95, "1Y": 4.80, "2Y": 4.70,
        "3Y": 4.50, "5Y": 4.30, "7Y": 4.20, "10Y": 4.10,
        "20Y": 4.00, "30Y": 3.90,
    }


# ── Config Tests ─────────────────────────────────────────────


class TestMacroConfig:
    def test_regime_type_values(self):
        assert RegimeType.EXPANSION.value == "expansion"
        assert RegimeType.SLOWDOWN.value == "slowdown"
        assert RegimeType.CONTRACTION.value == "contraction"
        assert RegimeType.RECOVERY.value == "recovery"

    def test_curve_shape_values(self):
        assert CurveShape.NORMAL.value == "normal"
        assert CurveShape.FLAT.value == "flat"
        assert CurveShape.INVERTED.value == "inverted"
        assert CurveShape.HUMPED.value == "humped"

    def test_indicator_type_values(self):
        assert IndicatorType.LEADING.value == "leading"
        assert IndicatorType.COINCIDENT.value == "coincident"
        assert IndicatorType.LAGGING.value == "lagging"

    def test_macro_factor_values(self):
        assert MacroFactor.GROWTH.value == "growth"
        assert MacroFactor.INFLATION.value == "inflation"
        assert MacroFactor.RATES.value == "rates"

    def test_indicator_config_defaults(self):
        cfg = IndicatorConfig()
        assert cfg.momentum_window == 6
        assert cfg.surprise_threshold == 1.0

    def test_yieldcurve_config_defaults(self):
        cfg = YieldCurveConfig()
        assert len(cfg.tenors) == 10
        assert cfg.key_spread_short == "2Y"
        assert cfg.key_spread_long == "10Y"

    def test_regime_config_defaults(self):
        cfg = RegimeConfig()
        assert cfg.n_regimes == 4
        assert cfg.consensus_threshold == 0.6

    def test_factor_config_defaults(self):
        cfg = FactorConfig()
        assert len(cfg.factors) == 5
        assert cfg.min_observations == 24

    def test_macro_config_bundles(self):
        cfg = MacroConfig()
        assert isinstance(cfg.indicators, IndicatorConfig)
        assert isinstance(cfg.yieldcurve, YieldCurveConfig)
        assert isinstance(cfg.regime, RegimeConfig)
        assert isinstance(cfg.factors, FactorConfig)


# ── Model Tests ──────────────────────────────────────────────


class TestMacroModels:
    def test_economic_indicator_properties(self):
        ind = EconomicIndicator(
            name="GDP", value=3.2, previous=2.8,
            consensus=3.0, indicator_type=IndicatorType.COINCIDENT,
        )
        assert abs(ind.surprise - 0.2) < 0.001
        assert abs(ind.change - 0.4) < 0.001
        assert abs(ind.change_pct - 14.29) < 0.1

    def test_economic_indicator_zero_prev(self):
        ind = EconomicIndicator(name="X", value=1.0, previous=0.0)
        assert ind.change_pct == 0.0

    def test_economic_indicator_to_dict(self):
        ind = EconomicIndicator(
            name="CPI", value=3.5, previous=3.2,
            consensus=3.4, date="2026-01-01",
        )
        d = ind.to_dict()
        assert d["name"] == "CPI"
        assert abs(d["surprise"] - 0.1) < 0.001

    def test_indicator_summary_breadth(self):
        s = IndicatorSummary(
            composite_index=0.5,
            n_improving=7, n_deteriorating=2, n_stable=1,
            leading_score=0.6, coincident_score=0.4, lagging_score=0.3,
        )
        assert abs(s.breadth - 0.7) < 0.01

    def test_indicator_summary_zero(self):
        s = IndicatorSummary(
            composite_index=0, n_improving=0, n_deteriorating=0, n_stable=0,
            leading_score=0, coincident_score=0, lagging_score=0,
        )
        assert s.breadth == 0.0

    def test_indicator_summary_to_dict(self):
        s = IndicatorSummary(
            composite_index=0.5,
            n_improving=7, n_deteriorating=2, n_stable=1,
            leading_score=0.6, coincident_score=0.4, lagging_score=0.3,
        )
        d = s.to_dict()
        assert d["breadth"] == s.breadth

    def test_yield_curve_properties(self):
        rates = {"2Y": 4.30, "10Y": 4.70}
        snap = YieldCurveSnapshot(date="2026-01-31", rates=rates)
        assert snap.short_rate == 4.30
        assert snap.long_rate == 4.70

    def test_yield_curve_empty(self):
        snap = YieldCurveSnapshot(date="", rates={})
        assert snap.short_rate == 0.0
        assert snap.long_rate == 0.0

    def test_yield_curve_to_dict(self):
        snap = YieldCurveSnapshot(
            date="2026-01-31", rates={"2Y": 4.30},
            shape=CurveShape.NORMAL, term_spread=0.40,
        )
        d = snap.to_dict()
        assert d["shape"] == "normal"

    def test_regime_state_confident(self):
        r = RegimeState(
            regime=RegimeType.EXPANSION,
            probability=0.75, duration=6,
        )
        assert r.is_confident

    def test_regime_state_not_confident(self):
        r = RegimeState(
            regime=RegimeType.CONTRACTION,
            probability=0.45, duration=2,
        )
        assert not r.is_confident

    def test_regime_state_to_dict(self):
        r = RegimeState(
            regime=RegimeType.EXPANSION,
            probability=0.75, duration=6,
            transition_probs={RegimeType.EXPANSION: 0.7, RegimeType.SLOWDOWN: 0.3},
        )
        d = r.to_dict()
        assert d["regime"] == "expansion"
        assert "expansion" in d["transition_probs"]

    def test_macro_factor_result_counts(self):
        r = MacroFactorResult(
            factor_returns={"growth": 0.5, "inflation": -0.2, "rates": 0.0},
            factor_exposures={"growth": 1.0, "inflation": -0.5, "rates": 0.0},
            factor_momentum={"growth": 0.3, "inflation": -0.1, "rates": 0.0},
        )
        assert r.n_positive == 1
        assert r.n_negative == 1

    def test_macro_factor_result_to_dict(self):
        r = MacroFactorResult(
            factor_returns={"growth": 0.5},
            factor_exposures={"growth": 1.0},
            factor_momentum={"growth": 0.3},
            dominant_factor="growth",
        )
        d = r.to_dict()
        assert d["dominant_factor"] == "growth"


# ── Indicator Tracker Tests ──────────────────────────────────


class TestIndicatorTracker:
    def test_add_and_summarize(self):
        tracker = IndicatorTracker()
        indicators = _make_indicators(12, trend=0.1)
        tracker.add_indicators(indicators)
        summary = tracker.summarize()

        assert summary.n_improving + summary.n_deteriorating + summary.n_stable > 0
        assert summary.leading_score != 0

    def test_improving_indicators(self):
        tracker = IndicatorTracker()
        # Strong uptrend
        for i in range(12):
            tracker.add_indicator(EconomicIndicator(
                name="PMI", value=50 + i * 2, previous=50 + (i - 1) * 2,
                indicator_type=IndicatorType.LEADING,
            ))
        summary = tracker.summarize()
        assert summary.n_improving >= 1

    def test_surprises(self):
        tracker = IndicatorTracker()
        tracker.add_indicator(EconomicIndicator(
            name="GDP", value=3.5, previous=3.0, consensus=3.0,
        ))
        tracker.add_indicator(EconomicIndicator(
            name="CPI", value=2.5, previous=2.6, consensus=2.8,
        ))
        surprises = tracker.get_surprises()
        assert len(surprises) == 2
        assert surprises[0][0] == "GDP"  # larger surprise first

    def test_empty_tracker(self):
        tracker = IndicatorTracker()
        summary = tracker.summarize()
        assert summary.composite_index == 0.0

    def test_reset(self):
        tracker = IndicatorTracker()
        tracker.add_indicators(_make_indicators(5))
        tracker.reset()
        assert tracker.get_history("ISM_PMI") == []

    def test_multiple_indicator_types(self):
        tracker = IndicatorTracker()
        for i in range(6):
            tracker.add_indicator(EconomicIndicator(
                name="LEI", value=100 + i, previous=100 + i - 1,
                indicator_type=IndicatorType.LEADING,
            ))
            tracker.add_indicator(EconomicIndicator(
                name="IP", value=100 + i * 0.5, previous=100 + (i - 1) * 0.5,
                indicator_type=IndicatorType.COINCIDENT,
            ))
        summary = tracker.summarize()
        assert summary.leading_score != 0 or summary.coincident_score != 0


# ── Yield Curve Analyzer Tests ───────────────────────────────


class TestYieldCurveAnalyzer:
    def test_normal_curve(self):
        analyzer = YieldCurveAnalyzer()
        rates = _make_normal_curve()
        snap = analyzer.analyze(rates, "2026-01-31")

        assert snap.shape == CurveShape.NORMAL
        assert snap.term_spread > 0
        assert not snap.is_inverted

    def test_inverted_curve(self):
        analyzer = YieldCurveAnalyzer()
        rates = _make_inverted_curve()
        snap = analyzer.analyze(rates, "2026-01-31")

        assert snap.shape == CurveShape.INVERTED
        assert snap.term_spread < 0
        assert snap.is_inverted

    def test_flat_curve(self):
        rates = {
            "3M": 4.50, "6M": 4.50, "1Y": 4.50, "2Y": 4.50,
            "5Y": 4.50, "10Y": 4.55, "30Y": 4.55,
        }
        analyzer = YieldCurveAnalyzer()
        snap = analyzer.analyze(rates, "2026-01-31")
        assert snap.shape == CurveShape.FLAT

    def test_nelson_siegel_fit(self):
        analyzer = YieldCurveAnalyzer()
        rates = _make_normal_curve()
        snap = analyzer.analyze(rates, "2026-01-31")

        # Level should be positive (average yield)
        assert snap.level > 0

    def test_term_spread_computation(self):
        rates = {"2Y": 4.00, "10Y": 4.50}
        analyzer = YieldCurveAnalyzer()
        snap = analyzer.analyze(rates, "2026-01-31")
        assert abs(snap.term_spread - 0.50) < 0.001

    def test_empty_rates(self):
        analyzer = YieldCurveAnalyzer()
        snap = analyzer.analyze({}, "2026-01-31")
        assert snap.rates == {}

    def test_history(self):
        analyzer = YieldCurveAnalyzer()
        analyzer.analyze(_make_normal_curve(), "2026-01-30")
        analyzer.analyze(_make_normal_curve(), "2026-01-31")
        assert len(analyzer.get_history()) == 2

    def test_reset(self):
        analyzer = YieldCurveAnalyzer()
        analyzer.analyze(_make_normal_curve(), "2026-01-31")
        analyzer.reset()
        assert len(analyzer.get_history()) == 0


# ── Regime Detector Tests ────────────────────────────────────


class TestMacroRegimeDetector:
    def _make_summary(self, breadth=0.7):
        n_imp = int(10 * breadth)
        n_det = 10 - n_imp
        return IndicatorSummary(
            composite_index=breadth - 0.5,
            n_improving=n_imp, n_deteriorating=n_det, n_stable=0,
            leading_score=breadth, coincident_score=breadth * 0.8,
            lagging_score=breadth * 0.6,
        )

    def test_expansion_regime(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.8)
        state = detector.detect(summary, growth_score=0.5, inflation_score=-0.3)
        assert state.regime == RegimeType.EXPANSION

    def test_slowdown_regime(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.5)
        state = detector.detect(summary, growth_score=0.3, inflation_score=0.5)
        assert state.regime == RegimeType.SLOWDOWN

    def test_contraction_regime(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.3)
        state = detector.detect(summary, growth_score=-0.5, inflation_score=0.3)
        assert state.regime == RegimeType.CONTRACTION

    def test_recovery_regime(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.4)
        state = detector.detect(summary, growth_score=-0.3, inflation_score=-0.5)
        assert state.regime == RegimeType.RECOVERY

    def test_probability_range(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.7)
        state = detector.detect(summary, growth_score=0.8, inflation_score=-0.5)
        assert 0 <= state.probability <= 1

    def test_duration_tracking(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.7)
        # Multiple expansion detections
        for _ in range(3):
            state = detector.detect(summary, growth_score=0.5, inflation_score=-0.3)
        assert state.duration >= 3

    def test_transition_probabilities(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.7)
        state = detector.detect(summary, growth_score=0.5, inflation_score=-0.3)
        assert len(state.transition_probs) == 4  # one per regime
        assert abs(sum(state.transition_probs.values()) - 1.0) < 0.01

    def test_history(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.7)
        detector.detect(summary, 0.5, -0.3)
        detector.detect(summary, 0.3, 0.2)
        assert len(detector.get_history()) == 2

    def test_reset(self):
        detector = RegimeDetector()
        summary = self._make_summary(0.7)
        detector.detect(summary, 0.5, -0.3)
        detector.reset()
        assert len(detector.get_history()) == 0


# ── Factor Model Tests ───────────────────────────────────────


class TestMacroFactorModel:
    def test_compute_factors(self):
        rng = np.random.RandomState(42)
        series = {
            "growth": list(rng.randn(24).cumsum()),
            "inflation": list(rng.randn(24).cumsum()),
            "rates": list(rng.randn(24).cumsum()),
        }
        model = MacroFactorModel()
        result = model.compute_factors(series)

        assert len(result.factor_returns) == 3
        assert len(result.factor_exposures) == 3
        assert result.dominant_factor in series

    def test_factor_momentum(self):
        # Strong upward trend
        series = {"growth": list(np.linspace(0, 10, 24))}
        model = MacroFactorModel()
        result = model.compute_factors(series)
        assert result.factor_momentum["growth"] > 0

    def test_regime_conditional(self):
        series = {"growth": list(np.linspace(0, 5, 24))}
        model = MacroFactorModel()
        result = model.compute_factors(series, regime=RegimeType.EXPANSION)
        assert "expansion" in result.regime_conditional

    def test_decompose_returns(self):
        rng = np.random.RandomState(42)
        n = 60
        factors = rng.randn(n, 3)
        betas = np.array([0.5, -0.3, 0.2])
        asset_returns = factors @ betas + rng.randn(n) * 0.1

        model = MacroFactorModel()
        contributions = model.decompose_returns(asset_returns, factors)
        assert "alpha" in contributions
        assert len(contributions) == 4  # 3 factors + alpha

    def test_decompose_too_few(self):
        model = MacroFactorModel()
        result = model.decompose_returns(np.array([1, 2]), np.array([[1], [2]]))
        assert result == {}

    def test_regime_factor_profile(self):
        series = {
            "growth": [1.0, -1.0, 0.5, -0.5] * 6,
            "inflation": [0.5, 0.5, -0.5, -0.5] * 6,
        }
        labels = [
            RegimeType.EXPANSION, RegimeType.CONTRACTION,
            RegimeType.SLOWDOWN, RegimeType.RECOVERY,
        ] * 6
        model = MacroFactorModel()
        profile = model.regime_factor_profile(series, labels)
        assert "expansion" in profile
        assert "growth" in profile["expansion"]

    def test_empty_factors(self):
        model = MacroFactorModel()
        result = model.compute_factors({})
        assert result.factor_returns == {}


# ── Integration Tests ────────────────────────────────────────


class TestMacroIntegration:
    def test_full_pipeline(self):
        """End-to-end: indicators -> regime -> factors."""
        # Track indicators
        tracker = IndicatorTracker()
        for i in range(12):
            tracker.add_indicator(EconomicIndicator(
                name="PMI", value=52 + i * 0.5, previous=52 + (i - 1) * 0.5,
                indicator_type=IndicatorType.LEADING,
            ))
            tracker.add_indicator(EconomicIndicator(
                name="GDP", value=2.5 + i * 0.1, previous=2.5 + (i - 1) * 0.1,
                indicator_type=IndicatorType.COINCIDENT,
            ))

        summary = tracker.summarize()
        assert summary.composite_index != 0

        # Yield curve
        curve = YieldCurveAnalyzer()
        snap = curve.analyze(_make_normal_curve(), "2026-01-31")
        assert snap.shape == CurveShape.NORMAL

        # Regime detection
        detector = RegimeDetector()
        state = detector.detect(summary, growth_score=0.6, inflation_score=-0.2)
        assert state.regime == RegimeType.EXPANSION

        # Factor model
        rng = np.random.RandomState(42)
        factor_series = {
            "growth": list(rng.randn(24).cumsum() + 1),
            "inflation": list(rng.randn(24).cumsum()),
        }
        model = MacroFactorModel()
        factors = model.compute_factors(factor_series, state.regime)
        assert factors.dominant_factor in factor_series


class TestMacroModuleImports:
    def test_top_level_imports(self):
        from src.macro import (
            IndicatorTracker,
            YieldCurveAnalyzer,
            RegimeDetector,
            MacroFactorModel,
            EconomicIndicator,
            IndicatorSummary,
            YieldCurveSnapshot,
            RegimeState,
            MacroFactorResult,
            RegimeType,
            CurveShape,
            IndicatorType,
            MacroFactor,
            DEFAULT_CONFIG,
        )
        assert DEFAULT_CONFIG is not None
