"""Sentiment Consensus Scoring.

Determines the degree of consensus across sentiment sources
and generates conviction-weighted consensus signals.
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
class SourceVote:
    """A source's directional vote."""
    source: str = ""
    score: float = 0.0  # -1 to +1
    direction: str = ""  # bullish, bearish, neutral
    confidence: float = 0.5
    weight: float = 1.0

    @property
    def conviction(self) -> float:
        return abs(self.score) * self.confidence


@dataclass
class ConsensusResult:
    """Consensus across sentiment sources."""
    symbol: str = ""
    consensus_direction: str = "neutral"  # bullish, bearish, neutral
    consensus_score: float = 0.0  # -1 to +1
    consensus_strength: float = 0.0  # 0-1
    unanimity: float = 0.0  # 0-1, fraction agreeing with majority
    n_bullish: int = 0
    n_bearish: int = 0
    n_neutral: int = 0
    avg_conviction: float = 0.0
    dissent_sources: list = field(default_factory=list)

    @property
    def is_unanimous(self) -> bool:
        return self.unanimity >= 0.9

    @property
    def has_strong_consensus(self) -> bool:
        return self.consensus_strength >= 0.6 and self.unanimity >= 0.6

    @property
    def is_split(self) -> bool:
        return self.unanimity < 0.5

    @property
    def total_votes(self) -> int:
        return self.n_bullish + self.n_bearish + self.n_neutral


@dataclass
class ConsensusShift:
    """Change in consensus between two periods."""
    symbol: str = ""
    prev_direction: str = "neutral"
    curr_direction: str = "neutral"
    score_change: float = 0.0
    strength_change: float = 0.0
    is_reversal: bool = False
    shift_magnitude: str = ""  # none, minor, moderate, major

    @property
    def is_significant(self) -> bool:
        return self.shift_magnitude in ("moderate", "major")


@dataclass
class MarketConsensus:
    """Market-wide consensus aggregation."""
    n_symbols: int = 0
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    neutral_pct: float = 0.0
    avg_strength: float = 0.0
    market_direction: str = "neutral"
    breadth_score: float = 0.5  # 0=all bearish, 1=all bullish
    high_conviction_count: int = 0

    @property
    def is_extreme(self) -> bool:
        return self.bullish_pct > 0.8 or self.bearish_pct > 0.8

    @property
    def is_balanced(self) -> bool:
        return 0.3 <= self.bullish_pct <= 0.7


# ---------------------------------------------------------------------------
# Consensus Scorer
# ---------------------------------------------------------------------------
class ConsensusScorer:
    """Computes consensus across sentiment sources.

    Classifies each source as bullish/bearish/neutral, then
    computes majority direction, unanimity, and conviction.
    """

    def __init__(
        self,
        bullish_threshold: float = 0.1,
        bearish_threshold: float = -0.1,
        min_votes: int = 2,
    ) -> None:
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.min_votes = min_votes

    def _classify(self, score: float) -> str:
        """Classify score as bullish, bearish, or neutral."""
        if score > self.bullish_threshold:
            return "bullish"
        elif score < self.bearish_threshold:
            return "bearish"
        return "neutral"

    def score_consensus(
        self,
        votes: list[SourceVote],
        symbol: str = "",
    ) -> ConsensusResult:
        """Compute consensus from source votes.

        Args:
            votes: List of source votes.
            symbol: Ticker symbol.

        Returns:
            ConsensusResult with direction, strength, and unanimity.
        """
        if not votes:
            return ConsensusResult(symbol=symbol)

        # Classify each vote
        for v in votes:
            v.direction = self._classify(v.score)

        n_bull = sum(1 for v in votes if v.direction == "bullish")
        n_bear = sum(1 for v in votes if v.direction == "bearish")
        n_neut = sum(1 for v in votes if v.direction == "neutral")
        total = len(votes)

        # Majority direction
        counts = {"bullish": n_bull, "bearish": n_bear, "neutral": n_neut}
        majority = max(counts, key=counts.get)

        # Unanimity: fraction agreeing with majority
        unanimity = counts[majority] / total

        # Weighted consensus score
        total_weight = sum(v.weight * v.confidence for v in votes)
        if total_weight > 0:
            consensus_score = sum(
                v.score * v.weight * v.confidence for v in votes
            ) / total_weight
        else:
            consensus_score = float(np.mean([v.score for v in votes]))

        # Consensus strength: combines unanimity and average conviction
        avg_conviction = float(np.mean([v.conviction for v in votes]))
        strength = unanimity * avg_conviction * min(1.0, total / self.min_votes)

        # Dissenting sources
        dissent = [v.source for v in votes if v.direction != majority]

        return ConsensusResult(
            symbol=symbol,
            consensus_direction=majority,
            consensus_score=round(float(np.clip(consensus_score, -1.0, 1.0)), 4),
            consensus_strength=round(min(1.0, strength), 4),
            unanimity=round(unanimity, 4),
            n_bullish=n_bull,
            n_bearish=n_bear,
            n_neutral=n_neut,
            avg_conviction=round(avg_conviction, 4),
            dissent_sources=dissent,
        )

    def detect_shift(
        self,
        prev: ConsensusResult,
        curr: ConsensusResult,
    ) -> ConsensusShift:
        """Detect shift in consensus between two periods.

        Args:
            prev: Previous period consensus.
            curr: Current period consensus.

        Returns:
            ConsensusShift describing the change.
        """
        score_change = curr.consensus_score - prev.consensus_score
        strength_change = curr.consensus_strength - prev.consensus_strength

        # Reversal: bullish -> bearish or vice versa
        is_reversal = (
            (prev.consensus_direction == "bullish" and curr.consensus_direction == "bearish")
            or (prev.consensus_direction == "bearish" and curr.consensus_direction == "bullish")
        )

        # Magnitude
        abs_change = abs(score_change)
        if abs_change < 0.1:
            magnitude = "none"
        elif abs_change < 0.3:
            magnitude = "minor"
        elif abs_change < 0.5:
            magnitude = "moderate"
        else:
            magnitude = "major"

        return ConsensusShift(
            symbol=curr.symbol,
            prev_direction=prev.consensus_direction,
            curr_direction=curr.consensus_direction,
            score_change=round(score_change, 4),
            strength_change=round(strength_change, 4),
            is_reversal=is_reversal,
            shift_magnitude=magnitude,
        )

    def market_consensus(
        self,
        results: list[ConsensusResult],
    ) -> MarketConsensus:
        """Aggregate consensus across all symbols for market view.

        Args:
            results: List of per-symbol consensus results.

        Returns:
            MarketConsensus with market-wide sentiment breadth.
        """
        if not results:
            return MarketConsensus()

        n = len(results)
        n_bull = sum(1 for r in results if r.consensus_direction == "bullish")
        n_bear = sum(1 for r in results if r.consensus_direction == "bearish")
        n_neut = n - n_bull - n_bear

        bull_pct = n_bull / n
        bear_pct = n_bear / n
        neut_pct = n_neut / n

        avg_strength = float(np.mean([r.consensus_strength for r in results]))

        # Market direction
        if bull_pct > 0.6:
            direction = "bullish"
        elif bear_pct > 0.6:
            direction = "bearish"
        else:
            direction = "neutral"

        # Breadth: 0=all bearish, 1=all bullish
        breadth = (bull_pct - bear_pct + 1.0) / 2.0

        high_conv = sum(1 for r in results if r.has_strong_consensus)

        return MarketConsensus(
            n_symbols=n,
            bullish_pct=round(bull_pct, 4),
            bearish_pct=round(bear_pct, 4),
            neutral_pct=round(neut_pct, 4),
            avg_strength=round(avg_strength, 4),
            market_direction=direction,
            breadth_score=round(breadth, 4),
            high_conviction_count=high_conv,
        )
