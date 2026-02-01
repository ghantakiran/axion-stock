"""Liquidity Scoring.

Computes composite liquidity scores from spread, volume, and impact
metrics. Classifies assets into liquidity tiers and ranks universes.
"""

import logging
from datetime import date
from typing import Optional

from src.liquidity.config import (
    ScoringConfig,
    LiquidityLevel,
    DEFAULT_SCORING_CONFIG,
)
from src.liquidity.models import (
    SpreadAnalysis,
    VolumeAnalysis,
    MarketImpact,
    LiquidityScore,
)

logger = logging.getLogger(__name__)


class LiquidityScorer:
    """Scores and classifies asset liquidity."""

    def __init__(self, config: Optional[ScoringConfig] = None) -> None:
        self.config = config or DEFAULT_SCORING_CONFIG

    def score(
        self,
        spread: SpreadAnalysis,
        volume: VolumeAnalysis,
        impact: Optional[MarketImpact] = None,
        price: float = 0.0,
    ) -> LiquidityScore:
        """Compute composite liquidity score.

        Args:
            spread: Spread analysis results.
            volume: Volume analysis results.
            impact: Optional market impact estimate.
            price: Current price for dollar volume.

        Returns:
            LiquidityScore with sub-component scores.
        """
        spread_score = self._score_spread(spread)
        volume_score = self._score_volume(volume)
        impact_score = self._score_impact(impact) if impact else 50.0

        composite = (
            self.config.spread_weight * spread_score
            + self.config.volume_weight * volume_score
            + self.config.impact_weight * impact_score
        )

        level = self._classify(composite)

        # Max safe shares from impact
        max_shares = impact.max_safe_size if impact else 0
        max_dollars = max_shares * price if price > 0 else 0.0

        return LiquidityScore(
            symbol=spread.symbol or volume.symbol,
            score=round(composite, 1),
            level=level,
            spread_score=round(spread_score, 1),
            volume_score=round(volume_score, 1),
            impact_score=round(impact_score, 1),
            max_safe_shares=max_shares,
            max_safe_dollars=round(max_dollars, 0),
            date=date.today(),
        )

    def _score_spread(self, spread: SpreadAnalysis) -> float:
        """Score spread quality (0-100, higher = tighter = better)."""
        bps = spread.spread_bps
        if bps <= 0:
            return 50.0

        # Tight spreads score high
        if bps <= 1:
            return 100.0
        elif bps <= 5:
            return 90.0 - (bps - 1) * 2.5
        elif bps <= 20:
            return 80.0 - (bps - 5) * 2.0
        elif bps <= 50:
            return 50.0 - (bps - 20) * 1.0
        elif bps <= 100:
            return 20.0 - (bps - 50) * 0.3
        else:
            return max(0.0, 5.0 - (bps - 100) * 0.05)

    def _score_volume(self, volume: VolumeAnalysis) -> float:
        """Score volume quality (0-100, higher = more liquid)."""
        adv = volume.avg_dollar_volume
        if adv <= 0:
            return 0.0

        # Score based on average dollar volume
        if adv >= 500_000_000:
            return 100.0
        elif adv >= 100_000_000:
            return 90.0 + (adv - 100_000_000) / 400_000_000 * 10
        elif adv >= 50_000_000:
            return 80.0 + (adv - 50_000_000) / 50_000_000 * 10
        elif adv >= 10_000_000:
            return 60.0 + (adv - 10_000_000) / 40_000_000 * 20
        elif adv >= 1_000_000:
            return 30.0 + (adv - 1_000_000) / 9_000_000 * 30
        elif adv >= 100_000:
            return 10.0 + (adv - 100_000) / 900_000 * 20
        else:
            return max(0.0, adv / 100_000 * 10)

    def _score_impact(self, impact: MarketImpact) -> float:
        """Score market impact (0-100, lower cost = higher score)."""
        bps = impact.total_cost_bps
        if bps <= 0:
            return 100.0

        if bps <= 1:
            return 100.0
        elif bps <= 5:
            return 90.0 - (bps - 1) * 2.5
        elif bps <= 20:
            return 80.0 - (bps - 5) * 2.0
        elif bps <= 50:
            return 50.0 - (bps - 20) * 1.0
        elif bps <= 100:
            return 20.0 - (bps - 50) * 0.3
        else:
            return max(0.0, 5.0 - (bps - 100) * 0.05)

    def _classify(self, score: float) -> LiquidityLevel:
        """Classify composite score into level."""
        if score >= self.config.very_high_threshold:
            return LiquidityLevel.VERY_HIGH
        elif score >= self.config.high_threshold:
            return LiquidityLevel.HIGH
        elif score >= self.config.medium_threshold:
            return LiquidityLevel.MEDIUM
        elif score >= self.config.low_threshold:
            return LiquidityLevel.LOW
        else:
            return LiquidityLevel.VERY_LOW

    def rank_universe(
        self,
        scores: list[LiquidityScore],
    ) -> list[LiquidityScore]:
        """Rank assets by liquidity score (descending).

        Args:
            scores: List of LiquidityScore objects.

        Returns:
            Sorted list, most liquid first.
        """
        return sorted(scores, key=lambda s: s.score, reverse=True)
