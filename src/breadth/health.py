"""Market Health Scorer.

Combines multiple breadth indicators into a composite
market health score (0-100) with classification levels.
"""

import logging
from datetime import date
from typing import Optional

from src.breadth.config import (
    HealthConfig,
    MarketHealthLevel,
    DEFAULT_HEALTH_CONFIG,
)
from src.breadth.models import (
    BreadthSnapshot,
    MarketHealth,
    SectorBreadth,
    BreadthSignal,
)

logger = logging.getLogger(__name__)


class HealthScorer:
    """Computes composite market health from breadth indicators.

    Weights individual indicator scores and produces a 0-100
    composite with a classification level.
    """

    def __init__(self, config: Optional[HealthConfig] = None) -> None:
        self.config = config or DEFAULT_HEALTH_CONFIG

    def score(
        self,
        snapshot: BreadthSnapshot,
        sector_breadth: Optional[list[SectorBreadth]] = None,
    ) -> MarketHealth:
        """Compute market health from a breadth snapshot.

        Args:
            snapshot: Current breadth snapshot.
            sector_breadth: Optional sector-level breadth data.

        Returns:
            MarketHealth assessment.
        """
        ad_score = self._score_ad(snapshot)
        nhnl_score = self._score_nhnl(snapshot)
        mcclellan_score = self._score_mcclellan(snapshot)
        thrust_score = self._score_thrust(snapshot)
        volume_score = self._score_volume(snapshot)

        # Weighted composite
        composite = (
            ad_score * self.config.ad_weight
            + nhnl_score * self.config.nhnl_weight
            + mcclellan_score * self.config.mcclellan_weight
            + thrust_score * self.config.thrust_weight
            + volume_score * self.config.volume_weight
        )
        composite = max(0.0, min(100.0, composite))

        level = self._classify(composite)
        summary = self._generate_summary(composite, level, snapshot)

        return MarketHealth(
            date=snapshot.date,
            score=round(composite, 1),
            level=level,
            ad_score=round(ad_score, 1),
            nhnl_score=round(nhnl_score, 1),
            mcclellan_score=round(mcclellan_score, 1),
            thrust_score=round(thrust_score, 1),
            volume_score=round(volume_score, 1),
            signals=list(snapshot.signals),
            sector_breadth=sector_breadth or [],
            summary=summary,
        )

    def _score_ad(self, snapshot: BreadthSnapshot) -> float:
        """Score advance-decline (0-100)."""
        ad = snapshot.advance_decline
        if not ad:
            return 50.0

        # Map breadth_pct (0-1) to (0-100)
        # 0.5 = neutral (50), 0.7+ = very bullish, 0.3- = very bearish
        pct = ad.breadth_pct
        score = pct * 100.0

        # Boost for strong ratios
        if ad.ad_ratio > 2.0:
            score = min(100.0, score + 10)
        elif ad.ad_ratio < 0.5:
            score = max(0.0, score - 10)

        return score

    def _score_nhnl(self, snapshot: BreadthSnapshot) -> float:
        """Score new highs/lows (0-100)."""
        nhnl = snapshot.new_highs_lows
        if not nhnl:
            return 50.0

        total = nhnl.new_highs + nhnl.new_lows
        if total == 0:
            return 50.0

        # Ratio of highs to total
        ratio = nhnl.new_highs / total
        return ratio * 100.0

    def _score_mcclellan(self, snapshot: BreadthSnapshot) -> float:
        """Score McClellan Oscillator (0-100)."""
        mc = snapshot.mcclellan
        if not mc:
            return 50.0

        # Map oscillator from [-150, 150] to [0, 100]
        # 0 = neutral (50)
        osc = mc.oscillator
        clamped = max(-150.0, min(150.0, osc))
        score = 50.0 + (clamped / 150.0) * 50.0
        return score

    def _score_thrust(self, snapshot: BreadthSnapshot) -> float:
        """Score breadth thrust (0-100)."""
        thrust = snapshot.thrust
        if not thrust:
            return 50.0

        if thrust.thrust_active:
            return 95.0  # Very bullish

        # Map EMA: 0.3 = bearish (20), 0.5 = neutral (50), 0.65+ = bullish (80)
        ema = thrust.breadth_ema
        if ema >= 0.65:
            return 85.0
        elif ema >= 0.50:
            return 50.0 + (ema - 0.50) / 0.15 * 35.0
        elif ema >= 0.35:
            return 20.0 + (ema - 0.35) / 0.15 * 30.0
        else:
            return max(0.0, ema / 0.35 * 20.0)

    def _score_volume(self, snapshot: BreadthSnapshot) -> float:
        """Score up/down volume ratio (0-100)."""
        ad = snapshot.advance_decline
        if not ad or ad.down_volume == 0:
            return 50.0

        ratio = ad.volume_ratio
        # Map: 0.5 = bearish (20), 1.0 = neutral (50), 2.0+ = bullish (80+)
        if ratio >= 2.0:
            return min(100.0, 80.0 + (ratio - 2.0) * 5.0)
        elif ratio >= 1.0:
            return 50.0 + (ratio - 1.0) * 30.0
        else:
            return max(0.0, ratio * 50.0)

    def _classify(self, score: float) -> MarketHealthLevel:
        """Classify score into health level."""
        if score >= self.config.very_bullish_threshold:
            return MarketHealthLevel.VERY_BULLISH
        elif score >= self.config.bullish_threshold:
            return MarketHealthLevel.BULLISH
        elif score >= self.config.neutral_threshold:
            return MarketHealthLevel.NEUTRAL
        elif score >= self.config.bearish_threshold:
            return MarketHealthLevel.BEARISH
        else:
            return MarketHealthLevel.VERY_BEARISH

    def _generate_summary(
        self,
        score: float,
        level: MarketHealthLevel,
        snapshot: BreadthSnapshot,
    ) -> str:
        """Generate a text summary of market health."""
        parts = [f"Market health: {level.value.replace('_', ' ').title()} ({score:.0f}/100)."]

        ad = snapshot.advance_decline
        if ad:
            parts.append(f"AD: {ad.advancing} adv / {ad.declining} dec (ratio {ad.ad_ratio:.2f}).")

        mc = snapshot.mcclellan
        if mc:
            parts.append(f"McClellan: {mc.oscillator:.0f}.")

        if snapshot.signals:
            sig_names = [s.value.replace("_", " ") for s in snapshot.signals]
            parts.append(f"Signals: {', '.join(sig_names)}.")

        return " ".join(parts)
