"""Tests for PRD-55: Regime Detection."""

import numpy as np
import pytest

from src.regime.config import (
    RegimeType,
    DetectionMethod,
    ClusterMethod,
    FeatureSet,
    HMMConfig,
    ClusterConfig,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_regime_returns(seed: int = 42) -> list[float]:
    """Generate synthetic multi-regime returns."""
    rng = np.random.RandomState(seed)
    # Bull: 100 days of positive mean
    bull = rng.normal(0.001, 0.01, 100)
    # Bear: 80 days of negative mean, higher vol
    bear = rng.normal(-0.002, 0.02, 80)
    # Sideways: 100 days of near-zero
    sideways = rng.normal(0.0, 0.008, 100)
    # Crisis: 20 days of large negative
    crisis = rng.normal(-0.01, 0.04, 20)
    return list(np.concatenate([bull, bear, sideways, crisis]))


# ---------------------------------------------------------------------------
# Config enums
# ---------------------------------------------------------------------------
class TestConfig:
    def test_regime_type_values(self):
        assert RegimeType.BULL.value == "bull"
        assert RegimeType.CRISIS.value == "crisis"

    def test_detection_methods(self):
        assert DetectionMethod.HMM.value == "hmm"
        assert DetectionMethod.CLUSTERING.value == "clustering"

    def test_hmm_config_defaults(self):
        cfg = HMMConfig()
        assert cfg.n_regimes == 4
        assert cfg.n_iterations == 100

    def test_cluster_config_defaults(self):
        cfg = ClusterConfig()
        assert cfg.method == ClusterMethod.KMEANS
        assert cfg.n_clusters == 4


# ---------------------------------------------------------------------------
# RegimeState dataclass
# ---------------------------------------------------------------------------
class TestRegimeState:
    def test_defaults(self):
        s = RegimeState()
        assert s.regime == "sideways"
        assert s.confidence == 0.0

    def test_is_high_confidence(self):
        s = RegimeState(confidence=0.85)
        assert s.is_high_confidence is True
        s2 = RegimeState(confidence=0.5)
        assert s2.is_high_confidence is False

    def test_is_crisis(self):
        s = RegimeState(regime="crisis")
        assert s.is_crisis is True
        s2 = RegimeState(regime="bull")
        assert s2.is_crisis is False


class TestRegimeSegment:
    def test_auto_length(self):
        seg = RegimeSegment(regime="bull", start_idx=0, end_idx=9)
        assert seg.length == 10


class TestRegimeHistory:
    def test_current_regime(self):
        h = RegimeHistory(regimes=["bull", "bull", "bear"])
        assert h.current_regime == "bear"
        assert h.n_observations == 3

    def test_regime_changes(self):
        h = RegimeHistory(regimes=["bull", "bull", "bear", "bear", "crisis"])
        assert h.n_regime_changes == 2

    def test_empty_history(self):
        h = RegimeHistory()
        assert h.current_regime == "sideways"
        assert h.n_regime_changes == 0


class TestTransitionMatrix:
    def test_get_probability(self):
        tm = TransitionMatrix(
            states=["bull", "bear"],
            matrix=[[0.9, 0.1], [0.3, 0.7]],
        )
        assert tm.get_probability("bull", "bear") == 0.1
        assert tm.get_probability("bear", "bull") == 0.3

    def test_persistence(self):
        tm = TransitionMatrix(
            states=["bull", "bear"],
            matrix=[[0.9, 0.1], [0.3, 0.7]],
        )
        assert tm.get_persistence("bull") == 0.9

    def test_unknown_state(self):
        tm = TransitionMatrix(states=["bull"], matrix=[[1.0]])
        assert tm.get_probability("bear", "bull") == 0.0


class TestRegimeAllocation:
    def test_is_defensive(self):
        a = RegimeAllocation(regime="bear")
        assert a.is_defensive is True
        a2 = RegimeAllocation(regime="bull")
        assert a2.is_defensive is False


# ---------------------------------------------------------------------------
# GaussianHMM
# ---------------------------------------------------------------------------
class TestGaussianHMM:
    def test_detect_returns_state(self):
        returns = _generate_regime_returns()
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        state = hmm.detect(returns)
        assert state.regime in ("bull", "bear", "sideways", "crisis")
        assert 0 <= state.confidence <= 1.0
        assert state.method == "hmm"

    def test_detect_with_volatility(self):
        returns = _generate_regime_returns()
        vols = [abs(r) * 2 + 0.01 for r in returns]
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        state = hmm.detect(returns, vols)
        assert state.regime in ("bull", "bear", "sideways", "crisis")

    def test_detect_history(self):
        returns = _generate_regime_returns()
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        history = hmm.detect_history(returns)
        assert len(history.regimes) == len(returns)
        assert len(history.probabilities) == len(returns)
        assert len(history.segments) > 0
        assert history.method == "hmm"

    def test_insufficient_data(self):
        hmm = GaussianHMM(HMMConfig(min_observations=100))
        state = hmm.detect([0.01, 0.02, -0.01])
        assert state.regime == "sideways"
        assert state.confidence == 0.0

    def test_probabilities_sum_to_one(self):
        returns = _generate_regime_returns()
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        state = hmm.detect(returns)
        if state.probabilities:
            total = sum(state.probabilities.values())
            assert total == pytest.approx(1.0, abs=0.01)

    def test_predict_proba_length(self):
        returns = _generate_regime_returns()
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        obs = np.array(returns).reshape(-1, 1)
        hmm.fit(obs)
        proba = hmm.predict_proba(obs)
        assert len(proba) == len(returns)

    def test_duration_tracking(self):
        returns = _generate_regime_returns()
        hmm = GaussianHMM(HMMConfig(n_regimes=4, min_observations=30))
        state = hmm.detect(returns)
        assert state.duration >= 1


# ---------------------------------------------------------------------------
# ClusterRegimeClassifier
# ---------------------------------------------------------------------------
class TestClusterRegimeClassifier:
    def test_classify_returns_state(self):
        returns = _generate_regime_returns()
        clf = ClusterRegimeClassifier(ClusterConfig(n_clusters=4, min_observations=30))
        state = clf.classify(returns)
        assert state.regime in ("bull", "bear", "sideways", "crisis")
        assert 0 <= state.confidence <= 1.0
        assert state.method == "clustering"

    def test_classify_history(self):
        returns = _generate_regime_returns()
        clf = ClusterRegimeClassifier(ClusterConfig(n_clusters=4, min_observations=30))
        history = clf.classify_history(returns)
        assert len(history.regimes) == len(returns)
        assert history.method == "clustering"
        assert len(history.segments) > 0

    def test_agglomerative(self):
        returns = _generate_regime_returns()
        clf = ClusterRegimeClassifier(
            ClusterConfig(method=ClusterMethod.AGGLOMERATIVE, n_clusters=4, min_observations=30)
        )
        state = clf.classify(returns)
        assert state.regime in ("bull", "bear", "sideways", "crisis")

    def test_silhouette_score(self):
        returns = _generate_regime_returns()
        clf = ClusterRegimeClassifier(ClusterConfig(n_clusters=4, min_observations=30))
        clf.fit(returns)
        score = clf.silhouette_score(returns)
        assert -1.0 <= score <= 1.0

    def test_insufficient_data(self):
        clf = ClusterRegimeClassifier(ClusterConfig(min_observations=100))
        state = clf.classify([0.01, 0.02])
        assert state.regime == "sideways"

    def test_probabilities_sum_to_one(self):
        returns = _generate_regime_returns()
        clf = ClusterRegimeClassifier(ClusterConfig(n_clusters=4, min_observations=30))
        state = clf.classify(returns)
        if state.probabilities:
            total = sum(state.probabilities.values())
            assert total == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# RegimeTransitionAnalyzer
# ---------------------------------------------------------------------------
class TestRegimeTransitionAnalyzer:
    def test_transition_matrix(self):
        regimes = ["bull", "bull", "bear", "bear", "bull", "sideways", "sideways"]
        analyzer = RegimeTransitionAnalyzer()
        tm = analyzer.compute_transition_matrix(regimes)
        assert len(tm.states) > 0
        # Each row should sum to ~1.0
        for row in tm.matrix:
            assert sum(row) == pytest.approx(1.0, abs=0.01)

    def test_expected_durations(self):
        regimes = ["bull"] * 20 + ["bear"] * 10 + ["bull"] * 15
        analyzer = RegimeTransitionAnalyzer()
        tm = analyzer.compute_transition_matrix(regimes)
        assert "bull" in tm.expected_durations
        assert tm.expected_durations["bull"] > 1.0

    def test_regime_stats(self):
        regimes = ["bull"] * 50 + ["bear"] * 30 + ["sideways"] * 20
        returns = list(np.random.RandomState(42).normal(0.001, 0.01, 100))
        analyzer = RegimeTransitionAnalyzer()
        stats = analyzer.regime_stats(regimes, returns)
        assert len(stats) == 3
        names = {s.regime for s in stats}
        assert "bull" in names
        assert "bear" in names

    def test_regime_stats_frequency(self):
        regimes = ["bull"] * 60 + ["bear"] * 40
        returns = list(np.random.RandomState(42).normal(0, 0.01, 100))
        analyzer = RegimeTransitionAnalyzer()
        stats = analyzer.regime_stats(regimes, returns)
        bull_stat = [s for s in stats if s.regime == "bull"][0]
        assert bull_stat.frequency == pytest.approx(0.6)

    def test_detect_changes(self):
        regimes = ["bull", "bull", "bear", "bear", "crisis"]
        analyzer = RegimeTransitionAnalyzer()
        changes = analyzer.detect_changes(regimes)
        assert changes == [2, 4]

    def test_forecast_regime(self):
        regimes = ["bull"] * 50 + ["bear"] * 30 + ["bull"] * 20
        analyzer = RegimeTransitionAnalyzer()
        tm = analyzer.compute_transition_matrix(regimes)
        forecast = analyzer.forecast_regime("bull", tm, horizon=5)
        assert len(forecast) == 5
        for step in forecast:
            total = sum(step.values())
            assert total == pytest.approx(1.0, abs=0.01)

    def test_forecast_unknown_regime(self):
        regimes = ["bull", "bear"]
        analyzer = RegimeTransitionAnalyzer()
        tm = analyzer.compute_transition_matrix(regimes)
        forecast = analyzer.forecast_regime("crisis", tm, horizon=3)
        assert len(forecast) == 3


# ---------------------------------------------------------------------------
# RegimeAllocator
# ---------------------------------------------------------------------------
class TestRegimeAllocator:
    def test_allocate_bull(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("bull", confidence=0.9)
        assert alloc.regime == "bull"
        assert alloc.weights["equity"] > alloc.weights["bonds"]
        assert alloc.is_defensive is False

    def test_allocate_crisis(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("crisis", confidence=0.8)
        assert alloc.weights["cash"] > alloc.weights["equity"]
        assert alloc.is_defensive is True

    def test_blended_weights(self):
        allocator = RegimeAllocator()
        probs = {"bull": 0.6, "sideways": 0.3, "bear": 0.1, "crisis": 0.0}
        alloc = allocator.allocate("bull", confidence=0.6, regime_probabilities=probs)
        # Blended should reflect majority bull
        assert alloc.blended_weights["equity"] > alloc.blended_weights["bonds"]
        total = sum(alloc.blended_weights.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_recommend_shift(self):
        allocator = RegimeAllocator()
        current = {"equity": 0.70, "bonds": 0.15, "commodities": 0.10, "cash": 0.05}
        shifts = allocator.recommend_shift(current, "crisis")
        # Should recommend selling equity, buying cash
        assert shifts.get("equity", 0) < 0
        assert shifts.get("cash", 0) > 0

    def test_regime_signal(self):
        allocator = RegimeAllocator()
        signals = allocator.regime_signal("crisis", previous_regime="bull")
        assert signals["equity"] == "sell"
        assert signals["cash"] == "buy"

    def test_regime_signal_same_regime(self):
        allocator = RegimeAllocator()
        signals = allocator.regime_signal("bull", previous_regime="bull")
        for signal in signals.values():
            assert signal == "hold"

    def test_allocation_weights_normalize(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("sideways")
        total = sum(alloc.blended_weights.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_expected_return_risk(self):
        allocator = RegimeAllocator()
        alloc = allocator.allocate("bull")
        assert alloc.expected_return > 0
        assert alloc.expected_risk > 0
        alloc_bear = allocator.allocate("bear")
        assert alloc_bear.expected_return < 0
