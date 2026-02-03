"""Regime-Aware Signal Adapter.

Adjusts raw signal weights and confidence levels based on the current
market regime.  For example, momentum signals are amplified in bull
regimes and suppressed in crisis regimes.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.regime.config import RegimeType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class RawSignal:
    """A raw (unadjusted) trading signal."""
    name: str = ""
    category: str = ""  # momentum, value, quality, technical, volatility
    raw_score: float = 0.0  # -1 to +1
    confidence: float = 0.5

    @property
    def is_bullish(self) -> bool:
        return self.raw_score > 0.1

    @property
    def is_bearish(self) -> bool:
        return self.raw_score < -0.1


@dataclass
class AdaptedSignal:
    """Signal after regime-aware adjustment."""
    name: str = ""
    category: str = ""
    raw_score: float = 0.0
    adapted_score: float = 0.0
    regime: str = ""
    weight_multiplier: float = 1.0
    confidence: float = 0.5
    adapted_confidence: float = 0.5

    @property
    def adjustment_pct(self) -> float:
        if abs(self.raw_score) < 1e-10:
            return 0.0
        return (self.adapted_score - self.raw_score) / abs(self.raw_score)

    @property
    def is_amplified(self) -> bool:
        return abs(self.adapted_score) > abs(self.raw_score)

    @property
    def is_suppressed(self) -> bool:
        return abs(self.adapted_score) < abs(self.raw_score)


@dataclass
class AdaptedSignalSet:
    """Collection of adapted signals with aggregate metrics."""
    regime: str = ""
    regime_confidence: float = 0.0
    signals: list[AdaptedSignal] = field(default_factory=list)
    composite_score: float = 0.0
    n_amplified: int = 0
    n_suppressed: int = 0
    n_unchanged: int = 0

    @property
    def net_direction(self) -> str:
        if self.composite_score > 0.1:
            return "bullish"
        elif self.composite_score < -0.1:
            return "bearish"
        return "neutral"

    @property
    def avg_confidence(self) -> float:
        if not self.signals:
            return 0.0
        return sum(s.adapted_confidence for s in self.signals) / len(self.signals)


# ---------------------------------------------------------------------------
# Regime weight multipliers per signal category
# ---------------------------------------------------------------------------
REGIME_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "bull": {
        "momentum": 1.4,
        "value": 0.7,
        "quality": 0.9,
        "technical": 1.2,
        "volatility": 0.6,
        "growth": 1.3,
    },
    "bear": {
        "momentum": 0.5,
        "value": 1.3,
        "quality": 1.4,
        "technical": 0.8,
        "volatility": 1.3,
        "growth": 0.5,
    },
    "sideways": {
        "momentum": 0.8,
        "value": 1.2,
        "quality": 1.1,
        "technical": 1.0,
        "volatility": 1.0,
        "growth": 0.9,
    },
    "crisis": {
        "momentum": 0.3,
        "value": 0.6,
        "quality": 1.5,
        "technical": 0.5,
        "volatility": 1.5,
        "growth": 0.3,
    },
}

# Confidence adjustments: regime confidence affects signal confidence
REGIME_CONFIDENCE_FLOOR: dict[str, float] = {
    "bull": 0.5,
    "bear": 0.4,
    "sideways": 0.3,
    "crisis": 0.6,
}


# ---------------------------------------------------------------------------
# Signal Adapter
# ---------------------------------------------------------------------------
class RegimeSignalAdapter:
    """Adapts raw signals based on current market regime."""

    def __init__(
        self,
        signal_weights: Optional[dict[str, dict[str, float]]] = None,
        confidence_floors: Optional[dict[str, float]] = None,
    ) -> None:
        self.signal_weights = signal_weights or REGIME_SIGNAL_WEIGHTS
        self.confidence_floors = confidence_floors or REGIME_CONFIDENCE_FLOOR

    def adapt_signal(
        self,
        signal: RawSignal,
        regime: str,
        regime_confidence: float = 1.0,
    ) -> AdaptedSignal:
        """Adapt a single signal for the current regime.

        Args:
            signal: Raw trading signal.
            regime: Current market regime.
            regime_confidence: Confidence in regime classification (0-1).

        Returns:
            AdaptedSignal with regime-adjusted score and confidence.
        """
        regime_key = regime.lower()
        weights = self.signal_weights.get(regime_key, {})
        multiplier = weights.get(signal.category, 1.0)

        # Blend multiplier toward 1.0 based on regime confidence
        # Low confidence = less adaptation
        blended_mult = 1.0 + (multiplier - 1.0) * regime_confidence
        adapted_score = max(-1.0, min(1.0, signal.raw_score * blended_mult))

        # Adjust confidence
        floor = self.confidence_floors.get(regime_key, 0.3)
        adapted_conf = max(floor, signal.confidence * regime_confidence)

        return AdaptedSignal(
            name=signal.name,
            category=signal.category,
            raw_score=signal.raw_score,
            adapted_score=round(adapted_score, 6),
            regime=regime_key,
            weight_multiplier=round(blended_mult, 4),
            confidence=signal.confidence,
            adapted_confidence=round(adapted_conf, 4),
        )

    def adapt_signals(
        self,
        signals: list[RawSignal],
        regime: str,
        regime_confidence: float = 1.0,
    ) -> AdaptedSignalSet:
        """Adapt a collection of signals for the current regime.

        Args:
            signals: List of raw signals.
            regime: Current market regime.
            regime_confidence: Confidence in regime classification.

        Returns:
            AdaptedSignalSet with all adapted signals and composite score.
        """
        adapted = [
            self.adapt_signal(s, regime, regime_confidence)
            for s in signals
        ]

        n_amp = sum(1 for s in adapted if s.is_amplified)
        n_sup = sum(1 for s in adapted if s.is_suppressed)
        n_unc = len(adapted) - n_amp - n_sup

        # Composite = confidence-weighted average of adapted scores
        if adapted:
            total_conf = sum(s.adapted_confidence for s in adapted)
            if total_conf > 0:
                composite = sum(
                    s.adapted_score * s.adapted_confidence for s in adapted
                ) / total_conf
            else:
                composite = sum(s.adapted_score for s in adapted) / len(adapted)
        else:
            composite = 0.0

        return AdaptedSignalSet(
            regime=regime.lower(),
            regime_confidence=regime_confidence,
            signals=adapted,
            composite_score=round(composite, 6),
            n_amplified=n_amp,
            n_suppressed=n_sup,
            n_unchanged=n_unc,
        )

    def get_regime_weights(self, regime: str) -> dict[str, float]:
        """Get signal category weights for a regime.

        Args:
            regime: Market regime name.

        Returns:
            Dict of category -> weight multiplier.
        """
        return dict(self.signal_weights.get(regime.lower(), {}))

    def compare_regimes(
        self,
        signals: list[RawSignal],
    ) -> dict[str, AdaptedSignalSet]:
        """Compare signal adaptation across all regimes.

        Args:
            signals: List of raw signals.

        Returns:
            Dict of regime -> AdaptedSignalSet.
        """
        result = {}
        for regime in ["bull", "bear", "sideways", "crisis"]:
            result[regime] = self.adapt_signals(signals, regime, 1.0)
        return result
