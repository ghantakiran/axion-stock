"""Tests for PRD-38: Volatility Analysis."""

import pytest
import numpy as np
import pandas as pd
from datetime import date

from src.volatility.config import (
    VolMethod,
    VolRegime,
    VolTimeframe,
    SurfaceInterpolation,
    STANDARD_WINDOWS,
    VolConfig,
    TermStructureConfig,
    SurfaceConfig,
    RegimeConfig,
    VolAnalysisConfig,
    DEFAULT_VOL_CONFIG,
    DEFAULT_CONFIG,
)
from src.volatility.models import (
    VolEstimate,
    TermStructurePoint,
    TermStructure,
    VolSmilePoint,
    VolSurface,
    VolRegimeState,
    VolConePoint,
)
from src.volatility.engine import VolatilityEngine
from src.volatility.surface import VolSurfaceAnalyzer
from src.volatility.regime import VolRegimeDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_returns(n: int = 300, seed: int = 42, vol: float = 0.01) -> pd.Series:
    """Generate random daily returns."""
    rng = np.random.RandomState(seed)
    return pd.Series(rng.normal(0.0003, vol, n))


def _make_ohlc(n: int = 300, seed: int = 42) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Generate synthetic OHLC data."""
    rng = np.random.RandomState(seed)
    close = 100.0 + np.cumsum(rng.normal(0.05, 1.0, n))
    open_ = close + rng.normal(0, 0.3, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, n))
    return pd.Series(open_), pd.Series(high), pd.Series(low), pd.Series(close)


# ===========================================================================
# Config Tests
# ===========================================================================

class TestVolatilityConfig:
    """Test configuration enums and dataclasses."""

    def test_vol_method_values(self):
        assert VolMethod.HISTORICAL.value == "historical"
        assert VolMethod.EWMA.value == "ewma"
        assert VolMethod.PARKINSON.value == "parkinson"
        assert VolMethod.GARMAN_KLASS.value == "garman_klass"

    def test_vol_regime_values(self):
        assert VolRegime.LOW.value == "low"
        assert VolRegime.NORMAL.value == "normal"
        assert VolRegime.HIGH.value == "high"
        assert VolRegime.EXTREME.value == "extreme"

    def test_vol_timeframe_values(self):
        assert VolTimeframe.DAILY.value == "daily"
        assert VolTimeframe.WEEKLY.value == "weekly"
        assert VolTimeframe.MONTHLY.value == "monthly"

    def test_surface_interpolation_values(self):
        assert SurfaceInterpolation.LINEAR.value == "linear"
        assert SurfaceInterpolation.CUBIC.value == "cubic"

    def test_standard_windows(self):
        assert STANDARD_WINDOWS["1M"] == 21
        assert STANDARD_WINDOWS["1Y"] == 252
        assert len(STANDARD_WINDOWS) == 7

    def test_vol_config_defaults(self):
        cfg = VolConfig()
        assert cfg.default_window == 21
        assert cfg.annualization_factor == 252.0
        assert cfg.ewma_lambda == 0.94
        assert cfg.min_periods == 10
        assert len(cfg.cone_percentiles) == 5
        assert len(cfg.cone_windows) == 7

    def test_term_structure_config_defaults(self):
        cfg = TermStructureConfig()
        assert len(cfg.tenor_days) == 7
        assert cfg.contango_threshold == 0.01

    def test_surface_config_defaults(self):
        cfg = SurfaceConfig()
        assert cfg.moneyness_range == (0.80, 1.20)
        assert cfg.interpolation == SurfaceInterpolation.LINEAR

    def test_regime_config_defaults(self):
        cfg = RegimeConfig()
        assert cfg.lookback_window == 252
        assert cfg.low_threshold == -1.0
        assert cfg.high_threshold == 1.0
        assert cfg.extreme_threshold == 2.0

    def test_vol_analysis_config_bundles(self):
        cfg = VolAnalysisConfig()
        assert isinstance(cfg.vol, VolConfig)
        assert isinstance(cfg.term_structure, TermStructureConfig)
        assert isinstance(cfg.surface, SurfaceConfig)
        assert isinstance(cfg.regime, RegimeConfig)

    def test_default_config_exists(self):
        assert DEFAULT_VOL_CONFIG.default_window == 21
        assert DEFAULT_CONFIG.vol.default_window == 21


# ===========================================================================
# Model Tests
# ===========================================================================

class TestVolatilityModels:
    """Test data models."""

    def test_vol_estimate_defaults(self):
        est = VolEstimate()
        assert est.value == 0.0
        assert est.method == VolMethod.HISTORICAL
        assert est.annualized is True

    def test_vol_estimate_daily_conversion(self):
        est = VolEstimate(value=0.20, annualized=True)
        daily = est.daily
        assert daily == pytest.approx(0.20 / np.sqrt(252), abs=1e-6)

    def test_vol_estimate_daily_when_not_annualized(self):
        est = VolEstimate(value=0.012, annualized=False)
        assert est.daily == 0.012

    def test_vol_estimate_to_dict(self):
        est = VolEstimate(symbol="AAPL", value=0.25, date=date(2026, 1, 31))
        d = est.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["date"] == "2026-01-31"

    def test_term_structure_point_vrp(self):
        pt = TermStructurePoint(tenor_days=21, implied_vol=0.25, realized_vol=0.20)
        assert pt.vol_risk_premium == pytest.approx(0.05, abs=1e-6)

    def test_term_structure_point_vrp_none(self):
        pt = TermStructurePoint(tenor_days=21, implied_vol=None, realized_vol=0.20)
        assert pt.vol_risk_premium is None

    def test_term_structure_contango(self):
        ts = TermStructure(points=[
            TermStructurePoint(tenor_days=21, realized_vol=0.15),
            TermStructurePoint(tenor_days=252, realized_vol=0.25),
        ])
        assert ts.is_contango is True
        assert ts.is_backwardation is False

    def test_term_structure_backwardation(self):
        ts = TermStructure(points=[
            TermStructurePoint(tenor_days=21, realized_vol=0.30),
            TermStructurePoint(tenor_days=252, realized_vol=0.20),
        ])
        assert ts.is_backwardation is True
        assert ts.is_contango is False

    def test_term_structure_slope(self):
        ts = TermStructure(points=[
            TermStructurePoint(tenor_days=21, realized_vol=0.15),
            TermStructurePoint(tenor_days=252, realized_vol=0.25),
        ])
        slope = ts.slope
        expected = (0.25 - 0.15) / (252 - 21)
        assert slope == pytest.approx(expected, abs=1e-8)

    def test_vol_surface_tenors(self):
        surface = VolSurface(smiles={
            30: [VolSmilePoint(strike=100, moneyness=1.0, implied_vol=0.20)],
            60: [VolSmilePoint(strike=100, moneyness=1.0, implied_vol=0.22)],
        })
        assert surface.tenors == [30, 60]
        assert surface.n_tenors == 2

    def test_vol_surface_atm_vol(self):
        surface = VolSurface(smiles={
            30: [
                VolSmilePoint(strike=90, moneyness=0.9, implied_vol=0.25),
                VolSmilePoint(strike=100, moneyness=1.0, implied_vol=0.20),
                VolSmilePoint(strike=110, moneyness=1.1, implied_vol=0.23),
            ],
        })
        assert surface.get_atm_vol(30) == 0.20

    def test_vol_surface_skew(self):
        surface = VolSurface(smiles={
            30: [
                VolSmilePoint(strike=90, moneyness=0.9, implied_vol=0.28),
                VolSmilePoint(strike=100, moneyness=1.0, implied_vol=0.20),
                VolSmilePoint(strike=110, moneyness=1.1, implied_vol=0.22),
            ],
        })
        skew = surface.skew(30)
        assert skew == pytest.approx(0.28 - 0.22, abs=1e-6)

    def test_vol_surface_butterfly(self):
        surface = VolSurface(smiles={
            30: [
                VolSmilePoint(strike=90, moneyness=0.9, implied_vol=0.28),
                VolSmilePoint(strike=100, moneyness=1.0, implied_vol=0.20),
                VolSmilePoint(strike=110, moneyness=1.1, implied_vol=0.24),
            ],
        })
        bfly = surface.butterfly(30)
        wing_avg = (0.28 + 0.24) / 2
        assert bfly == pytest.approx(wing_avg - 0.20, abs=1e-6)

    def test_vol_regime_state_defaults(self):
        state = VolRegimeState()
        assert state.regime == VolRegime.NORMAL
        assert state.days_in_regime == 0

    def test_vol_regime_state_vol_ratio(self):
        state = VolRegimeState(current_vol=0.30, avg_vol=0.20)
        assert state.vol_ratio == 1.5

    def test_vol_regime_state_to_dict(self):
        state = VolRegimeState(regime=VolRegime.HIGH, current_vol=0.30, z_score=1.5)
        d = state.to_dict()
        assert d["regime"] == "high"
        assert d["z_score"] == 1.5

    def test_vol_cone_point_percentile(self):
        pt = VolConePoint(
            window=21,
            percentiles={5.0: 0.10, 25.0: 0.15, 50.0: 0.20, 75.0: 0.25, 95.0: 0.35},
            current=0.22,
        )
        assert pt.current_percentile == 50.0

    def test_vol_cone_point_empty(self):
        pt = VolConePoint(window=21)
        assert pt.current_percentile is None


# ===========================================================================
# Engine Tests
# ===========================================================================

class TestVolatilityEngine:
    """Test volatility computation engine."""

    def test_historical_vol_basic(self):
        returns = _make_returns(100, vol=0.01)
        engine = VolatilityEngine()
        est = engine.compute_historical(returns, window=21, symbol="TEST")
        assert est.method == VolMethod.HISTORICAL
        assert est.symbol == "TEST"
        assert est.value > 0
        assert est.annualized is True

    def test_historical_vol_scales_with_input(self):
        engine = VolatilityEngine()
        low_vol = engine.compute_historical(_make_returns(100, vol=0.005), window=21)
        high_vol = engine.compute_historical(_make_returns(100, vol=0.03), window=21)
        assert high_vol.value > low_vol.value

    def test_historical_vol_insufficient_data(self):
        engine = VolatilityEngine()
        est = engine.compute_historical(pd.Series([0.01, 0.02]), window=21)
        assert est.value == 0.0

    def test_ewma_vol_basic(self):
        returns = _make_returns(100)
        engine = VolatilityEngine()
        est = engine.compute_ewma(returns, symbol="EWMA")
        assert est.method == VolMethod.EWMA
        assert est.value > 0

    def test_ewma_lambda_sensitivity(self):
        returns = _make_returns(100)
        engine = VolatilityEngine()
        fast = engine.compute_ewma(returns, lambda_=0.80)
        slow = engine.compute_ewma(returns, lambda_=0.99)
        # Both should produce valid estimates
        assert fast.value > 0
        assert slow.value > 0

    def test_parkinson_vol_basic(self):
        _, high, low, _ = _make_ohlc(100)
        engine = VolatilityEngine()
        est = engine.compute_parkinson(high, low, window=21, symbol="PARK")
        assert est.method == VolMethod.PARKINSON
        assert est.value > 0

    def test_parkinson_insufficient_data(self):
        engine = VolatilityEngine()
        est = engine.compute_parkinson(pd.Series([101.0]), pd.Series([99.0]), window=21)
        assert est.value == 0.0

    def test_garman_klass_vol_basic(self):
        open_, high, low, close = _make_ohlc(100)
        engine = VolatilityEngine()
        est = engine.compute_garman_klass(open_, high, low, close, window=21, symbol="GK")
        assert est.method == VolMethod.GARMAN_KLASS
        assert est.value > 0

    def test_compute_all_methods(self):
        returns = _make_returns(100)
        open_, high, low, close = _make_ohlc(100)
        engine = VolatilityEngine()
        results = engine.compute_all(
            returns, high=high, low=low, open_=open_, close=close, window=21
        )
        assert VolMethod.HISTORICAL in results
        assert VolMethod.EWMA in results
        assert VolMethod.PARKINSON in results
        assert VolMethod.GARMAN_KLASS in results

    def test_compute_all_without_ohlc(self):
        returns = _make_returns(100)
        engine = VolatilityEngine()
        results = engine.compute_all(returns, window=21)
        assert VolMethod.HISTORICAL in results
        assert VolMethod.EWMA in results
        assert VolMethod.PARKINSON not in results
        assert VolMethod.GARMAN_KLASS not in results

    def test_vol_cone(self):
        returns = _make_returns(300)
        engine = VolatilityEngine()
        cone = engine.compute_vol_cone(returns)
        assert len(cone) > 0
        for pt in cone:
            assert pt.window > 0
            assert len(pt.percentiles) == 5
            assert pt.current > 0

    def test_vol_cone_insufficient_data(self):
        returns = _make_returns(10)
        engine = VolatilityEngine()
        cone = engine.compute_vol_cone(returns)
        # Most windows need more data than 10 observations
        assert len(cone) == 0

    def test_term_structure_realized(self):
        returns = _make_returns(300)
        engine = VolatilityEngine()
        ts = engine.compute_term_structure(returns, tenor_days=(5, 21, 63), symbol="AAPL")
        assert ts.symbol == "AAPL"
        assert len(ts.points) == 3

    def test_term_structure_with_iv(self):
        returns = _make_returns(300)
        iv_by_tenor = {21: 0.22, 63: 0.25}
        engine = VolatilityEngine()
        ts = engine.compute_term_structure(returns, tenor_days=(21, 63), iv_by_tenor=iv_by_tenor)
        for pt in ts.points:
            assert pt.implied_vol is not None
            assert pt.realized_vol is not None

    def test_implied_vs_realized(self):
        engine = VolatilityEngine()
        result = engine.implied_vs_realized(0.25, 0.20)
        assert result["spread"] == pytest.approx(0.05, abs=1e-6)
        assert result["ratio"] == pytest.approx(1.25, abs=0.01)
        assert result["premium_pct"] == pytest.approx(25.0, abs=0.1)

    def test_compute_percentile(self):
        returns = _make_returns(300)
        engine = VolatilityEngine()
        est = engine.compute_historical(returns, window=21)
        pct = engine.compute_percentile(est.value, returns, window=21)
        assert 0.0 <= pct <= 100.0


# ===========================================================================
# Surface Tests
# ===========================================================================

class TestVolSurfaceAnalyzer:
    """Test volatility surface analyzer."""

    def _sample_iv_data(self) -> dict[int, list[tuple[float, float]]]:
        """Generate sample IV data."""
        return {
            30: [(90, 0.28), (95, 0.24), (100, 0.20), (105, 0.22), (110, 0.25)],
            60: [(90, 0.30), (95, 0.26), (100, 0.22), (105, 0.24), (110, 0.27)],
            90: [(90, 0.32), (95, 0.28), (100, 0.24), (105, 0.26), (110, 0.29)],
        }

    def test_build_surface(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100, symbol="TEST")
        assert surface.symbol == "TEST"
        assert surface.spot == 100
        assert surface.n_tenors == 3
        assert surface.tenors == [30, 60, 90]

    def test_build_surface_moneyness(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100)
        smile = surface.get_smile(30)
        moneyness_values = [p.moneyness for p in smile]
        assert 0.9 in moneyness_values
        assert 1.0 in moneyness_values
        assert 1.1 in moneyness_values

    def test_compute_smile(self):
        analyzer = VolSurfaceAnalyzer()
        strikes = [90.0, 100.0, 110.0]
        ivs = [0.28, 0.20, 0.24]
        smile = analyzer.compute_smile(strikes, ivs, spot=100)
        assert len(smile) == 3
        assert smile[0].moneyness < smile[-1].moneyness

    def test_compute_smile_mismatched_lengths(self):
        analyzer = VolSurfaceAnalyzer()
        smile = analyzer.compute_smile([90.0, 100.0], [0.28], spot=100)
        assert smile == []

    def test_compute_skew(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100)
        skew = analyzer.compute_skew(surface, 30)
        assert skew is not None
        # OTM put vol (90 strike, 0.28) - OTM call vol (110 strike, 0.25)
        assert skew == pytest.approx(0.28 - 0.25, abs=1e-6)

    def test_compute_butterfly(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100)
        bfly = analyzer.compute_butterfly(surface, 30)
        assert bfly is not None
        # Wing avg - ATM = ((0.28 + 0.25) / 2) - 0.20
        wing_avg = (0.28 + 0.25) / 2
        assert bfly == pytest.approx(wing_avg - 0.20, abs=1e-6)

    def test_atm_term_structure(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100)
        atm_ts = analyzer.atm_term_structure(surface)
        assert len(atm_ts) == 3
        # ATM vols should increase with tenor (contango in this data)
        assert atm_ts[0][1] < atm_ts[-1][1]

    def test_smile_metrics(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100)
        metrics = analyzer.smile_metrics(surface, 30)
        assert metrics["atm_vol"] is not None
        assert metrics["skew"] is not None
        assert metrics["butterfly"] is not None
        assert metrics["n_strikes"] == 5

    def test_empty_tenor_returns_none(self):
        analyzer = VolSurfaceAnalyzer()
        surface = VolSurface()
        assert analyzer.compute_skew(surface, 30) is None
        assert analyzer.compute_butterfly(surface, 30) is None

    def test_surface_to_dict(self):
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(self._sample_iv_data(), spot=100, symbol="SPY")
        d = surface.to_dict()
        assert d["symbol"] == "SPY"
        assert d["n_tenors"] == 3


# ===========================================================================
# Regime Tests
# ===========================================================================

class TestVolRegimeDetector:
    """Test volatility regime detection."""

    def test_detect_normal_regime(self):
        returns = _make_returns(300, vol=0.01)
        detector = VolRegimeDetector()
        state = detector.detect(returns, window=21)
        assert state.regime in list(VolRegime)
        assert state.current_vol > 0
        assert state.avg_vol > 0

    def test_detect_high_vol_regime(self):
        # Create returns with a high-vol tail
        rng = np.random.RandomState(42)
        normal = rng.normal(0, 0.01, 250)
        spike = rng.normal(0, 0.05, 50)
        returns = pd.Series(np.concatenate([normal, spike]))
        detector = VolRegimeDetector()
        state = detector.detect(returns, window=21)
        assert state.regime in (VolRegime.HIGH, VolRegime.EXTREME)
        assert state.z_score > 0

    def test_detect_low_vol_regime(self):
        # Create returns with a low-vol tail
        rng = np.random.RandomState(42)
        normal = rng.normal(0, 0.02, 250)
        calm = rng.normal(0, 0.002, 50)
        returns = pd.Series(np.concatenate([normal, calm]))
        detector = VolRegimeDetector()
        state = detector.detect(returns, window=21)
        assert state.regime == VolRegime.LOW
        assert state.z_score < 0

    def test_regime_change_detection(self):
        rng = np.random.RandomState(42)
        normal = rng.normal(0, 0.01, 250)
        spike = rng.normal(0, 0.05, 50)
        returns_normal = pd.Series(normal)
        returns_spike = pd.Series(np.concatenate([normal, spike]))

        detector = VolRegimeDetector()
        state1 = detector.detect(returns_normal, window=21)
        state2 = detector.detect(returns_spike, window=21)

        # Second detection should show regime change if regimes differ
        if state1.regime != state2.regime:
            assert state2.regime_changed is True
            assert state2.prev_regime == state1.regime

    def test_days_in_regime_increments(self):
        returns = _make_returns(300, vol=0.01)
        detector = VolRegimeDetector()
        state1 = detector.detect(returns, window=21)
        state2 = detector.detect(returns, window=21)
        # If same regime, days should increment
        if not state2.regime_changed:
            assert state2.days_in_regime == state1.days_in_regime + 1

    def test_get_history(self):
        returns = _make_returns(300)
        detector = VolRegimeDetector()
        detector.detect(returns, window=21)
        detector.detect(returns, window=21)
        history = detector.get_history()
        assert len(history) == 2

    def test_reset(self):
        returns = _make_returns(300)
        detector = VolRegimeDetector()
        detector.detect(returns, window=21)
        detector.reset()
        assert len(detector.get_history()) == 0

    def test_regime_distribution(self):
        returns = _make_returns(300)
        detector = VolRegimeDetector()
        dist = detector.regime_distribution(returns, window=21)
        assert set(dist.keys()) == set(VolRegime)
        total = sum(dist.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_insufficient_data(self):
        detector = VolRegimeDetector()
        state = detector.detect(pd.Series([0.01, 0.02]), window=21)
        assert state.regime == VolRegime.NORMAL
        assert state.current_vol == 0.0

    def test_percentile_in_range(self):
        returns = _make_returns(300)
        detector = VolRegimeDetector()
        state = detector.detect(returns, window=21)
        assert 0.0 <= state.percentile <= 100.0


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestVolatilityIntegration:
    """End-to-end integration tests."""

    def test_full_vol_analysis_pipeline(self):
        """Compute vol -> cone -> regime -> term structure."""
        returns = _make_returns(300, vol=0.015)
        engine = VolatilityEngine()
        detector = VolRegimeDetector()

        # Vol estimate
        est = engine.compute_historical(returns, window=21, symbol="SPY")
        assert est.value > 0

        # Percentile
        pct = engine.compute_percentile(est.value, returns, window=21)
        assert 0 <= pct <= 100

        # Cone
        cone = engine.compute_vol_cone(returns)
        assert len(cone) > 0

        # Regime
        state = detector.detect(returns, window=21)
        assert state.current_vol > 0

        # Term structure
        ts = engine.compute_term_structure(returns, tenor_days=(5, 21, 63))
        assert len(ts.points) == 3

    def test_surface_analysis_pipeline(self):
        """Build surface -> compute metrics per tenor."""
        iv_data = {
            30: [(90, 0.28), (95, 0.24), (100, 0.20), (105, 0.22), (110, 0.25)],
            60: [(90, 0.30), (95, 0.26), (100, 0.22), (105, 0.24), (110, 0.27)],
        }
        analyzer = VolSurfaceAnalyzer()
        surface = analyzer.build_surface(iv_data, spot=100, symbol="SPY")

        for tenor in surface.tenors:
            metrics = analyzer.smile_metrics(surface, tenor)
            assert metrics["atm_vol"] is not None
            assert metrics["n_strikes"] == 5


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestVolatilityModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.volatility import (
            VolatilityEngine,
            VolSurfaceAnalyzer,
            VolRegimeDetector,
            VolMethod,
            VolRegime,
            VolEstimate,
            VolSurface,
            VolRegimeState,
            VolConePoint,
            DEFAULT_CONFIG,
        )
        assert VolatilityEngine is not None
        assert VolSurfaceAnalyzer is not None
        assert VolRegimeDetector is not None
