"""Regime-Specific Trading Signals.

Generates signals from regime dynamics: regime transitions, persistence
strength, momentum-regime alignment, and cross-method divergence.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.regime.config import RegimeType
from src.regime.models import RegimeState, TransitionMatrix

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class TransitionSignal:
    """Signal generated from a regime transition."""
    from_regime: str = ""
    to_regime: str = ""
    signal_type: str = ""  # risk_on, risk_off, neutral
    strength: float = 0.0  # 0-1
    confidence: float = 0.0
    description: str = ""

    @property
    def is_risk_on(self) -> bool:
        return self.signal_type == "risk_on"

    @property
    def is_risk_off(self) -> bool:
        return self.signal_type == "risk_off"

    @property
    def is_strong(self) -> bool:
        return self.strength >= 0.7


@dataclass
class PersistenceSignal:
    """Signal from regime persistence (duration in current regime)."""
    regime: str = ""
    duration: int = 0
    expected_duration: float = 0.0
    persistence_ratio: float = 0.0  # duration / expected_duration
    signal: str = ""  # extended, normal, early
    conviction: float = 0.0  # Higher = more confident regime continues

    @property
    def is_extended(self) -> bool:
        return self.persistence_ratio > 1.5

    @property
    def is_early(self) -> bool:
        return self.persistence_ratio < 0.3


@dataclass
class AlignmentSignal:
    """Signal from alignment between momentum and regime."""
    regime: str = ""
    momentum_direction: str = ""  # up, down, flat
    is_aligned: bool = False
    alignment_score: float = 0.0  # -1 to +1
    recommendation: str = ""  # lean_in, fade, neutral

    @property
    def is_contrarian(self) -> bool:
        return not self.is_aligned and abs(self.alignment_score) > 0.3


@dataclass
class DivergenceSignal:
    """Signal from divergence between detection methods."""
    primary_regime: str = ""
    secondary_regime: str = ""
    divergence_score: float = 0.0  # 0-1
    signal: str = ""  # transition_warning, stable, uncertain
    methods_agreeing: int = 0
    methods_total: int = 0

    @property
    def is_warning(self) -> bool:
        return self.signal == "transition_warning"

    @property
    def agreement_pct(self) -> float:
        if self.methods_total == 0:
            return 0.0
        return self.methods_agreeing / self.methods_total


@dataclass
class RegimeSignalSummary:
    """Summary of all regime-derived signals."""
    current_regime: str = ""
    transition_signal: Optional[TransitionSignal] = None
    persistence_signal: Optional[PersistenceSignal] = None
    alignment_signal: Optional[AlignmentSignal] = None
    divergence_signal: Optional[DivergenceSignal] = None
    overall_bias: str = "neutral"  # bullish, bearish, neutral
    overall_conviction: float = 0.0

    @property
    def has_actionable_signal(self) -> bool:
        if self.transition_signal and self.transition_signal.is_strong:
            return True
        if self.alignment_signal and self.alignment_signal.is_contrarian:
            return True
        if self.divergence_signal and self.divergence_signal.is_warning:
            return True
        return False


# ---------------------------------------------------------------------------
# Transition signal classification
# ---------------------------------------------------------------------------
TRANSITION_SIGNALS: dict[tuple[str, str], tuple[str, float]] = {
    ("crisis", "bear"): ("risk_on", 0.5),
    ("crisis", "sideways"): ("risk_on", 0.7),
    ("crisis", "bull"): ("risk_on", 1.0),
    ("bear", "sideways"): ("risk_on", 0.5),
    ("bear", "bull"): ("risk_on", 0.8),
    ("sideways", "bull"): ("risk_on", 0.4),
    ("bull", "sideways"): ("risk_off", 0.3),
    ("bull", "bear"): ("risk_off", 0.7),
    ("bull", "crisis"): ("risk_off", 1.0),
    ("sideways", "bear"): ("risk_off", 0.5),
    ("sideways", "crisis"): ("risk_off", 0.8),
    ("bear", "crisis"): ("risk_off", 0.6),
}

# Expected durations (in trading days) per regime
DEFAULT_EXPECTED_DURATIONS: dict[str, float] = {
    "bull": 80.0,
    "bear": 40.0,
    "sideways": 55.0,
    "crisis": 15.0,
}


# ---------------------------------------------------------------------------
# Regime Signal Generator
# ---------------------------------------------------------------------------
class RegimeSignalGenerator:
    """Generates trading signals from regime dynamics."""

    def __init__(
        self,
        expected_durations: Optional[dict[str, float]] = None,
    ) -> None:
        self.expected_durations = expected_durations or dict(
            DEFAULT_EXPECTED_DURATIONS
        )

    def transition_signal(
        self,
        from_regime: str,
        to_regime: str,
        confidence: float = 0.5,
    ) -> TransitionSignal:
        """Generate signal from a regime transition.

        Args:
            from_regime: Previous regime.
            to_regime: New regime.
            confidence: Confidence in the transition.

        Returns:
            TransitionSignal with risk on/off classification.
        """
        key = (from_regime.lower(), to_regime.lower())

        if key in TRANSITION_SIGNALS:
            sig_type, strength = TRANSITION_SIGNALS[key]
        else:
            sig_type = "neutral"
            strength = 0.0

        # Scale strength by confidence
        adj_strength = strength * confidence

        if sig_type == "risk_on":
            desc = f"Regime improving: {from_regime} -> {to_regime}"
        elif sig_type == "risk_off":
            desc = f"Regime deteriorating: {from_regime} -> {to_regime}"
        else:
            desc = f"Regime change: {from_regime} -> {to_regime}"

        return TransitionSignal(
            from_regime=from_regime.lower(),
            to_regime=to_regime.lower(),
            signal_type=sig_type,
            strength=round(adj_strength, 4),
            confidence=round(confidence, 4),
            description=desc,
        )

    def persistence_signal(
        self,
        regime: str,
        duration: int,
        expected_duration: Optional[float] = None,
    ) -> PersistenceSignal:
        """Generate signal from regime persistence.

        Long-duration regimes may signal exhaustion; early regimes
        may signal trend continuation.

        Args:
            regime: Current regime.
            duration: Days in current regime.
            expected_duration: Expected regime duration.

        Returns:
            PersistenceSignal with continuation/exhaustion assessment.
        """
        exp_dur = expected_duration or self.expected_durations.get(
            regime.lower(), 50.0
        )

        ratio = duration / exp_dur if exp_dur > 0 else 0.0

        if ratio > 1.5:
            signal = "extended"
            # Conviction decays as regime extends beyond expected
            conviction = max(0.1, 1.0 - (ratio - 1.0) * 0.3)
        elif ratio < 0.3:
            signal = "early"
            conviction = min(0.9, 0.5 + ratio)
        else:
            signal = "normal"
            conviction = 0.7

        return PersistenceSignal(
            regime=regime.lower(),
            duration=duration,
            expected_duration=round(exp_dur, 1),
            persistence_ratio=round(ratio, 4),
            signal=signal,
            conviction=round(conviction, 4),
        )

    def alignment_signal(
        self,
        regime: str,
        momentum_score: float,
    ) -> AlignmentSignal:
        """Generate signal from momentum-regime alignment.

        When momentum confirms the regime (e.g., positive momentum in
        bull regime), conviction is higher.  Divergence may signal
        a regime transition.

        Args:
            regime: Current regime.
            momentum_score: Momentum indicator (-1 to +1).

        Returns:
            AlignmentSignal with alignment assessment.
        """
        regime_key = regime.lower()

        # Expected momentum direction per regime
        expected_direction = {
            "bull": 1.0,
            "bear": -1.0,
            "sideways": 0.0,
            "crisis": -1.0,
        }

        expected = expected_direction.get(regime_key, 0.0)

        if momentum_score > 0.1:
            mom_dir = "up"
        elif momentum_score < -0.1:
            mom_dir = "down"
        else:
            mom_dir = "flat"

        # Alignment = correlation between momentum and expected direction
        if abs(expected) < 0.01:
            # Sideways: aligned if momentum is close to zero
            aligned = abs(momentum_score) < 0.3
            alignment_score = 1.0 - abs(momentum_score)
        else:
            alignment_score = momentum_score * expected
            aligned = alignment_score > 0

        # Recommendation
        if aligned and alignment_score > 0.3:
            recommendation = "lean_in"
        elif not aligned and abs(alignment_score) > 0.3:
            recommendation = "fade"
        else:
            recommendation = "neutral"

        return AlignmentSignal(
            regime=regime_key,
            momentum_direction=mom_dir,
            is_aligned=aligned,
            alignment_score=round(alignment_score, 4),
            recommendation=recommendation,
        )

    def divergence_signal(
        self,
        method_regimes: dict[str, str],
        method_confidences: Optional[dict[str, float]] = None,
    ) -> DivergenceSignal:
        """Generate signal from method divergence.

        When detection methods disagree, it may signal an upcoming
        regime transition.

        Args:
            method_regimes: Dict of method -> detected regime.
            method_confidences: Dict of method -> confidence.

        Returns:
            DivergenceSignal with divergence assessment.
        """
        if not method_regimes:
            return DivergenceSignal()

        confidences = method_confidences or {
            m: 0.5 for m in method_regimes
        }

        # Find most common regime (weighted by confidence)
        regime_votes: dict[str, float] = {}
        for method, regime in method_regimes.items():
            conf = confidences.get(method, 0.5)
            regime_votes[regime] = regime_votes.get(regime, 0.0) + conf

        primary = max(regime_votes, key=regime_votes.get)
        remaining = {r: v for r, v in regime_votes.items() if r != primary}
        secondary = max(remaining, key=remaining.get) if remaining else primary

        # Agreement
        total = len(method_regimes)
        agreeing = sum(1 for r in method_regimes.values() if r == primary)

        # Divergence score: 0 = full agreement, 1 = complete disagreement
        divergence = 1.0 - (agreeing / total) if total > 0 else 0.0

        if divergence >= 0.5:
            signal = "transition_warning"
        elif divergence > 0:
            signal = "uncertain"
        else:
            signal = "stable"

        return DivergenceSignal(
            primary_regime=primary,
            secondary_regime=secondary,
            divergence_score=round(divergence, 4),
            signal=signal,
            methods_agreeing=agreeing,
            methods_total=total,
        )

    def generate_summary(
        self,
        current_regime: str,
        previous_regime: Optional[str] = None,
        duration: int = 0,
        momentum_score: float = 0.0,
        method_regimes: Optional[dict[str, str]] = None,
        regime_confidence: float = 0.5,
    ) -> RegimeSignalSummary:
        """Generate comprehensive regime signal summary.

        Args:
            current_regime: Current detected regime.
            previous_regime: Previous regime (for transition signal).
            duration: Days in current regime.
            momentum_score: Current momentum indicator.
            method_regimes: Dict of method -> regime (for divergence).
            regime_confidence: Confidence in current regime.

        Returns:
            RegimeSignalSummary with all signal types.
        """
        # Transition signal
        t_sig = None
        if previous_regime and previous_regime != current_regime:
            t_sig = self.transition_signal(
                previous_regime, current_regime, regime_confidence
            )

        # Persistence signal
        p_sig = self.persistence_signal(current_regime, duration)

        # Alignment signal
        a_sig = self.alignment_signal(current_regime, momentum_score)

        # Divergence signal
        d_sig = None
        if method_regimes:
            d_sig = self.divergence_signal(method_regimes)

        # Overall bias
        bias_score = 0.0
        conviction_parts = []

        if t_sig:
            if t_sig.is_risk_on:
                bias_score += t_sig.strength
            elif t_sig.is_risk_off:
                bias_score -= t_sig.strength
            conviction_parts.append(t_sig.confidence)

        if a_sig:
            if a_sig.recommendation == "lean_in":
                bias_score += 0.3
            elif a_sig.recommendation == "fade":
                bias_score -= 0.3

        # Regime inherent bias
        regime_bias = {
            "bull": 0.3, "bear": -0.3,
            "sideways": 0.0, "crisis": -0.5,
        }
        bias_score += regime_bias.get(current_regime.lower(), 0.0)

        conviction_parts.append(p_sig.conviction)
        if d_sig:
            # High divergence reduces conviction
            conviction_parts.append(1.0 - d_sig.divergence_score)

        overall_conviction = (
            sum(conviction_parts) / len(conviction_parts)
            if conviction_parts else 0.0
        )

        if bias_score > 0.2:
            overall_bias = "bullish"
        elif bias_score < -0.2:
            overall_bias = "bearish"
        else:
            overall_bias = "neutral"

        return RegimeSignalSummary(
            current_regime=current_regime.lower(),
            transition_signal=t_sig,
            persistence_signal=p_sig,
            alignment_signal=a_sig,
            divergence_signal=d_sig,
            overall_bias=overall_bias,
            overall_conviction=round(overall_conviction, 4),
        )
