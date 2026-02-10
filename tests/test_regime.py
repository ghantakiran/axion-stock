"""Tests for src/regime/ module — RegimeDetector, GaussianHMM, RegimeEnsemble,
RegimeAllocator, ClusterRegimeClassifier, RegimeTransitionAnalyzer,
RegimeSignalAdapter, DynamicThresholdManager, and RegimeSignalGenerator.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, date, timedelta

from src.regime.detector import (
    MarketRegime,
    RegimeDetector,
    RegimeFeatures,
    RegimeClassification,
)
from src.regime.config import (
    RegimeType,
    HMMConfig,
    ClusterConfig,
    ClusterMethod,
    TransitionConfig,
    AllocationConfig,
)
from src.regime.models import (
    RegimeState,
    RegimeSegment,
    RegimeHistory,
    TransitionMatrix,
    RegimeStats,
    RegimeAllocation,
)
from src.regime.hmm import GaussianHMM
from src.regime.clustering import ClusterRegimeClassifier
from src.regime.transitions import RegimeTransitionAnalyzer
from src.regime.allocation import RegimeAllocator
from src.regime.ensemble import (
    MethodResult,
    EnsembleResult,
    EnsembleComparison,
    RegimeEnsemble,
)
from src.regime.signal_adapter import (
    RawSignal,
    AdaptedSignal,
    AdaptedSignalSet,
    RegimeSignalAdapter,
)
from src.regime.threshold_manager import (
    ThresholdSet,
    ThresholdComparison,
    SignalDecision,
    DynamicThresholdManager,
)
from src.regime.regime_signals import (
    TransitionSignal,
    PersistenceSignal,
    AlignmentSignal,
    DivergenceSignal,
    RegimeSignalSummary,
    RegimeSignalGenerator,
)
from src.regime.weights import AdaptiveWeights, REGIME_WEIGHTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_regime_returns(seed: int = 42) -> list[float]:
    """Generate synthetic multi-regime returns (300 obs)."""
    rng = np.random.RandomState(seed)
    bull = rng.normal(0.001, 0.01, 100)
    bear = rng.normal(-0.002, 0.02, 80)
    sideways = rng.normal(0.0, 0.008, 100)
    crisis = rng.normal(-0.01, 0.04, 20)
    return list(np.concatenate([bull, bear, sideways, crisis]))


def _build_market_prices(n_days: int = 300, seed: int = 42) -> pd.DataFrame:
    """Build a synthetic SPY-like price DataFrame."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(end=date.today(), periods=n_days)
    returns = rng.normal(0.0005, 0.012, n_days)
    prices = 100 * np.cumprod(1 + returns)
    return pd.DataFrame({"SPY": prices}, index=dates)


# ---------------------------------------------------------------------------
# TestRegimeDetector
# ---------------------------------------------------------------------------
class TestRegimeDetector:
    def test_init_creates_empty_cache(self):
        detector = RegimeDetector()
        assert detector._cache == {}

    def test_classify_with_insufficient_data(self):
        detector = RegimeDetector()
        df = pd.DataFrame({"SPY": [100.0, 101.0]}, index=pd.bdate_range("2024-01-01", periods=2))
        result = detector.classify(df)
        assert result.regime == MarketRegime.SIDEWAYS
        assert result.confidence == 0.0

    def test_classify_with_empty_dataframe(self):
        detector = RegimeDetector()
        result = detector.classify(pd.DataFrame())
        assert result.regime == MarketRegime.SIDEWAYS

    def test_classify_returns_valid_regime(self):
        detector = RegimeDetector()
        df = _build_market_prices(250)
        result = detector.classify(df)
        assert result.regime in list(MarketRegime)
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_caches_result(self):
        detector = RegimeDetector()
        df = _build_market_prices(250)
        r1 = detector.classify(df)
        r2 = detector.classify(df)
        assert r1.regime == r2.regime

    def test_classify_crisis_when_vix_high(self):
        detector = RegimeDetector()
        df = _build_market_prices(250)
        dates = df.index
        vix = pd.Series(40.0, index=dates)
        result = detector.classify(df, vix_data=vix)
        assert result.regime == MarketRegime.CRISIS

    def test_classify_from_features_bull(self):
        detector = RegimeDetector()
        features = RegimeFeatures(
            sp500_above_200sma=True,
            sp500_trend_strength=0.08,
            vix_level=12.0,
            vix_20d_change=-2.0,
            breadth_ratio=0.65,
            momentum_1m=0.04,
        )
        regime, conf = detector._classify_from_features(features)
        assert regime == MarketRegime.BULL
        assert conf > 0.5

    def test_classify_from_features_bear(self):
        detector = RegimeDetector()
        features = RegimeFeatures(
            sp500_above_200sma=False,
            sp500_trend_strength=-0.08,
            vix_level=30.0,
            vix_20d_change=5.0,
            breadth_ratio=0.35,
            momentum_1m=-0.05,
        )
        regime, conf = detector._classify_from_features(features)
        assert regime == MarketRegime.BEAR

    def test_classify_from_features_sideways(self):
        detector = RegimeDetector()
        features = RegimeFeatures(
            sp500_above_200sma=True,
            sp500_trend_strength=0.01,
            vix_level=18.0,
            vix_20d_change=0.0,
            breadth_ratio=0.50,
            momentum_1m=0.01,
        )
        regime, conf = detector._classify_from_features(features)
        assert regime == MarketRegime.SIDEWAYS

    def test_get_regime_summary(self):
        detector = RegimeDetector()
        features = RegimeFeatures(
            sp500_above_200sma=True,
            sp500_trend_strength=0.05,
            vix_level=15.0,
            vix_20d_change=-1.0,
            breadth_ratio=0.60,
        )
        classification = RegimeClassification(
            regime=MarketRegime.BULL,
            confidence=0.8,
            features=features,
            timestamp=datetime.now(),
        )
        summary = detector.get_regime_summary(classification)
        assert "BULL" in summary
        assert "80%" in summary

    def test_classification_str(self):
        features = RegimeFeatures(
            sp500_above_200sma=True,
            sp500_trend_strength=0.0,
            vix_level=20.0,
            vix_20d_change=0.0,
            breadth_ratio=0.5,
        )
        c = RegimeClassification(
            regime=MarketRegime.BULL,
            confidence=0.85,
            features=features,
            timestamp=datetime.now(),
        )
        assert "BULL" in str(c)


# ---------------------------------------------------------------------------
# TestGaussianHMM
# ---------------------------------------------------------------------------
class TestGaussianHMM:
    def test_init_default_config(self):
        hmm = GaussianHMM()
        assert hmm.n == 4
        assert not hmm._fitted

    def test_init_custom_config(self):
        cfg = HMMConfig(n_regimes=3, n_iterations=50)
        hmm = GaussianHMM(config=cfg)
        assert hmm.n == 3

    def test_fit_returns_self(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        obs = np.array(returns).reshape(-1, 1)
        result = hmm.fit(obs)
        assert result is hmm
        assert hmm._fitted

    def test_fit_insufficient_data(self):
        hmm = GaussianHMM()
        obs = np.array([0.01, -0.01]).reshape(-1, 1)
        hmm.fit(obs)
        assert not hmm._fitted

    def test_predict_before_fit_returns_sideways(self):
        hmm = GaussianHMM()
        obs = np.array([0.01, -0.01, 0.005]).reshape(-1, 1)
        labels = hmm.predict(obs)
        assert all(l == "sideways" for l in labels)

    def test_predict_after_fit(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        obs = np.array(returns).reshape(-1, 1)
        hmm.fit(obs)
        labels = hmm.predict(obs)
        assert len(labels) == len(returns)
        valid_regimes = {"bull", "bear", "sideways", "crisis"}
        assert all(l in valid_regimes for l in labels)

    def test_predict_proba_before_fit(self):
        hmm = GaussianHMM()
        obs = np.array([0.01, -0.01, 0.005]).reshape(-1, 1)
        proba = hmm.predict_proba(obs)
        assert len(proba) == 3
        assert all(isinstance(p, dict) for p in proba)

    def test_predict_proba_sums_to_one(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        obs = np.array(returns).reshape(-1, 1)
        hmm.fit(obs)
        proba = hmm.predict_proba(obs)
        for p in proba:
            total = sum(p.values())
            assert abs(total - 1.0) < 0.05

    def test_detect_returns_regime_state(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        state = hmm.detect(returns)
        assert isinstance(state, RegimeState)
        assert state.method == "hmm"
        assert state.duration >= 1

    def test_detect_empty_returns(self):
        hmm = GaussianHMM()
        state = hmm.detect([])
        assert state.regime == "sideways"
        assert state.confidence == 0.0

    def test_detect_with_volatilities(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        vols = [abs(r) * 10 + 0.1 for r in returns]
        state = hmm.detect(returns, volatilities=vols)
        assert isinstance(state, RegimeState)

    def test_detect_history(self):
        hmm = GaussianHMM()
        returns = _generate_regime_returns()
        history = hmm.detect_history(returns)
        assert isinstance(history, RegimeHistory)
        assert history.method == "hmm"
        assert len(history.regimes) == len(returns)
        assert len(history.segments) >= 1

    def test_detect_history_empty(self):
        hmm = GaussianHMM()
        history = hmm.detect_history([])
        assert history.n_observations == 0


# ---------------------------------------------------------------------------
# TestClusterRegimeClassifier
# ---------------------------------------------------------------------------
class TestClusterRegimeClassifier:
    def test_init_default_config(self):
        clf = ClusterRegimeClassifier()
        assert not clf._fitted

    def test_fit_returns_self(self):
        clf = ClusterRegimeClassifier()
        returns = _generate_regime_returns()
        result = clf.fit(returns)
        assert result is clf
        assert clf._fitted

    def test_fit_insufficient_data(self):
        clf = ClusterRegimeClassifier()
        clf.fit([0.01, -0.01])
        assert not clf._fitted

    def test_classify_returns_regime_state(self):
        clf = ClusterRegimeClassifier()
        returns = _generate_regime_returns()
        state = clf.classify(returns)
        assert isinstance(state, RegimeState)
        assert state.method == "clustering"

    def test_classify_history(self):
        clf = ClusterRegimeClassifier()
        returns = _generate_regime_returns()
        history = clf.classify_history(returns)
        assert isinstance(history, RegimeHistory)
        assert history.method == "clustering"
        assert len(history.regimes) == len(returns)

    def test_agglomerative_method(self):
        cfg = ClusterConfig(method=ClusterMethod.AGGLOMERATIVE)
        clf = ClusterRegimeClassifier(config=cfg)
        returns = _generate_regime_returns()
        state = clf.classify(returns)
        assert isinstance(state, RegimeState)

    def test_silhouette_score_unfitted(self):
        clf = ClusterRegimeClassifier()
        score = clf.silhouette_score([0.01, -0.01])
        assert score == 0.0

    def test_silhouette_score_fitted(self):
        clf = ClusterRegimeClassifier()
        returns = _generate_regime_returns()
        clf.fit(returns)
        score = clf.silhouette_score(returns)
        assert -1.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# TestRegimeTransitionAnalyzer
# ---------------------------------------------------------------------------
class TestRegimeTransitionAnalyzer:
    def test_init_default_config(self):
        analyzer = RegimeTransitionAnalyzer()
        assert analyzer.config.min_regime_length == 5

    def test_compute_transition_matrix(self):
        analyzer = RegimeTransitionAnalyzer()
        regimes = ["bull"] * 50 + ["bear"] * 30 + ["sideways"] * 20
        tm = analyzer.compute_transition_matrix(regimes)
        assert isinstance(tm, TransitionMatrix)
        assert len(tm.states) >= 2
        for row in tm.matrix:
            assert abs(sum(row) - 1.0) < 0.01

    def test_transition_matrix_expected_durations(self):
        analyzer = RegimeTransitionAnalyzer()
        regimes = ["bull"] * 50 + ["bear"] * 30 + ["bull"] * 20
        tm = analyzer.compute_transition_matrix(regimes)
        assert "bull" in tm.expected_durations
        assert tm.expected_durations["bull"] > 0

    def test_get_persistence(self):
        tm = TransitionMatrix(
            states=["bull", "bear"],
            matrix=[[0.9, 0.1], [0.2, 0.8]],
            counts=[[45, 5], [6, 24]],
            expected_durations={"bull": 10.0, "bear": 5.0},
        )
        assert tm.get_persistence("bull") == 0.9
        assert tm.get_persistence("bear") == 0.8

    def test_get_probability_unknown_state(self):
        tm = TransitionMatrix(
            states=["bull", "bear"],
            matrix=[[0.9, 0.1], [0.2, 0.8]],
            counts=[[45, 5], [6, 24]],
        )
        assert tm.get_probability("unknown", "bull") == 0.0

    def test_regime_stats(self):
        analyzer = RegimeTransitionAnalyzer()
        regimes = ["bull"] * 50 + ["bear"] * 30
        rng = np.random.RandomState(42)
        returns = list(rng.normal(0.001, 0.01, 50)) + list(rng.normal(-0.002, 0.02, 30))
        stats = analyzer.regime_stats(regimes, returns)
        assert len(stats) == 2
        bull_stat = [s for s in stats if s.regime == "bull"][0]
        assert bull_stat.count == 50
        assert bull_stat.frequency > 0.5

    def test_detect_changes(self):
        analyzer = RegimeTransitionAnalyzer()
        regimes = ["bull", "bull", "bear", "bear", "bull"]
        changes = analyzer.detect_changes(regimes)
        assert changes == [2, 4]

    def test_forecast_regime(self):
        analyzer = RegimeTransitionAnalyzer()
        regimes = ["bull"] * 50 + ["bear"] * 30 + ["sideways"] * 20
        tm = analyzer.compute_transition_matrix(regimes)
        forecast = analyzer.forecast_regime("bull", tm, horizon=5)
        assert len(forecast) == 5
        for step in forecast:
            assert abs(sum(step.values()) - 1.0) < 0.05

    def test_forecast_unknown_regime(self):
        analyzer = RegimeTransitionAnalyzer()
        tm = TransitionMatrix(
            states=["bull", "bear"],
            matrix=[[0.9, 0.1], [0.2, 0.8]],
            counts=[[45, 5], [6, 24]],
        )
        forecast = analyzer.forecast_regime("unknown", tm, horizon=3)
        assert len(forecast) == 3


# ---------------------------------------------------------------------------
# TestRegimeAllocator
# ---------------------------------------------------------------------------
class TestRegimeAllocator:
    def test_init_default(self):
        allocator = RegimeAllocator()
        assert allocator.config.blend_with_probabilities is True

    def test_allocate_bull(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("bull", confidence=0.8)
        assert isinstance(alloc, RegimeAllocation)
        assert alloc.regime == "bull"
        assert alloc.confidence == 0.8
        assert "equity" in alloc.weights

    def test_allocate_crisis(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("crisis")
        assert alloc.weights["cash"] > alloc.weights["equity"]

    def test_allocate_with_probabilities(self):
        allocator = RegimeAllocator()
        probs = {"bull": 0.6, "bear": 0.1, "sideways": 0.2, "crisis": 0.1}
        alloc = allocator.allocate("bull", regime_probabilities=probs)
        assert sum(alloc.blended_weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_recommend_shift(self):
        allocator = RegimeAllocator()
        current = {"equity": 0.6, "bonds": 0.2, "commodities": 0.1, "cash": 0.1}
        shifts = allocator.recommend_shift(current, "bear")
        assert "equity" in shifts or len(shifts) > 0

    def test_regime_signal_bull_to_bear(self):
        allocator = RegimeAllocator()
        signals = allocator.regime_signal("bear", previous_regime="bull")
        assert "equity" in signals
        assert signals["equity"] == "sell"

    def test_regime_signal_no_previous(self):
        allocator = RegimeAllocator()
        signals = allocator.regime_signal("bull")
        assert all(v == "hold" for v in signals.values())

    def test_allocation_is_defensive(self):
        alloc = RegimeAllocation(regime="crisis", confidence=0.9)
        assert alloc.is_defensive is True
        alloc2 = RegimeAllocation(regime="bull", confidence=0.9)
        assert alloc2.is_defensive is False

    def test_smoothing_between_allocations(self):
        allocator = RegimeAllocator()
        a1 = allocator.allocate("bull")
        a2 = allocator.allocate("crisis")
        # Second allocation should be smoothed (not pure crisis weights)
        assert a2.blended_weights["equity"] > 0.0


# ---------------------------------------------------------------------------
# TestRegimeEnsemble
# ---------------------------------------------------------------------------
class TestRegimeEnsemble:
    def test_init_default_weights(self):
        ensemble = RegimeEnsemble()
        assert "hmm" in ensemble.method_weights

    def test_combine_empty(self):
        ensemble = RegimeEnsemble()
        result = ensemble.combine([])
        assert result.consensus_regime == ""

    def test_combine_unanimous(self):
        ensemble = RegimeEnsemble()
        results = [
            MethodResult(method="hmm", regime="bull", confidence=0.8,
                         probabilities={"bull": 0.8, "bear": 0.1, "sideways": 0.1}, weight=0.4),
            MethodResult(method="clustering", regime="bull", confidence=0.7,
                         probabilities={"bull": 0.7, "bear": 0.15, "sideways": 0.15}, weight=0.3),
        ]
        combined = ensemble.combine(results)
        assert combined.consensus_regime == "bull"
        assert combined.is_unanimous is True
        assert combined.agreement_ratio == 1.0

    def test_combine_disagreement(self):
        ensemble = RegimeEnsemble()
        results = [
            MethodResult(method="hmm", regime="bull", confidence=0.8,
                         probabilities={"bull": 0.8, "bear": 0.2}, weight=0.5),
            MethodResult(method="clustering", regime="bear", confidence=0.6,
                         probabilities={"bull": 0.3, "bear": 0.7}, weight=0.5),
        ]
        combined = ensemble.combine(results)
        assert combined.is_unanimous is False
        assert combined.agreement_ratio == 0.5

    def test_combine_from_states(self):
        ensemble = RegimeEnsemble()
        states = {
            "hmm": RegimeState(regime="bull", confidence=0.8, probabilities={"bull": 0.8, "bear": 0.2}),
            "clustering": RegimeState(regime="bull", confidence=0.7, probabilities={"bull": 0.7, "bear": 0.3}),
        }
        result = ensemble.combine_from_states(states)
        assert result.consensus_regime == "bull"

    def test_compare_methods(self):
        ensemble = RegimeEnsemble()
        results = [
            MethodResult(method="hmm", regime="bull", confidence=0.8,
                         probabilities={"bull": 0.8, "bear": 0.2}, weight=0.4),
            MethodResult(method="clustering", regime="bear", confidence=0.6,
                         probabilities={"bull": 0.3, "bear": 0.7}, weight=0.3),
        ]
        comparison = ensemble.compare_methods(results)
        assert isinstance(comparison, EnsembleComparison)
        assert comparison.has_divergence is True
        assert comparison.confidence_spread > 0

    def test_weighted_regime_state(self):
        ensemble = RegimeEnsemble()
        results = [
            MethodResult(method="hmm", regime="bull", confidence=0.9,
                         probabilities={"bull": 0.9, "bear": 0.1}, weight=0.5),
        ]
        state = ensemble.weighted_regime_state(results)
        assert isinstance(state, RegimeState)
        assert state.method == "ensemble"

    def test_ensemble_result_properties(self):
        r = EnsembleResult(
            consensus_regime="bull",
            consensus_confidence=0.8,
            agreement_ratio=0.75,
            method_results=[
                MethodResult(method="hmm", regime="bull", confidence=0.8, weight=0.5),
            ],
        )
        assert r.is_high_confidence is True
        assert r.has_strong_agreement is True
        assert r.dominant_method == "hmm"

    def test_method_result_weighted_confidence(self):
        mr = MethodResult(method="hmm", regime="bull", confidence=0.8, weight=0.5)
        assert mr.weighted_confidence == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# TestRegimeSignalAdapter
# ---------------------------------------------------------------------------
class TestRegimeSignalAdapter:
    def test_init_defaults(self):
        adapter = RegimeSignalAdapter()
        assert "bull" in adapter.signal_weights

    def test_adapt_signal_bull_momentum(self):
        adapter = RegimeSignalAdapter()
        raw = RawSignal(name="mom", category="momentum", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(raw, "bull", regime_confidence=1.0)
        assert adapted.adapted_score > raw.raw_score  # Momentum amplified in bull
        assert adapted.is_amplified is True

    def test_adapt_signal_crisis_momentum(self):
        adapter = RegimeSignalAdapter()
        raw = RawSignal(name="mom", category="momentum", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(raw, "crisis", regime_confidence=1.0)
        assert adapted.adapted_score < raw.raw_score  # Momentum suppressed in crisis
        assert adapted.is_suppressed is True

    def test_adapt_signal_low_regime_confidence(self):
        adapter = RegimeSignalAdapter()
        raw = RawSignal(name="qual", category="quality", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(raw, "crisis", regime_confidence=0.0)
        # With zero regime confidence, multiplier blends to 1.0
        assert abs(adapted.adapted_score - raw.raw_score) < 0.01

    def test_adapt_signals_collection(self):
        adapter = RegimeSignalAdapter()
        signals = [
            RawSignal(name="mom", category="momentum", raw_score=0.6, confidence=0.7),
            RawSignal(name="val", category="value", raw_score=0.4, confidence=0.6),
        ]
        result = adapter.adapt_signals(signals, "bull", regime_confidence=0.9)
        assert isinstance(result, AdaptedSignalSet)
        assert len(result.signals) == 2
        assert result.n_amplified + result.n_suppressed + result.n_unchanged == 2

    def test_adapted_signal_set_net_direction(self):
        s = AdaptedSignalSet(composite_score=0.5)
        assert s.net_direction == "bullish"
        s2 = AdaptedSignalSet(composite_score=-0.5)
        assert s2.net_direction == "bearish"
        s3 = AdaptedSignalSet(composite_score=0.0)
        assert s3.net_direction == "neutral"

    def test_get_regime_weights(self):
        adapter = RegimeSignalAdapter()
        weights = adapter.get_regime_weights("bull")
        assert "momentum" in weights
        assert weights["momentum"] > 1.0  # Momentum amplified in bull

    def test_compare_regimes(self):
        adapter = RegimeSignalAdapter()
        signals = [
            RawSignal(name="mom", category="momentum", raw_score=0.5, confidence=0.7),
        ]
        comparison = adapter.compare_regimes(signals)
        assert "bull" in comparison
        assert "crisis" in comparison
        assert len(comparison) == 4

    def test_raw_signal_properties(self):
        bullish = RawSignal(raw_score=0.5)
        assert bullish.is_bullish is True
        assert bullish.is_bearish is False
        bearish = RawSignal(raw_score=-0.5)
        assert bearish.is_bearish is True

    def test_adapted_signal_adjustment_pct(self):
        adapted = AdaptedSignal(raw_score=0.5, adapted_score=0.7)
        assert adapted.adjustment_pct == pytest.approx(0.4)

    def test_adapted_signal_zero_raw(self):
        adapted = AdaptedSignal(raw_score=0.0, adapted_score=0.0)
        assert adapted.adjustment_pct == 0.0


# ---------------------------------------------------------------------------
# TestDynamicThresholdManager
# ---------------------------------------------------------------------------
class TestDynamicThresholdManager:
    def test_init_defaults(self):
        mgr = DynamicThresholdManager()
        assert "bull" in mgr.thresholds

    def test_get_thresholds_bull(self):
        mgr = DynamicThresholdManager()
        ts = mgr.get_thresholds("bull")
        assert ts.entry_threshold == 0.3
        assert ts.position_size_scalar == 1.2

    def test_get_thresholds_crisis(self):
        mgr = DynamicThresholdManager()
        ts = mgr.get_thresholds("crisis")
        assert ts.min_confidence == 0.85
        assert ts.stop_loss_pct == 0.02

    def test_get_thresholds_unknown_falls_back(self):
        mgr = DynamicThresholdManager()
        ts = mgr.get_thresholds("unknown")
        assert ts is not None

    def test_evaluate_signal_enter(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal("test_sig", 0.5, 0.7, "bull")
        assert decision.action == "enter"
        assert decision.position_size > 0

    def test_evaluate_signal_hold_low_confidence(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal("test_sig", 0.5, 0.3, "bull")
        assert decision.action == "hold"
        assert decision.position_size == 0.0

    def test_evaluate_signal_exit(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal("test_sig", -0.5, 0.5, "bull", current_position=True)
        assert decision.action == "exit"

    def test_evaluate_signal_hold_in_position(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal("test_sig", 0.0, 0.5, "bull", current_position=True)
        assert decision.action == "hold"

    def test_compare_thresholds(self):
        mgr = DynamicThresholdManager()
        comparison = mgr.compare_thresholds("bull")
        assert isinstance(comparison, ThresholdComparison)
        assert comparison.current_regime == "bull"
        assert comparison.tightest_stop != ""

    def test_interpolate_thresholds(self):
        mgr = DynamicThresholdManager()
        probs = {"bull": 0.5, "bear": 0.3, "crisis": 0.2}
        blended = mgr.interpolate_thresholds(probs)
        assert "blended" in blended.regime
        assert 0.0 < blended.entry_threshold < 1.0

    def test_threshold_set_risk_reward_ratio(self):
        ts = ThresholdSet(stop_loss_pct=0.05, take_profit_pct=0.15)
        assert ts.risk_reward_ratio == pytest.approx(3.0)

    def test_threshold_set_conservative(self):
        ts = ThresholdSet(min_confidence=0.8, stop_loss_pct=0.02)
        assert ts.is_conservative is True
        ts2 = ThresholdSet(min_confidence=0.5, stop_loss_pct=0.07)
        assert ts2.is_conservative is False

    def test_signal_decision_is_actionable(self):
        d1 = SignalDecision(action="enter")
        assert d1.is_actionable is True
        d2 = SignalDecision(action="hold")
        assert d2.is_actionable is False


# ---------------------------------------------------------------------------
# TestRegimeSignalGenerator
# ---------------------------------------------------------------------------
class TestRegimeSignalGenerator:
    def test_init_default_durations(self):
        gen = RegimeSignalGenerator()
        assert gen.expected_durations["bull"] == 80.0

    def test_transition_signal_risk_on(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("crisis", "bull", confidence=0.8)
        assert sig.signal_type == "risk_on"
        assert sig.strength > 0
        assert sig.is_risk_on is True

    def test_transition_signal_risk_off(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("bull", "crisis", confidence=0.8)
        assert sig.signal_type == "risk_off"
        assert sig.is_risk_off is True

    def test_transition_signal_same_regime(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("bull", "bull", confidence=0.8)
        assert sig.signal_type == "neutral"

    def test_persistence_signal_extended(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=150)
        assert sig.signal == "extended"
        assert sig.is_extended is True

    def test_persistence_signal_early(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=5)
        assert sig.signal == "early"
        assert sig.is_early is True

    def test_persistence_signal_normal(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=50)
        assert sig.signal == "normal"

    def test_alignment_signal_bull_positive_momentum(self):
        gen = RegimeSignalGenerator()
        sig = gen.alignment_signal("bull", momentum_score=0.5)
        assert sig.is_aligned is True
        assert sig.recommendation == "lean_in"

    def test_alignment_signal_bull_negative_momentum(self):
        gen = RegimeSignalGenerator()
        sig = gen.alignment_signal("bull", momentum_score=-0.5)
        assert sig.is_aligned is False
        assert sig.is_contrarian is True

    def test_alignment_signal_sideways(self):
        gen = RegimeSignalGenerator()
        sig = gen.alignment_signal("sideways", momentum_score=0.05)
        assert sig.is_aligned is True

    def test_divergence_signal_full_agreement(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({"hmm": "bull", "cluster": "bull", "rule": "bull"})
        assert sig.signal == "stable"
        assert sig.divergence_score == 0.0

    def test_divergence_signal_transition_warning(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({"hmm": "bull", "cluster": "bear"})
        assert sig.signal == "transition_warning"
        assert sig.is_warning is True

    def test_divergence_signal_empty(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({})
        assert sig.primary_regime == ""

    def test_generate_summary_with_transition(self):
        gen = RegimeSignalGenerator()
        summary = gen.generate_summary(
            current_regime="bear",
            previous_regime="bull",
            duration=10,
            momentum_score=-0.3,
            method_regimes={"hmm": "bear", "cluster": "bear"},
            regime_confidence=0.8,
        )
        assert isinstance(summary, RegimeSignalSummary)
        assert summary.transition_signal is not None
        assert summary.transition_signal.signal_type == "risk_off"
        assert summary.overall_bias == "bearish"

    def test_generate_summary_no_transition(self):
        gen = RegimeSignalGenerator()
        summary = gen.generate_summary(
            current_regime="bull",
            duration=50,
            momentum_score=0.3,
        )
        assert summary.transition_signal is None
        assert summary.persistence_signal is not None
        assert summary.divergence_signal is None

    def test_summary_has_actionable_signal(self):
        s = RegimeSignalSummary(
            transition_signal=TransitionSignal(strength=0.9, signal_type="risk_on"),
        )
        assert s.has_actionable_signal is True

    def test_summary_no_actionable_signal(self):
        s = RegimeSignalSummary()
        assert s.has_actionable_signal is False


# ---------------------------------------------------------------------------
# TestAdaptiveWeights
# ---------------------------------------------------------------------------
class TestAdaptiveWeights:
    def test_init_defaults(self):
        aw = AdaptiveWeights()
        assert aw.use_momentum_overlay is True

    def test_get_weights_bull(self):
        aw = AdaptiveWeights(use_momentum_overlay=False)
        weights = aw.get_weights(MarketRegime.BULL)
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert weights["momentum"] > weights["value"]

    def test_get_weights_crisis(self):
        aw = AdaptiveWeights(use_momentum_overlay=False)
        weights = aw.get_weights(MarketRegime.CRISIS)
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert weights["volatility"] >= weights["momentum"]

    def test_get_static_weights(self):
        aw = AdaptiveWeights()
        static = aw.get_static_weights()
        assert abs(sum(static.values()) - 1.0) < 0.01

    def test_regime_weights_sum_to_one(self):
        for regime, weights in REGIME_WEIGHTS.items():
            assert abs(sum(weights.values()) - 1.0) < 0.01, f"{regime} weights don't sum to 1"

    def test_explain_weights(self):
        aw = AdaptiveWeights(use_momentum_overlay=False)
        weights = aw.get_weights(MarketRegime.BULL)
        explanation = aw.explain_weights(MarketRegime.BULL, weights)
        assert "BULL" in explanation
        assert "momentum" in explanation


# ---------------------------------------------------------------------------
# TestRegimeModels
# ---------------------------------------------------------------------------
class TestRegimeModels:
    def test_regime_segment_post_init(self):
        seg = RegimeSegment(regime="bull", start_idx=0, end_idx=9)
        assert seg.length == 10

    def test_regime_history_properties(self):
        h = RegimeHistory(regimes=["bull", "bull", "bear"])
        assert h.n_observations == 3
        assert h.current_regime == "bear"
        assert h.n_regime_changes == 1

    def test_regime_history_empty(self):
        h = RegimeHistory()
        assert h.n_observations == 0
        assert h.current_regime == "sideways"
        assert h.n_regime_changes == 0

    def test_regime_state_properties(self):
        s = RegimeState(regime="crisis", confidence=0.9)
        assert s.is_crisis is True
        assert s.is_high_confidence is True
        s2 = RegimeState(regime="bull", confidence=0.5)
        assert s2.is_crisis is False
        assert s2.is_high_confidence is False
