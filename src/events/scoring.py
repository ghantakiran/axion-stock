"""Earnings Quality Scoring.

Quantitative scoring of earnings events based on surprise
consistency, guidance revisions, revenue quality, and
forward-looking indicators.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.events.config import EarningsConfig
from src.events.models import EarningsEvent, EarningsSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class EarningsQualityScore:
    """Comprehensive earnings quality assessment."""
    symbol: str = ""
    quarter: str = ""
    overall_score: float = 0.0  # -1 to +1

    # Component scores
    surprise_score: float = 0.0
    consistency_score: float = 0.0
    revenue_quality_score: float = 0.0
    guidance_score: float = 0.0
    beat_breadth_score: float = 0.0

    # Context
    eps_surprise_pct: float = 0.0
    revenue_surprise_pct: float = 0.0
    beat_rate: float = 0.0
    consecutive_beats: int = 0

    @property
    def is_high_quality(self) -> bool:
        return self.overall_score >= 0.6

    @property
    def is_low_quality(self) -> bool:
        return self.overall_score <= -0.4

    @property
    def grade(self) -> str:
        if self.overall_score >= 0.7:
            return "A"
        elif self.overall_score >= 0.4:
            return "B"
        elif self.overall_score >= 0.1:
            return "C"
        elif self.overall_score >= -0.2:
            return "D"
        return "F"


@dataclass
class GuidanceRevision:
    """Guidance revision details."""
    symbol: str = ""
    metric: str = "eps"  # eps, revenue
    prior_low: float = 0.0
    prior_high: float = 0.0
    new_low: float = 0.0
    new_high: float = 0.0

    @property
    def revision_pct(self) -> float:
        prior_mid = (self.prior_low + self.prior_high) / 2
        new_mid = (self.new_low + self.new_high) / 2
        if abs(prior_mid) < 1e-10:
            return 0.0
        return (new_mid - prior_mid) / abs(prior_mid)

    @property
    def is_raise(self) -> bool:
        return self.revision_pct > 0.01

    @property
    def is_cut(self) -> bool:
        return self.revision_pct < -0.01

    @property
    def range_narrowed(self) -> bool:
        prior_range = self.prior_high - self.prior_low
        new_range = self.new_high - self.new_low
        return new_range < prior_range


@dataclass
class EarningsScorecardSummary:
    """Summary scorecard across multiple quarters."""
    symbol: str = ""
    n_quarters: int = 0
    avg_quality_score: float = 0.0
    score_trend: float = 0.0  # Positive = improving
    best_quarter: str = ""
    best_score: float = 0.0
    worst_quarter: str = ""
    worst_score: float = 0.0
    consistency: float = 0.0  # Low std dev = consistent

    @property
    def is_improving(self) -> bool:
        return self.score_trend > 0.05


# ---------------------------------------------------------------------------
# Earnings Scorer
# ---------------------------------------------------------------------------
class EarningsScorer:
    """Scores earnings quality on multiple dimensions."""

    def __init__(self, config: Optional[EarningsConfig] = None) -> None:
        self.config = config or EarningsConfig()

    def score_event(
        self,
        event: EarningsEvent,
        summary: Optional[EarningsSummary] = None,
        guidance: Optional[GuidanceRevision] = None,
    ) -> EarningsQualityScore:
        """Score a single earnings event.

        Args:
            event: The earnings event to score.
            summary: Historical earnings summary for consistency.
            guidance: Guidance revision if applicable.

        Returns:
            EarningsQualityScore with component scores.
        """
        # 1. Surprise score: magnitude and direction
        surprise_score = self._score_surprise(event)

        # 2. Consistency: historical beat pattern
        consistency_score = self._score_consistency(summary)

        # 3. Revenue quality: revenue beat in addition to EPS
        revenue_score = self._score_revenue_quality(event)

        # 4. Guidance: revision direction and magnitude
        guidance_score = self._score_guidance(guidance)

        # 5. Beat breadth: both EPS and revenue beat together
        breadth_score = self._score_beat_breadth(event)

        # Weighted composite
        weights = {
            "surprise": 0.30,
            "consistency": 0.20,
            "revenue": 0.20,
            "guidance": 0.15,
            "breadth": 0.15,
        }

        overall = (
            surprise_score * weights["surprise"]
            + consistency_score * weights["consistency"]
            + revenue_score * weights["revenue"]
            + guidance_score * weights["guidance"]
            + breadth_score * weights["breadth"]
        )

        return EarningsQualityScore(
            symbol=event.symbol,
            quarter=event.fiscal_quarter,
            overall_score=round(overall, 4),
            surprise_score=round(surprise_score, 4),
            consistency_score=round(consistency_score, 4),
            revenue_quality_score=round(revenue_score, 4),
            guidance_score=round(guidance_score, 4),
            beat_breadth_score=round(breadth_score, 4),
            eps_surprise_pct=round(event.eps_surprise, 4),
            revenue_surprise_pct=round(event.revenue_surprise, 4),
            beat_rate=round(summary.beat_rate if summary else 0.0, 4),
            consecutive_beats=summary.streak if summary and summary.streak > 0 else 0,
        )

    def scorecard(
        self,
        scores: list[EarningsQualityScore],
    ) -> EarningsScorecardSummary:
        """Summarize quality scores across multiple quarters.

        Args:
            scores: List of per-quarter quality scores.

        Returns:
            EarningsScorecardSummary with trends and averages.
        """
        if not scores:
            return EarningsScorecardSummary()

        values = [s.overall_score for s in scores]
        best = max(scores, key=lambda s: s.overall_score)
        worst = min(scores, key=lambda s: s.overall_score)

        # Trend: linear regression slope
        if len(values) >= 2:
            x = np.arange(len(values))
            slope = float(np.polyfit(x, values, 1)[0])
        else:
            slope = 0.0

        return EarningsScorecardSummary(
            symbol=scores[0].symbol,
            n_quarters=len(scores),
            avg_quality_score=round(float(np.mean(values)), 4),
            score_trend=round(slope, 4),
            best_quarter=best.quarter,
            best_score=best.overall_score,
            worst_quarter=worst.quarter,
            worst_score=worst.overall_score,
            consistency=round(1 - float(np.std(values)), 4),
        )

    def _score_surprise(self, event: EarningsEvent) -> float:
        """Score based on EPS surprise magnitude."""
        surprise = event.eps_surprise
        # Map surprise to [-1, 1] using tanh
        return float(np.tanh(surprise * 10))

    def _score_consistency(self, summary: Optional[EarningsSummary]) -> float:
        """Score based on historical beat consistency."""
        if not summary or summary.total_reports < 2:
            return 0.0
        # Beat rate above 75% = high consistency
        beat_rate = summary.beat_rate
        score = (beat_rate - 0.5) * 2  # Map 0.5-1.0 → 0-1
        # Bonus for streaks
        if summary.streak >= 4:
            score = min(1.0, score + 0.2)
        return max(-1.0, min(1.0, score))

    def _score_revenue_quality(self, event: EarningsEvent) -> float:
        """Score based on revenue surprise (top-line growth)."""
        rev_surprise = event.revenue_surprise
        return float(np.tanh(rev_surprise * 8))

    def _score_guidance(self, guidance: Optional[GuidanceRevision]) -> float:
        """Score based on guidance revision."""
        if not guidance:
            return 0.0
        revision = guidance.revision_pct
        score = float(np.tanh(revision * 5))
        # Bonus for narrowing range (higher confidence)
        if guidance.range_narrowed:
            score += 0.1 * (1 if score >= 0 else -1)
        return max(-1.0, min(1.0, score))

    def _score_beat_breadth(self, event: EarningsEvent) -> float:
        """Score based on beating on both EPS and revenue."""
        eps_beat = event.eps_surprise > self.config.beat_threshold
        rev_beat = event.revenue_surprise > 0
        eps_miss = event.eps_surprise < self.config.miss_threshold
        rev_miss = event.revenue_surprise < 0

        if eps_beat and rev_beat:
            return 0.8  # Double beat
        elif eps_beat and not rev_miss:
            return 0.4  # EPS beat, revenue okay
        elif eps_miss and rev_miss:
            return -0.8  # Double miss
        elif eps_miss and not rev_beat:
            return -0.4  # EPS miss, revenue okay
        return 0.0  # Mixed or neutral
