"""Tests for PRD-61: Regime-Aware Signals."""

import pytest

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
from src.regime.ensemble import (
    MethodResult,
    EnsembleResult,
    EnsembleComparison,
    RegimeEnsemble,
)
from src.regime.regime_signals import (
    TransitionSignal,
    PersistenceSignal,
    AlignmentSignal,
    DivergenceSignal,
    RegimeSignalSummary,
    RegimeSignalGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _signals():
    return [
        RawSignal(name="RSI", category="momentum", raw_score=0.6, confidence=0.7),
        RawSignal(name="PE", category="value", raw_score=0.4, confidence=0.8),
        RawSignal(name="ROE", category="quality", raw_score=0.5, confidence=0.9),
    ]


def _method_results():
    return [
        MethodResult(
            method="hmm", regime="bull", confidence=0.8,
            probabilities={"bull": 0.7, "sideways": 0.2, "bear": 0.08, "crisis": 0.02},
            weight=0.4,
        ),
        MethodResult(
            method="clustering", regime="bull", confidence=0.6,
            probabilities={"bull": 0.55, "sideways": 0.3, "bear": 0.1, "crisis": 0.05},
            weight=0.3,
        ),
        MethodResult(
            method="rule_based", regime="sideways", confidence=0.7,
            probabilities={"bull": 0.3, "sideways": 0.5, "bear": 0.15, "crisis": 0.05},
            weight=0.3,
        ),
    ]


# ---------------------------------------------------------------------------
# RawSignal / AdaptedSignal
# ---------------------------------------------------------------------------
class TestRawSignal:
    def test_is_bullish(self):
        assert RawSignal(raw_score=0.5).is_bullish is True
        assert RawSignal(raw_score=-0.5).is_bullish is False

    def test_is_bearish(self):
        assert RawSignal(raw_score=-0.5).is_bearish is True
        assert RawSignal(raw_score=0.5).is_bearish is False


class TestAdaptedSignal:
    def test_is_amplified(self):
        s = AdaptedSignal(raw_score=0.5, adapted_score=0.7)
        assert s.is_amplified is True
        assert s.is_suppressed is False

    def test_is_suppressed(self):
        s = AdaptedSignal(raw_score=0.5, adapted_score=0.3)
        assert s.is_suppressed is True

    def test_adjustment_pct(self):
        s = AdaptedSignal(raw_score=0.5, adapted_score=0.7)
        assert s.adjustment_pct == pytest.approx(0.4, abs=0.01)

    def test_adjustment_pct_zero(self):
        s = AdaptedSignal(raw_score=0.0, adapted_score=0.0)
        assert s.adjustment_pct == 0.0


# ---------------------------------------------------------------------------
# RegimeSignalAdapter
# ---------------------------------------------------------------------------
class TestRegimeSignalAdapter:
    def test_adapt_signal_bull_momentum(self):
        adapter = RegimeSignalAdapter()
        sig = RawSignal(name="RSI", category="momentum", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(sig, "bull", regime_confidence=1.0)
        assert adapted.adapted_score > sig.raw_score  # Momentum amplified in bull
        assert adapted.weight_multiplier > 1.0

    def test_adapt_signal_crisis_momentum(self):
        adapter = RegimeSignalAdapter()
        sig = RawSignal(name="RSI", category="momentum", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(sig, "crisis", regime_confidence=1.0)
        assert adapted.adapted_score < sig.raw_score  # Momentum suppressed in crisis

    def test_adapt_signal_low_confidence(self):
        adapter = RegimeSignalAdapter()
        sig = RawSignal(name="RSI", category="momentum", raw_score=0.5, confidence=0.7)
        adapted = adapter.adapt_signal(sig, "bull", regime_confidence=0.1)
        # Low confidence = less adaptation, closer to raw
        assert abs(adapted.adapted_score - sig.raw_score) < 0.1

    def test_adapt_signals_composite(self):
        adapter = RegimeSignalAdapter()
        result = adapter.adapt_signals(_signals(), "bull", 0.9)
        assert result.regime == "bull"
        assert len(result.signals) == 3
        assert result.n_amplified + result.n_suppressed + result.n_unchanged == 3
        assert result.composite_score != 0.0

    def test_adapt_signals_empty(self):
        adapter = RegimeSignalAdapter()
        result = adapter.adapt_signals([], "bull")
        assert result.composite_score == 0.0

    def test_get_regime_weights(self):
        adapter = RegimeSignalAdapter()
        weights = adapter.get_regime_weights("crisis")
        assert "quality" in weights
        assert weights["quality"] > weights["momentum"]

    def test_compare_regimes(self):
        adapter = RegimeSignalAdapter()
        comparison = adapter.compare_regimes(_signals())
        assert len(comparison) == 4
        assert "bull" in comparison
        assert "crisis" in comparison

    def test_adapted_signal_set_direction(self):
        result = AdaptedSignalSet(composite_score=0.5)
        assert result.net_direction == "bullish"
        result = AdaptedSignalSet(composite_score=-0.5)
        assert result.net_direction == "bearish"
        result = AdaptedSignalSet(composite_score=0.0)
        assert result.net_direction == "neutral"


# ---------------------------------------------------------------------------
# ThresholdSet / DynamicThresholdManager
# ---------------------------------------------------------------------------
class TestThresholdSet:
    def test_risk_reward_ratio(self):
        ts = ThresholdSet(stop_loss_pct=0.05, take_profit_pct=0.15)
        assert ts.risk_reward_ratio == pytest.approx(3.0)

    def test_is_conservative(self):
        ts = ThresholdSet(min_confidence=0.8, stop_loss_pct=0.02)
        assert ts.is_conservative is True
        ts2 = ThresholdSet(min_confidence=0.5, stop_loss_pct=0.07)
        assert ts2.is_conservative is False


class TestDynamicThresholdManager:
    def test_get_thresholds(self):
        mgr = DynamicThresholdManager()
        ts = mgr.get_thresholds("crisis")
        assert ts.regime == "crisis"
        assert ts.stop_loss_pct < 0.05  # Tighter stops in crisis

    def test_evaluate_signal_enter(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal(
            "RSI", signal_score=0.8, signal_confidence=0.9,
            regime="bull", current_position=False,
        )
        assert decision.action == "enter"
        assert decision.position_size > 0
        assert decision.is_actionable is True

    def test_evaluate_signal_hold(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal(
            "RSI", signal_score=0.2, signal_confidence=0.9,
            regime="bull", current_position=False,
        )
        assert decision.action == "hold"

    def test_evaluate_signal_exit(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal(
            "RSI", signal_score=-0.4, signal_confidence=0.8,
            regime="bull", current_position=True,
        )
        assert decision.action == "exit"

    def test_evaluate_low_confidence(self):
        mgr = DynamicThresholdManager()
        decision = mgr.evaluate_signal(
            "RSI", signal_score=0.9, signal_confidence=0.3,
            regime="crisis", current_position=False,
        )
        # High signal but low confidence in crisis => hold
        assert decision.action == "hold"

    def test_compare_thresholds(self):
        mgr = DynamicThresholdManager()
        comparison = mgr.compare_thresholds("bull")
        assert comparison.current_regime == "bull"
        assert len(comparison.thresholds) == 4
        assert comparison.tightest_stop == "crisis"

    def test_interpolate_thresholds(self):
        mgr = DynamicThresholdManager()
        blended = mgr.interpolate_thresholds({
            "bull": 0.6, "sideways": 0.3, "bear": 0.1,
        })
        assert "blended" in blended.regime
        assert blended.entry_threshold > 0
        assert blended.stop_loss_pct > 0


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------
class TestMethodResult:
    def test_weighted_confidence(self):
        mr = MethodResult(confidence=0.8, weight=0.4)
        assert mr.weighted_confidence == pytest.approx(0.32)


class TestEnsembleResult:
    def test_is_high_confidence(self):
        assert EnsembleResult(consensus_confidence=0.8).is_high_confidence is True
        assert EnsembleResult(consensus_confidence=0.5).is_high_confidence is False

    def test_has_strong_agreement(self):
        assert EnsembleResult(agreement_ratio=0.75).has_strong_agreement is True
        assert EnsembleResult(agreement_ratio=0.5).has_strong_agreement is False


class TestRegimeEnsemble:
    def test_combine_unanimous(self):
        ensemble = RegimeEnsemble()
        results = [
            MethodResult(method="hmm", regime="bull", confidence=0.8,
                         probabilities={"bull": 0.8, "bear": 0.2}, weight=0.4),
            MethodResult(method="cluster", regime="bull", confidence=0.7,
                         probabilities={"bull": 0.7, "bear": 0.3}, weight=0.3),
            MethodResult(method="rules", regime="bull", confidence=0.6,
                         probabilities={"bull": 0.6, "bear": 0.4}, weight=0.3),
        ]
        r = ensemble.combine(results)
        assert r.consensus_regime == "bull"
        assert r.is_unanimous is True
        assert r.agreement_ratio == 1.0

    def test_combine_disagreement(self):
        ensemble = RegimeEnsemble()
        results = _method_results()
        r = ensemble.combine(results)
        assert r.consensus_regime in ("bull", "sideways")
        assert r.is_unanimous is False
        assert r.n_methods == 3

    def test_combine_empty(self):
        ensemble = RegimeEnsemble()
        r = ensemble.combine([])
        assert r.consensus_regime == ""

    def test_compare_methods(self):
        ensemble = RegimeEnsemble()
        results = _method_results()
        comparison = ensemble.compare_methods(results)
        assert len(comparison.divergent_methods) > 0 or len(comparison.method_agreement) == 3
        assert comparison.confidence_spread >= 0

    def test_weighted_regime_state(self):
        ensemble = RegimeEnsemble()
        results = _method_results()
        state = ensemble.weighted_regime_state(results)
        assert state.method == "ensemble"
        assert state.regime in ("bull", "sideways")
        assert state.confidence > 0

    def test_combine_from_states(self):
        from src.regime.models import RegimeState
        ensemble = RegimeEnsemble()
        states = {
            "hmm": RegimeState(regime="bull", confidence=0.8,
                               probabilities={"bull": 0.8, "bear": 0.2}),
            "clustering": RegimeState(regime="bull", confidence=0.7,
                                      probabilities={"bull": 0.7, "bear": 0.3}),
        }
        r = ensemble.combine_from_states(states)
        assert r.consensus_regime == "bull"
        assert r.n_methods == 2


# ---------------------------------------------------------------------------
# Regime Signals
# ---------------------------------------------------------------------------
class TestTransitionSignal:
    def test_is_risk_on(self):
        assert TransitionSignal(signal_type="risk_on").is_risk_on is True
        assert TransitionSignal(signal_type="risk_off").is_risk_on is False

    def test_is_strong(self):
        assert TransitionSignal(strength=0.8).is_strong is True
        assert TransitionSignal(strength=0.3).is_strong is False


class TestPersistenceSignal:
    def test_is_extended(self):
        assert PersistenceSignal(persistence_ratio=2.0).is_extended is True
        assert PersistenceSignal(persistence_ratio=0.5).is_extended is False

    def test_is_early(self):
        assert PersistenceSignal(persistence_ratio=0.1).is_early is True


class TestAlignmentSignal:
    def test_is_contrarian(self):
        s = AlignmentSignal(is_aligned=False, alignment_score=-0.5)
        assert s.is_contrarian is True
        s2 = AlignmentSignal(is_aligned=True, alignment_score=0.5)
        assert s2.is_contrarian is False


class TestDivergenceSignal:
    def test_is_warning(self):
        assert DivergenceSignal(signal="transition_warning").is_warning is True
        assert DivergenceSignal(signal="stable").is_warning is False

    def test_agreement_pct(self):
        d = DivergenceSignal(methods_agreeing=2, methods_total=3)
        assert d.agreement_pct == pytest.approx(0.667, abs=0.01)


class TestRegimeSignalGenerator:
    def test_transition_risk_on(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("bear", "bull", confidence=0.8)
        assert sig.signal_type == "risk_on"
        assert sig.strength > 0

    def test_transition_risk_off(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("bull", "crisis", confidence=0.9)
        assert sig.signal_type == "risk_off"
        assert sig.is_strong is True

    def test_transition_same_regime(self):
        gen = RegimeSignalGenerator()
        sig = gen.transition_signal("bull", "bull", confidence=0.9)
        assert sig.signal_type == "neutral"

    def test_persistence_extended(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=150)
        assert sig.is_extended is True
        assert sig.conviction < 0.8  # Conviction drops when extended

    def test_persistence_early(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=5)
        assert sig.is_early is True

    def test_persistence_normal(self):
        gen = RegimeSignalGenerator()
        sig = gen.persistence_signal("bull", duration=50)
        assert sig.signal == "normal"

    def test_alignment_bull_positive_momentum(self):
        gen = RegimeSignalGenerator()
        sig = gen.alignment_signal("bull", momentum_score=0.6)
        assert sig.is_aligned is True
        assert sig.recommendation == "lean_in"

    def test_alignment_bull_negative_momentum(self):
        gen = RegimeSignalGenerator()
        sig = gen.alignment_signal("bull", momentum_score=-0.5)
        assert sig.is_aligned is False
        assert sig.is_contrarian is True

    def test_divergence_stable(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({"hmm": "bull", "cluster": "bull", "rules": "bull"})
        assert sig.signal == "stable"
        assert sig.divergence_score == 0.0

    def test_divergence_warning(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({"hmm": "bull", "cluster": "bear", "rules": "crisis"})
        assert sig.signal == "transition_warning"
        assert sig.divergence_score > 0.5

    def test_divergence_empty(self):
        gen = RegimeSignalGenerator()
        sig = gen.divergence_signal({})
        assert sig.primary_regime == ""

    def test_generate_summary_with_transition(self):
        gen = RegimeSignalGenerator()
        summary = gen.generate_summary(
            current_regime="bull",
            previous_regime="bear",
            duration=10,
            momentum_score=0.5,
            method_regimes={"hmm": "bull", "cluster": "bull"},
            regime_confidence=0.8,
        )
        assert summary.current_regime == "bull"
        assert summary.transition_signal is not None
        assert summary.transition_signal.is_risk_on is True
        assert summary.overall_bias == "bullish"

    def test_generate_summary_no_transition(self):
        gen = RegimeSignalGenerator()
        summary = gen.generate_summary(
            current_regime="sideways",
            duration=30,
            momentum_score=0.0,
        )
        assert summary.transition_signal is None
        assert summary.persistence_signal is not None
        assert summary.divergence_signal is None

    def test_summary_has_actionable(self):
        gen = RegimeSignalGenerator()
        summary = gen.generate_summary(
            current_regime="bull",
            previous_regime="crisis",
            duration=5,
            momentum_score=-0.6,
            method_regimes={"hmm": "bull", "cluster": "bear", "rules": "crisis"},
            regime_confidence=0.9,
        )
        assert summary.has_actionable_signal is True
