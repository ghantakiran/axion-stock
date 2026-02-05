"""Multi-Source Sentiment Fusion.

Combines sentiment signals from diverse sources using adaptive
weighting, conflict resolution, and source reliability tracking.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class SourceSignal:
    """Individual source signal for fusion."""
    source: str = ""
    score: float = 0.0  # -1 to +1
    confidence: float = 0.5  # 0-1
    weight: float = 1.0
    symbol: str = ""

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight * self.confidence


@dataclass
class FusionResult:
    """Result of multi-source sentiment fusion."""
    symbol: str = ""
    fused_score: float = 0.0  # -1 to +1
    fused_confidence: float = 0.0
    n_sources: int = 0
    agreement_ratio: float = 0.0  # 0-1, how much sources agree
    conflict_level: float = 0.0  # 0-1, source disagreement
    dominant_source: str = ""
    source_contributions: dict = field(default_factory=dict)

    @property
    def sentiment_label(self) -> str:
        if self.fused_score > 0.3:
            return "bullish"
        elif self.fused_score > 0.1:
            return "mildly_bullish"
        elif self.fused_score >= -0.1:
            return "neutral"
        elif self.fused_score >= -0.3:
            return "mildly_bearish"
        else:
            return "bearish"

    @property
    def is_high_conviction(self) -> bool:
        return self.fused_confidence >= 0.7 and self.agreement_ratio >= 0.6

    @property
    def has_conflict(self) -> bool:
        return self.conflict_level > 0.5


@dataclass
class SourceReliability:
    """Tracks reliability of a source over time."""
    source: str = ""
    accuracy_score: float = 0.5  # Rolling accuracy
    n_observations: int = 0
    hit_rate: float = 0.5  # Fraction of correct directional calls
    avg_confidence: float = 0.5
    weight_adjustment: float = 1.0  # Adaptive weight multiplier

    @property
    def is_reliable(self) -> bool:
        return self.accuracy_score >= 0.5 and self.n_observations >= 10

    @property
    def effective_weight(self) -> float:
        return self.weight_adjustment * self.accuracy_score


@dataclass
class FusionComparison:
    """Cross-symbol fusion comparison."""
    results: list[FusionResult] = field(default_factory=list)
    most_bullish: str = ""
    most_bearish: str = ""
    highest_conviction: str = ""
    avg_agreement: float = 0.0

    @property
    def n_symbols(self) -> int:
        return len(self.results)


# ---------------------------------------------------------------------------
# Sentiment Fusion Engine
# ---------------------------------------------------------------------------

# Default source weights
DEFAULT_SOURCE_WEIGHTS = {
    "news": 0.25,
    "social": 0.15,
    "insider": 0.20,
    "analyst": 0.20,
    "earnings": 0.10,
    "options": 0.10,
}


class SentimentFusionEngine:
    """Fuses sentiment from multiple sources with adaptive weighting.

    Handles source conflicts, tracks reliability, and produces
    a single fused score with confidence metrics.
    """

    def __init__(
        self,
        source_weights: Optional[dict[str, float]] = None,
        min_sources: int = 2,
        conflict_penalty: float = 0.3,
    ) -> None:
        self.source_weights = source_weights or dict(DEFAULT_SOURCE_WEIGHTS)
        self.min_sources = min_sources
        self.conflict_penalty = conflict_penalty
        self._reliability: dict[str, SourceReliability] = {}

    def fuse(
        self,
        signals: list[SourceSignal],
        symbol: str = "",
    ) -> FusionResult:
        """Fuse multiple source signals into a single score.

        Args:
            signals: List of source signals.
            symbol: Ticker symbol.

        Returns:
            FusionResult with fused score and metrics.
        """
        if not signals:
            return FusionResult(symbol=symbol)

        if len(signals) < self.min_sources:
            # Not enough sources — return low-confidence average
            avg = float(np.mean([s.score for s in signals]))
            return FusionResult(
                symbol=symbol,
                fused_score=round(avg, 4),
                fused_confidence=0.2,
                n_sources=len(signals),
                agreement_ratio=1.0 if len(signals) == 1 else 0.5,
                conflict_level=0.0,
                dominant_source=signals[0].source if signals else "",
            )

        # Compute effective weights
        weights = []
        for s in signals:
            base_w = self.source_weights.get(s.source, 0.1)
            reliability = self._reliability.get(s.source)
            reliability_mult = reliability.effective_weight if reliability else 1.0
            weights.append(base_w * s.confidence * reliability_mult)

        total_w = sum(weights)
        if total_w <= 0:
            return FusionResult(symbol=symbol, n_sources=len(signals))

        # Weighted fusion
        fused = sum(
            s.score * w for s, w in zip(signals, weights)
        ) / total_w

        # Source contributions
        contributions = {}
        for s, w in zip(signals, weights):
            contributions[s.source] = round(w / total_w, 4)

        # Agreement analysis
        signs = [1 if s.score > 0.05 else (-1 if s.score < -0.05 else 0) for s in signals]
        non_neutral = [s for s in signs if s != 0]
        if non_neutral:
            majority = max(set(non_neutral), key=non_neutral.count)
            agreement = sum(1 for s in non_neutral if s == majority) / len(non_neutral)
        else:
            agreement = 1.0

        # Conflict: standard deviation of scores
        score_std = float(np.std([s.score for s in signals]))
        conflict = min(1.0, score_std / 0.5)  # Normalize: 0.5 std = full conflict

        # Confidence: base from source count and agreement, penalize conflict
        base_conf = min(1.0, len(signals) / 5.0) * agreement
        confidence = base_conf * (1.0 - self.conflict_penalty * conflict)

        # Dominant source
        dominant_idx = int(np.argmax(weights))
        dominant_source = signals[dominant_idx].source

        return FusionResult(
            symbol=symbol,
            fused_score=round(float(np.clip(fused, -1.0, 1.0)), 4),
            fused_confidence=round(max(0.0, confidence), 4),
            n_sources=len(signals),
            agreement_ratio=round(agreement, 4),
            conflict_level=round(conflict, 4),
            dominant_source=dominant_source,
            source_contributions=contributions,
        )

    def update_reliability(
        self,
        source: str,
        predicted_direction: float,
        actual_direction: float,
    ) -> SourceReliability:
        """Update source reliability based on prediction accuracy.

        Args:
            source: Source name.
            predicted_direction: Predicted sentiment (-1 to 1).
            actual_direction: Actual outcome (-1 to 1).

        Returns:
            Updated SourceReliability.
        """
        if source not in self._reliability:
            self._reliability[source] = SourceReliability(source=source)

        rel = self._reliability[source]
        rel.n_observations += 1

        # Check directional accuracy
        correct = (predicted_direction * actual_direction) > 0
        alpha = 0.05  # Exponential moving average rate
        rel.hit_rate = rel.hit_rate * (1 - alpha) + (1.0 if correct else 0.0) * alpha
        rel.accuracy_score = rel.hit_rate

        # Weight adjustment: boost reliable sources, penalize unreliable
        if rel.n_observations >= 10:
            rel.weight_adjustment = 0.5 + rel.accuracy_score
        else:
            rel.weight_adjustment = 1.0

        return rel

    def get_reliability(self, source: str) -> Optional[SourceReliability]:
        """Get current reliability for a source."""
        return self._reliability.get(source)

    def compare_fusions(
        self,
        results: list[FusionResult],
    ) -> FusionComparison:
        """Compare fusion results across symbols.

        Args:
            results: List of FusionResult objects.

        Returns:
            FusionComparison with rankings.
        """
        if not results:
            return FusionComparison()

        most_bullish = max(results, key=lambda r: r.fused_score)
        most_bearish = min(results, key=lambda r: r.fused_score)
        highest_conv = max(results, key=lambda r: r.fused_confidence)

        return FusionComparison(
            results=results,
            most_bullish=most_bullish.symbol,
            most_bearish=most_bearish.symbol,
            highest_conviction=highest_conv.symbol,
            avg_agreement=round(
                float(np.mean([r.agreement_ratio for r in results])), 4
            ),
        )
