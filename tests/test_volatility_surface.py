"""Tests for PRD-64: Volatility Surface Modeling.

Covers SVI calibration, skew analytics, term structure modeling,
and volatility regime signals.
"""

import pytest
import numpy as np

from src.volatility.svi_model import (
    SVIParams,
    SVISurface,
    CalibrationResult,
    SVICalibrator,
)
from src.volatility.skew_analytics import (
    RiskReversal,
    SkewDynamics,
    SkewTermStructure,
    SkewRegime,
    SkewAnalyzer,
)
from src.volatility.term_model import (
    TermStructureFit,
    CarryRollDown,
    TermDynamics,
    TermComparison,
    TermStructureModeler,
)
from src.volatility.vol_regime_signals import (
    VolOfVol,
    MeanReversionSignal,
    RegimeTransitionSignal,
    VolSignalSummary,
    VolRegimeSignalGenerator,
)


# ===================================================================
# SVI Model Tests
# ===================================================================
class TestSVIParams:
    def test_atm_variance(self):
        p = SVIParams(a=0.04, b=0.1, rho=-0.3, sigma=0.2, tenor_days=30)
        assert p.atm_variance > 0

    def test_atm_vol(self):
        p = SVIParams(a=0.04, b=0.1, rho=-0.3, sigma=0.2, tenor_days=30)
        vol = p.atm_vol
        assert 0.0 < vol < 2.0

    def test_arbitrage_free(self):
        p = SVIParams(a=0.04, b=0.1, rho=-0.3, sigma=0.2)
        assert p.is_arbitrage_free

    def test_arbitrage_violation_negative_b(self):
        p = SVIParams(a=0.04, b=-0.1, rho=-0.3, sigma=0.2)
        assert not p.is_arbitrage_free


class TestSVISurface:
    def setup_method(self):
        self.surface = SVISurface(
            symbol="AAPL",
            slices={
                30: SVIParams(a=0.04, b=0.10, rho=-0.3, m=0.0, sigma=0.2, tenor_days=30),
                60: SVIParams(a=0.05, b=0.12, rho=-0.25, m=0.0, sigma=0.22, tenor_days=60),
                90: SVIParams(a=0.055, b=0.11, rho=-0.28, m=0.0, sigma=0.21, tenor_days=90),
            },
            spot=200.0,
        )

    def test_tenors(self):
        assert self.surface.tenors == [30, 60, 90]

    def test_n_slices(self):
        assert self.surface.n_slices == 3

    def test_get_iv_exact_tenor(self):
        iv = self.surface.get_iv(0.0, 30)
        assert iv > 0

    def test_get_iv_interpolated_tenor(self):
        iv = self.surface.get_iv(0.0, 45)
        iv30 = self.surface.get_iv(0.0, 30)
        iv60 = self.surface.get_iv(0.0, 60)
        assert min(iv30, iv60) <= iv <= max(iv30, iv60) + 0.01

    def test_get_iv_beyond_range(self):
        iv = self.surface.get_iv(0.0, 120)
        assert iv > 0

    def test_empty_surface(self):
        s = SVISurface()
        iv = s.get_iv(0.0, 30)
        assert iv == 0.2  # Default fallback


class TestCalibrationResult:
    def test_good_fit(self):
        cr = CalibrationResult(converged=True, final_rmse=0.009)
        assert cr.is_good_fit
        assert cr.quality_label == "excellent"

    def test_fair_fit(self):
        cr = CalibrationResult(converged=True, final_rmse=0.04)
        assert not cr.is_good_fit
        assert cr.quality_label == "fair"

    def test_poor_fit(self):
        cr = CalibrationResult(converged=False, final_rmse=0.10)
        assert cr.quality_label == "poor"


class TestSVICalibrator:
    def setup_method(self):
        self.calibrator = SVICalibrator(max_iterations=100)

    def test_calibrate_slice(self):
        # Generate synthetic smile data
        k = np.linspace(-0.2, 0.2, 9)
        true_a, true_b, true_rho, true_m, true_sigma = 0.04, 0.1, -0.3, 0.0, 0.2
        true_var = true_a + true_b * (
            true_rho * (k - true_m) + np.sqrt((k - true_m) ** 2 + true_sigma ** 2)
        )
        true_iv = np.sqrt(true_var / (30 / 365.0))

        params = self.calibrator.calibrate_slice(k, true_iv, 30)
        assert params.tenor_days == 30
        assert params.b >= 0
        assert abs(params.rho) < 1
        assert params.sigma > 0

    def test_calibrate_surface(self):
        k = np.linspace(-0.15, 0.15, 7)
        iv_data = {}
        for tenor in [30, 60, 90]:
            t = tenor / 365.0
            base_var = 0.04 + 0.01 * (tenor / 30)
            var = base_var + 0.1 * (
                -0.3 * k + np.sqrt(k ** 2 + 0.04)
            )
            iv = np.sqrt(np.maximum(var, 0.001) / t)
            iv_data[tenor] = (k, iv)

        result = self.calibrator.calibrate_surface(iv_data, spot=100, symbol="AAPL")
        assert result.surface.n_slices == 3
        assert result.surface.symbol == "AAPL"
        assert result.final_rmse >= 0

    def test_calibrate_empty_data(self):
        params = self.calibrator.calibrate_slice(
            np.array([]), np.array([]), 30
        )
        assert params.tenor_days == 30

    def test_compare_surfaces(self):
        s1 = SVISurface(slices={
            30: SVIParams(a=0.04, b=0.10, rho=-0.3, tenor_days=30),
        })
        s2 = SVISurface(slices={
            30: SVIParams(a=0.05, b=0.12, rho=-0.28, tenor_days=30),
        })
        comp = self.calibrator.compare_surfaces(s1, s2)
        assert 30 in comp["common_tenors"]
        assert comp["diffs"][30]["delta_a"] == pytest.approx(-0.01, abs=0.001)


# ===================================================================
# Skew Analytics Tests
# ===================================================================
class TestRiskReversal:
    def test_put_skew(self):
        rr = RiskReversal(put_vol=0.30, call_vol=0.22, risk_reversal=0.09)
        assert rr.skew_direction == "put_skew"
        assert rr.skew_magnitude == "extreme"

    def test_call_skew(self):
        rr = RiskReversal(risk_reversal=-0.03)
        assert rr.skew_direction == "call_skew"

    def test_symmetric(self):
        rr = RiskReversal(risk_reversal=0.005)
        assert rr.skew_direction == "symmetric"

    def test_magnitude_levels(self):
        assert RiskReversal(risk_reversal=0.09).skew_magnitude == "extreme"
        assert RiskReversal(risk_reversal=0.05).skew_magnitude == "elevated"
        assert RiskReversal(risk_reversal=0.025).skew_magnitude == "moderate"
        assert RiskReversal(risk_reversal=0.01).skew_magnitude == "low"


class TestSkewDynamics:
    def test_extreme(self):
        sd = SkewDynamics(z_score=2.5)
        assert sd.is_extreme

    def test_cheap_skew(self):
        sd = SkewDynamics(z_score=-1.5)
        assert sd.is_cheap
        assert not sd.is_expensive

    def test_expensive_skew(self):
        sd = SkewDynamics(z_score=1.5)
        assert sd.is_expensive
        assert not sd.is_cheap


class TestSkewAnalyzer:
    def setup_method(self):
        self.analyzer = SkewAnalyzer()

    def test_compute_risk_reversal(self):
        rr = self.analyzer.compute_risk_reversal(
            put_vol=0.28, call_vol=0.22, atm_vol=0.24,
            tenor_days=30, symbol="AAPL",
        )
        assert rr.risk_reversal == pytest.approx(0.06, abs=0.001)
        assert rr.butterfly == pytest.approx(0.01, abs=0.001)

    def test_compute_from_smile(self):
        smile = [(0.85, 0.30), (0.90, 0.27), (0.95, 0.24),
                 (1.0, 0.22), (1.05, 0.23), (1.10, 0.25)]
        rr = self.analyzer.compute_from_smile(smile, tenor_days=30, symbol="AAPL")
        assert rr.risk_reversal != 0.0
        assert rr.atm_vol > 0

    def test_skew_dynamics(self):
        history = [0.04 + np.random.normal(0, 0.01) for _ in range(50)]
        history[-1] = 0.08  # Current much higher than average
        sd = self.analyzer.skew_dynamics(history, symbol="AAPL")
        assert sd.z_score > 1.0
        assert sd.n_observations == 50

    def test_skew_dynamics_short(self):
        sd = self.analyzer.skew_dynamics([0.03, 0.04], symbol="AAPL")
        assert sd.n_observations == 2

    def test_skew_term_structure_normal(self):
        tenor_rr = [(30, 0.04), (60, 0.05), (90, 0.06)]
        ts = self.analyzer.skew_term_structure(tenor_rr, symbol="AAPL")
        assert ts.shape == "normal"
        assert ts.n_tenors == 3

    def test_skew_term_structure_inverted(self):
        tenor_rr = [(30, 0.08), (60, 0.06), (90, 0.03)]
        ts = self.analyzer.skew_term_structure(tenor_rr, symbol="AAPL")
        assert ts.shape == "inverted"

    def test_classify_regime_panic(self):
        regime = self.analyzer.classify_regime(rr=0.08, butterfly=0.03, symbol="AAPL")
        assert regime.is_panic
        assert regime.confidence > 0.3

    def test_classify_regime_complacent(self):
        regime = self.analyzer.classify_regime(rr=0.005, butterfly=0.002, symbol="AAPL")
        assert regime.is_complacent

    def test_classify_regime_normal(self):
        regime = self.analyzer.classify_regime(rr=0.03, butterfly=0.01, symbol="AAPL")
        assert regime.regime == "normal"


# ===================================================================
# Term Structure Modeling Tests
# ===================================================================
class TestTermStructureFit:
    def test_long_short_vol(self):
        fit = TermStructureFit(beta0=0.20, beta1=-0.05)
        assert fit.long_term_vol == 0.20
        assert fit.short_term_vol == pytest.approx(0.15)

    def test_slope(self):
        fit = TermStructureFit(beta0=0.20, beta1=-0.05)
        assert fit.slope == 0.05  # Contango

    def test_predict(self):
        fit = TermStructureFit(beta0=0.20, beta1=-0.03, beta2=0.01, tau=90.0)
        vol_30 = fit.predict(30)
        vol_180 = fit.predict(180)
        assert vol_30 > 0
        assert vol_180 > 0

    def test_good_fit(self):
        fit = TermStructureFit(rmse=0.01, n_points=5)
        assert fit.is_good_fit


class TestCarryRollDown:
    def test_positive_carry(self):
        crd = CarryRollDown(vol_carry=0.02)
        assert crd.is_positive_carry

    def test_carry_signal_sell(self):
        crd = CarryRollDown(total_pnl_bps=60.0)
        assert crd.carry_signal == "strong_sell_vol"

    def test_carry_signal_neutral(self):
        crd = CarryRollDown(total_pnl_bps=5.0)
        assert crd.carry_signal == "neutral"

    def test_carry_signal_buy(self):
        crd = CarryRollDown(total_pnl_bps=-55.0)
        assert crd.carry_signal == "strong_buy_vol"


class TestTermStructureModeler:
    def setup_method(self):
        self.modeler = TermStructureModeler()

    def test_fit_basic(self):
        tenor_vol = [(30, 0.22), (60, 0.23), (90, 0.235), (180, 0.24), (365, 0.25)]
        fit = self.modeler.fit(tenor_vol, symbol="AAPL")
        assert fit.n_points == 5
        assert fit.rmse >= 0
        assert fit.symbol == "AAPL"

    def test_fit_insufficient_points(self):
        fit = self.modeler.fit([(30, 0.22), (60, 0.23)], symbol="X")
        assert fit.n_points == 2

    def test_carry_roll_down(self):
        fit = TermStructureFit(beta0=0.22, beta1=-0.02, beta2=0.005, tau=90.0)
        crd = self.modeler.carry_roll_down(fit, realized_vol=0.18, tenor_days=30)
        assert crd.vol_carry > 0  # IV > RV
        assert crd.current_iv > 0

    def test_classify_shape_contango(self):
        shape = self.modeler.classify_shape([(30, 0.20), (60, 0.22), (90, 0.25)])
        assert shape == "contango"

    def test_classify_shape_backwardation(self):
        shape = self.modeler.classify_shape([(30, 0.28), (60, 0.24), (90, 0.20)])
        assert shape == "backwardation"

    def test_classify_shape_humped(self):
        shape = self.modeler.classify_shape([(30, 0.20), (60, 0.28), (90, 0.21)])
        assert shape == "humped"

    def test_track_dynamics_steepening(self):
        prior = [(30, 0.20), (60, 0.22), (90, 0.24)]
        current = [(30, 0.20), (60, 0.24), (90, 0.28)]
        dyn = self.modeler.track_dynamics(current, prior, symbol="AAPL")
        assert dyn.current_shape == "contango"
        assert dyn.slope_current > dyn.slope_prior

    def test_compare_term_structures(self):
        fits = [
            TermStructureFit(symbol="AAPL", beta0=0.22, beta1=-0.05),
            TermStructureFit(symbol="MSFT", beta0=0.18, beta1=-0.01),
        ]
        comp = self.modeler.compare_term_structures(fits)
        assert comp.n_symbols == 2
        assert comp.highest_level == "AAPL"
        assert comp.lowest_level == "MSFT"


# ===================================================================
# Vol Regime Signals Tests
# ===================================================================
class TestVolOfVol:
    def test_elevated(self):
        vov = VolOfVol(vol_of_vol_percentile=80.0)
        assert vov.is_elevated
        assert not vov.is_suppressed

    def test_suppressed(self):
        vov = VolOfVol(vol_of_vol_percentile=20.0)
        assert vov.is_suppressed

    def test_stability_score(self):
        vov = VolOfVol(vol_of_vol_percentile=30.0)
        assert vov.stability_score == pytest.approx(0.7)


class TestMeanReversionSignal:
    def test_actionable(self):
        mr = MeanReversionSignal(z_score=2.0, half_life_days=15.0)
        assert mr.is_actionable

    def test_not_actionable(self):
        mr = MeanReversionSignal(z_score=0.5, half_life_days=15.0)
        assert not mr.is_actionable

    def test_signal_strength(self):
        mr = MeanReversionSignal(z_score=1.5)
        assert mr.signal_strength == pytest.approx(0.5)


class TestRegimeTransitionSignal:
    def test_risk_off(self):
        rt = RegimeTransitionSignal(signal="risk_off")
        assert rt.is_risk_off

    def test_confirmed(self):
        rt = RegimeTransitionSignal(days_in_new_regime=5)
        assert rt.is_confirmed
        rt2 = RegimeTransitionSignal(days_in_new_regime=1)
        assert not rt2.is_confirmed


class TestVolSignalSummary:
    def test_strong_signal(self):
        vs = VolSignalSummary(composite_strength=0.7)
        assert vs.is_strong_signal

    def test_recommended_action(self):
        assert VolSignalSummary(composite_signal="strong_risk_off").recommended_action == "reduce_exposure"
        assert VolSignalSummary(composite_signal="risk_off").recommended_action == "add_hedges"
        assert VolSignalSummary(composite_signal="risk_on").recommended_action == "reduce_hedges"
        assert VolSignalSummary(composite_signal="strong_risk_on").recommended_action == "increase_exposure"
        assert VolSignalSummary(composite_signal="neutral").recommended_action == "hold"


class TestVolRegimeSignalGenerator:
    def setup_method(self):
        self.gen = VolRegimeSignalGenerator()

    def test_vol_of_vol(self):
        series = list(np.random.normal(0.20, 0.02, 100))
        vov = self.gen.compute_vol_of_vol(series, symbol="AAPL")
        assert vov.vol_of_vol > 0
        assert vov.n_periods == 100

    def test_vol_of_vol_short(self):
        vov = self.gen.compute_vol_of_vol([0.2, 0.21, 0.19], symbol="X")
        assert vov.n_periods == 3

    def test_mean_reversion_sell_vol(self):
        # Vol well above mean
        series = list(np.random.normal(0.20, 0.02, 100))
        series[-1] = 0.35  # Current much higher
        mr = self.gen.mean_reversion_signal(series, symbol="AAPL")
        assert mr.z_score > 1.5
        assert mr.signal == "sell_vol"

    def test_mean_reversion_buy_vol(self):
        series = list(np.random.normal(0.25, 0.02, 100))
        series[-1] = 0.15  # Current much lower
        mr = self.gen.mean_reversion_signal(series, symbol="AAPL")
        assert mr.z_score < -1.5
        assert mr.signal == "buy_vol"

    def test_mean_reversion_short(self):
        mr = self.gen.mean_reversion_signal([0.2, 0.21], symbol="X")
        assert mr.signal == "neutral"

    def test_regime_transition_spike(self):
        sig = self.gen.regime_transition_signal("low", "high", days_in_new=2, symbol="AAPL")
        assert sig.transition_type == "spike"
        assert sig.signal == "risk_off"
        assert sig.strength > 0.5

    def test_regime_transition_normalization(self):
        sig = self.gen.regime_transition_signal("extreme", "normal", days_in_new=5, symbol="AAPL")
        assert sig.transition_type == "normalization"
        assert sig.signal == "risk_on"

    def test_generate_summary_with_transition(self):
        series = list(np.random.normal(0.20, 0.02, 100))
        summary = self.gen.generate_summary(
            vol_series=series,
            current_regime="high",
            prev_regime="normal",
            days_in_regime=3,
            symbol="AAPL",
        )
        assert summary.vol_of_vol is not None
        assert summary.mean_reversion is not None
        assert summary.regime_transition is not None
        assert summary.n_signals > 0

    def test_generate_summary_no_transition(self):
        series = list(np.random.normal(0.20, 0.02, 100))
        summary = self.gen.generate_summary(
            vol_series=series,
            current_regime="normal",
            symbol="AAPL",
        )
        assert summary.regime_transition is None
        assert summary.composite_signal in [
            "strong_risk_off", "risk_off", "neutral", "risk_on", "strong_risk_on"
        ]

    def test_regime_transition_confirmed(self):
        sig = self.gen.regime_transition_signal("normal", "high", days_in_new=5)
        assert sig.is_confirmed
        # Strength should be boosted
        sig2 = self.gen.regime_transition_signal("normal", "high", days_in_new=1)
        assert sig.strength >= sig2.strength
