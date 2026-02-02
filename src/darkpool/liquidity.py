"""Dark Pool Liquidity Estimation.

Estimates hidden liquidity from dark pool activity,
computes fill rates, and scores accessibility.
"""

import logging
from typing import Optional

import numpy as np

from src.darkpool.config import LiquidityConfig, LiquidityLevel, DEFAULT_LIQUIDITY_CONFIG
from src.darkpool.models import DarkPoolVolume, DarkPrint, DarkLiquidity

logger = logging.getLogger(__name__)


class LiquidityEstimator:
    """Estimates dark pool liquidity and accessibility."""

    def __init__(self, config: Optional[LiquidityConfig] = None) -> None:
        self.config = config or DEFAULT_LIQUIDITY_CONFIG

    def estimate(
        self,
        volume_history: list[DarkPoolVolume],
        prints: Optional[list[DarkPrint]] = None,
        symbol: str = "",
    ) -> DarkLiquidity:
        """Estimate dark pool liquidity.

        Args:
            volume_history: Historical dark pool volume records.
            prints: Optional recent prints for depth estimation.
            symbol: Stock symbol.

        Returns:
            DarkLiquidity with score and fill rates.
        """
        if not volume_history:
            return self._empty_estimate(symbol)

        recent = volume_history[-self.config.fill_rate_window:]

        # Component scores
        vol_share_score = self._volume_share_score(recent)
        fill_rates = self._estimate_fill_rates(recent, prints)
        fill_rate_score = self._fill_rate_score(fill_rates)
        depth = self._estimate_depth(recent, prints)
        depth_score = self._depth_score(depth, recent)
        consistency = self._consistency_score(recent)

        # Weighted composite
        w = self.config.score_weights
        liquidity_score = (
            w["volume_share"] * vol_share_score
            + w["fill_rate"] * fill_rate_score
            + w["depth"] * depth_score
            + w["consistency"] * consistency
        )
        liquidity_score = round(min(max(liquidity_score, 0.0), 1.0), 4)

        # Classify level
        level = self._classify_level(liquidity_score)

        # Dark-lit ratio
        total_dark = sum(r.dark_volume for r in recent)
        total_lit = sum(r.lit_volume for r in recent)
        dark_lit_ratio = total_dark / total_lit if total_lit > 0 else 0.0

        return DarkLiquidity(
            symbol=symbol,
            liquidity_score=liquidity_score,
            level=level,
            estimated_depth=round(depth, 2),
            dark_lit_ratio=round(dark_lit_ratio, 4),
            fill_rates=fill_rates,
            consistency=round(consistency, 4),
        )

    def _volume_share_score(self, records: list[DarkPoolVolume]) -> float:
        """Score based on average dark pool market share."""
        shares = [r.dark_share for r in records if r.total_volume > 0]
        if not shares:
            return 0.0
        avg = np.mean(shares)
        # Normalize: 40%+ dark share -> score 1.0
        return float(min(avg / 0.40, 1.0))

    def _estimate_fill_rates(
        self,
        records: list[DarkPoolVolume],
        prints: Optional[list[DarkPrint]] = None,
    ) -> dict:
        """Estimate fill rates at various order sizes.

        Heuristic: probability of filling scales with dark volume
        and decreases with order size.
        """
        if not records:
            return {}

        avg_dark_vol = float(np.mean([r.dark_volume for r in records]))
        if avg_dark_vol == 0:
            return {str(s): 0.0 for s in self.config.depth_levels}

        fill_rates = {}
        for size in self.config.depth_levels:
            # Simple model: fill probability = 1 - (size / dark_vol)^0.5
            ratio = size / avg_dark_vol
            rate = max(0.0, 1.0 - ratio ** 0.5)
            fill_rates[str(size)] = round(rate, 4)

        return fill_rates

    def _fill_rate_score(self, fill_rates: dict) -> float:
        """Score from average fill rates."""
        if not fill_rates:
            return 0.0
        return float(np.mean(list(fill_rates.values())))

    def _estimate_depth(
        self,
        records: list[DarkPoolVolume],
        prints: Optional[list[DarkPrint]] = None,
    ) -> float:
        """Estimate effective dark pool depth in shares.

        Uses average dark volume as proxy, adjusted by
        print data if available.
        """
        avg_dark_vol = float(np.mean([r.dark_volume for r in records]))

        if prints:
            # Use median print size as depth indicator
            sizes = [p.size for p in prints]
            if sizes:
                median_size = float(np.median(sizes))
                # Blend: 70% volume-based, 30% print-based
                return 0.7 * avg_dark_vol + 0.3 * median_size * len(prints)

        return avg_dark_vol

    def _depth_score(
        self, depth: float, records: list[DarkPoolVolume]
    ) -> float:
        """Score depth relative to total volume."""
        if not records:
            return 0.0
        avg_total = float(np.mean([r.total_volume for r in records]))
        if avg_total == 0:
            return 0.0
        ratio = depth / avg_total
        return float(min(ratio / 0.5, 1.0))  # 50% depth -> score 1.0

    def _consistency_score(self, records: list[DarkPoolVolume]) -> float:
        """Score based on how consistent dark volume is day-to-day.

        Lower coefficient of variation -> higher consistency.
        """
        dark_vols = [r.dark_volume for r in records if r.dark_volume > 0]
        if len(dark_vols) < 2:
            return 0.0

        mean_v = np.mean(dark_vols)
        if mean_v == 0:
            return 0.0
        cv = np.std(dark_vols) / mean_v
        # CV of 0 -> score 1.0, CV of 1+ -> score 0.0
        return float(max(0.0, 1.0 - cv))

    def _classify_level(self, score: float) -> LiquidityLevel:
        """Classify liquidity level from score."""
        if score >= self.config.deep_threshold:
            return LiquidityLevel.DEEP
        elif score >= self.config.moderate_threshold:
            return LiquidityLevel.MODERATE
        elif score >= self.config.shallow_threshold:
            return LiquidityLevel.SHALLOW
        return LiquidityLevel.DRY

    def _empty_estimate(self, symbol: str) -> DarkLiquidity:
        return DarkLiquidity(
            symbol=symbol,
            liquidity_score=0.0,
            level=LiquidityLevel.DRY,
        )
