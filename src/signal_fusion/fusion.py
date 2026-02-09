"""Signal Fusion — merges multiple raw signals into consensus.

Implements weighted fusion with time decay, agreement scoring,
composite score calculation, and reasoning generation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.signal_fusion.collector import RawSignal, SignalSource


# ── Default source weights ────────────────────────────────────────────

DEFAULT_SOURCE_WEIGHTS: dict[SignalSource, float] = {
    SignalSource.EMA_CLOUD: 0.25,
    SignalSource.SOCIAL: 0.15,
    SignalSource.FACTOR: 0.20,
    SignalSource.ML_RANKING: 0.15,
    SignalSource.SENTIMENT: 0.10,
    SignalSource.TECHNICAL: 0.10,
    SignalSource.FUNDAMENTAL: 0.05,
}


@dataclass
class FusionConfig:
    """Configuration for signal fusion.

    Attributes:
        source_weights: Weight per source (normalized internally).
        min_sources: Minimum number of sources required for a valid fusion.
        agreement_threshold: Fraction of sources that must agree for consensus.
        decay_minutes: Half-life for time-decay weighting of stale signals.
    """

    source_weights: dict[SignalSource, float] = field(
        default_factory=lambda: dict(DEFAULT_SOURCE_WEIGHTS)
    )
    min_sources: int = 2
    agreement_threshold: float = 0.6
    decay_minutes: float = 60.0

    def __post_init__(self) -> None:
        # Normalize weights so they sum to 1.0
        total = sum(self.source_weights.values())
        if total > 0:
            self.source_weights = {
                k: v / total for k, v in self.source_weights.items()
            }

    def get_weight(self, source: SignalSource) -> float:
        """Return the normalized weight for a source (0.0 if unknown)."""
        return self.source_weights.get(source, 0.0)


@dataclass
class FusedSignal:
    """Result of fusing multiple raw signals for a single symbol.

    Attributes:
        symbol: Ticker symbol.
        direction: Consensus direction ('bullish', 'bearish', 'neutral').
        composite_score: Score from -100 (strong sell) to +100 (strong buy).
        confidence: Overall fusion confidence 0.0 to 1.0.
        source_count: Number of sources that contributed.
        agreeing_sources: Sources that agree with the consensus direction.
        dissenting_sources: Sources that disagree with the consensus direction.
        reasoning: Human-readable reasoning strings.
        timestamp: When fusion was computed.
    """

    symbol: str
    direction: str
    composite_score: float
    confidence: float
    source_count: int
    agreeing_sources: list[str] = field(default_factory=list)
    dissenting_sources: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "composite_score": round(self.composite_score, 2),
            "confidence": round(self.confidence, 3),
            "source_count": self.source_count,
            "agreeing_sources": self.agreeing_sources,
            "dissenting_sources": self.dissenting_sources,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


# ── SignalFusion engine ───────────────────────────────────────────────


class SignalFusion:
    """Fuses multiple raw signals into a single consensus signal.

    Pipeline:
      1) Group signals by symbol
      2) Weight by source importance
      3) Apply time-decay for stale signals
      4) Calculate agreement ratio
      5) Generate composite score (-100 to +100)
      6) Produce human-readable reasoning

    Args:
        config: FusionConfig with weights, thresholds, etc.
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()

    # ── public API ────────────────────────────────────────────────

    def fuse(self, signals: list[RawSignal]) -> FusedSignal:
        """Fuse a list of raw signals (assumed to be for the same symbol).

        Args:
            signals: Raw signals to fuse (should be for a single symbol).

        Returns:
            A FusedSignal with composite score and reasoning.
        """
        if not signals:
            return FusedSignal(
                symbol="UNKNOWN",
                direction="neutral",
                composite_score=0.0,
                confidence=0.0,
                source_count=0,
                reasoning=["No signals provided"],
            )

        symbol = signals[0].symbol
        now = datetime.now(timezone.utc)

        # Deduplicate by source (keep latest per source)
        by_source: dict[SignalSource, RawSignal] = {}
        for sig in signals:
            existing = by_source.get(sig.source)
            if existing is None or sig.timestamp > existing.timestamp:
                by_source[sig.source] = sig

        unique_signals = list(by_source.values())
        source_count = len(unique_signals)

        # Compute direction scores (weighted)
        bullish_score = 0.0
        bearish_score = 0.0
        neutral_score = 0.0
        total_weight = 0.0
        weighted_confidence = 0.0

        agreeing: list[str] = []
        dissenting: list[str] = []
        reasoning: list[str] = []

        for sig in unique_signals:
            weight = self.config.get_weight(sig.source)
            decay = self._time_decay(sig.timestamp, now)
            effective_weight = weight * decay * (sig.strength / 100.0)
            conf_contribution = sig.confidence * weight * decay

            total_weight += weight * decay
            weighted_confidence += conf_contribution

            if sig.direction == "bullish":
                bullish_score += effective_weight
            elif sig.direction == "bearish":
                bearish_score += effective_weight
            else:
                neutral_score += effective_weight

            reasoning.append(
                f"{sig.source.value}: {sig.direction} "
                f"(str={sig.strength:.0f}, conf={sig.confidence:.2f}, "
                f"decay={decay:.2f})"
            )

        # Determine consensus direction
        scores = {
            "bullish": bullish_score,
            "bearish": bearish_score,
            "neutral": neutral_score,
        }
        direction = max(scores, key=scores.get)  # type: ignore[arg-type]

        # Agreement ratio
        for sig in unique_signals:
            source_name = sig.source.value
            if sig.direction == direction:
                agreeing.append(source_name)
            else:
                dissenting.append(source_name)

        agreement_ratio = len(agreeing) / max(source_count, 1)

        # Composite score: -100 to +100
        # Net = bullish - bearish, scaled to [-100, 100]
        net_score = bullish_score - bearish_score
        if total_weight > 0:
            composite = (net_score / total_weight) * 100.0
        else:
            composite = 0.0
        composite = max(-100.0, min(100.0, composite))

        # Overall confidence
        if total_weight > 0:
            confidence = weighted_confidence / total_weight
        else:
            confidence = 0.0
        # Boost confidence when agreement is high
        confidence *= (0.5 + 0.5 * agreement_ratio)
        confidence = max(0.0, min(1.0, confidence))

        # Summary reasoning
        reasoning.insert(
            0,
            f"Consensus: {direction} | Agreement: {agreement_ratio:.0%} "
            f"({len(agreeing)}/{source_count} sources) | "
            f"Score: {composite:+.1f}",
        )

        return FusedSignal(
            symbol=symbol,
            direction=direction,
            composite_score=composite,
            confidence=confidence,
            source_count=source_count,
            agreeing_sources=agreeing,
            dissenting_sources=dissenting,
            reasoning=reasoning,
            timestamp=now,
        )

    def fuse_batch(
        self, by_symbol: dict[str, list[RawSignal]]
    ) -> dict[str, FusedSignal]:
        """Fuse signals for multiple symbols.

        Args:
            by_symbol: Dict mapping symbol -> list of RawSignal.

        Returns:
            Dict mapping symbol -> FusedSignal.
        """
        return {symbol: self.fuse(sigs) for symbol, sigs in by_symbol.items()}

    # ── internal helpers ──────────────────────────────────────────

    def _time_decay(self, signal_time: datetime, now: datetime) -> float:
        """Exponential time decay based on signal age.

        Uses half-life = config.decay_minutes.
        Returns a multiplier between 0.0 and 1.0.
        """
        if self.config.decay_minutes <= 0:
            return 1.0
        age_minutes = (now - signal_time).total_seconds() / 60.0
        if age_minutes <= 0:
            return 1.0
        half_life = self.config.decay_minutes
        return math.exp(-0.693 * age_minutes / half_life)
