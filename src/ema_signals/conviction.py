"""Conviction scoring system for EMA cloud trade signals.

Scores each signal 0-100 based on 6 weighted factors:
- Cloud alignment (25): How many cloud layers agree
- MTF confluence (25): How many timeframes confirm
- Volume confirmation (15): Current vs average volume
- Cloud thickness (10): Wider cloud = stronger support/resistance
- Candle quality (10): Full-body candles vs wicks/dojis
- Factor score (15): Integration with Axion multi-factor model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.ema_signals.clouds import CloudState
from src.ema_signals.detector import TradeSignal


@dataclass
class ConvictionScore:
    """Detailed breakdown of a signal's conviction score."""

    total: int
    cloud_alignment: float
    mtf_confluence: float
    volume_confirmation: float
    cloud_thickness: float
    candle_quality: float
    factor_score: float
    breakdown: dict = field(default_factory=dict)

    @property
    def level(self) -> str:
        """Human-readable conviction level."""
        if self.total >= 75:
            return "high"
        elif self.total >= 50:
            return "medium"
        elif self.total >= 25:
            return "low"
        return "none"


# ═══════════════════════════════════════════════════════════════════════
# Conviction Scorer
# ═══════════════════════════════════════════════════════════════════════


class ConvictionScorer:
    """Score signal conviction using multi-factor criteria.

    Weights (total = 100):
        cloud_alignment: 25
        mtf_confluence:  25
        volume:          15
        cloud_thickness: 10
        candle_quality:  10
        factor_score:    15
    """

    WEIGHT_CLOUD_ALIGNMENT = 25.0
    WEIGHT_MTF_CONFLUENCE = 25.0
    WEIGHT_VOLUME = 15.0
    WEIGHT_THICKNESS = 10.0
    WEIGHT_CANDLE = 10.0
    WEIGHT_FACTOR = 15.0

    def score(
        self,
        signal: TradeSignal,
        volume_data: Optional[dict] = None,
        factor_scores: Optional[dict] = None,
    ) -> ConvictionScore:
        """Compute conviction score for a trade signal.

        Args:
            signal: The trade signal to score.
            volume_data: Dict with "current_volume" and "avg_volume" keys.
            factor_scores: Dict with "composite" key (0-1 range).

        Returns:
            ConvictionScore with detailed breakdown.
        """
        cloud_pts = self._score_cloud_alignment(signal.cloud_states, signal.direction)
        mtf_pts = self._score_mtf_confluence(signal.metadata)
        vol_pts = self._score_volume(volume_data)
        thick_pts = self._score_thickness(signal.cloud_states)
        candle_pts = self._score_candle_quality(signal.metadata)
        factor_pts = self._score_factor(factor_scores)

        total = int(
            min(100, cloud_pts + mtf_pts + vol_pts + thick_pts + candle_pts + factor_pts)
        )

        return ConvictionScore(
            total=total,
            cloud_alignment=round(cloud_pts, 2),
            mtf_confluence=round(mtf_pts, 2),
            volume_confirmation=round(vol_pts, 2),
            cloud_thickness=round(thick_pts, 2),
            candle_quality=round(candle_pts, 2),
            factor_score=round(factor_pts, 2),
            breakdown={
                "aligned_clouds": sum(
                    1
                    for cs in signal.cloud_states
                    if (cs.is_bullish and signal.direction == "long")
                    or (not cs.is_bullish and signal.direction == "short")
                ),
                "total_clouds": len(signal.cloud_states),
                "volume_ratio": (
                    volume_data.get("current_volume", 0)
                    / max(volume_data.get("avg_volume", 1), 1)
                    if volume_data
                    else 0
                ),
            },
        )

    def _score_cloud_alignment(
        self, cloud_states: list[CloudState], direction: str
    ) -> float:
        """Score based on how many cloud layers agree with signal direction."""
        if not cloud_states:
            return 0.0

        aligned = 0
        for cs in cloud_states:
            if direction == "long" and cs.is_bullish and cs.price_above:
                aligned += 1
            elif direction == "short" and not cs.is_bullish and cs.price_below:
                aligned += 1
            elif direction == "long" and cs.is_bullish:
                aligned += 0.5
            elif direction == "short" and not cs.is_bullish:
                aligned += 0.5

        ratio = aligned / len(cloud_states)
        return ratio * self.WEIGHT_CLOUD_ALIGNMENT

    def _score_mtf_confluence(self, metadata: dict) -> float:
        """Score based on multi-timeframe agreement.

        Populated by MTFEngine before scoring; reads metadata["confirming_timeframes"].
        """
        confirming = metadata.get("confirming_timeframes", 1)
        total_tf = metadata.get("total_timeframes", 5)

        if confirming >= 4:
            return self.WEIGHT_MTF_CONFLUENCE
        elif confirming >= 3:
            return self.WEIGHT_MTF_CONFLUENCE * 0.8
        elif confirming >= 2:
            return self.WEIGHT_MTF_CONFLUENCE * 0.5
        return self.WEIGHT_MTF_CONFLUENCE * 0.2

    def _score_volume(self, volume_data: Optional[dict]) -> float:
        """Score based on volume confirmation."""
        if not volume_data:
            return self.WEIGHT_VOLUME * 0.3  # Neutral if no data

        current = volume_data.get("current_volume", 0)
        avg = volume_data.get("avg_volume", 1)
        if avg <= 0:
            return 0.0

        ratio = current / avg
        if ratio >= 2.0:
            return self.WEIGHT_VOLUME
        elif ratio >= 1.5:
            return self.WEIGHT_VOLUME * 0.8
        elif ratio >= 1.0:
            return self.WEIGHT_VOLUME * 0.5
        return self.WEIGHT_VOLUME * 0.2

    def _score_thickness(self, cloud_states: list[CloudState]) -> float:
        """Score based on cloud thickness (wider = stronger support/resistance)."""
        if not cloud_states:
            return 0.0

        avg_thickness = np.mean([cs.thickness for cs in cloud_states])

        # Thickness as % of price: >1% = thick, <0.2% = thin
        if avg_thickness >= 0.01:
            return self.WEIGHT_THICKNESS
        elif avg_thickness >= 0.005:
            return self.WEIGHT_THICKNESS * 0.7
        elif avg_thickness >= 0.002:
            return self.WEIGHT_THICKNESS * 0.4
        return self.WEIGHT_THICKNESS * 0.1

    def _score_candle_quality(self, metadata: dict) -> float:
        """Score based on candle pattern quality.

        Full-body candles closing through cloud score higher than
        wicks/dojis. Reads metadata["body_ratio"] if available.
        """
        body_ratio = metadata.get("body_ratio", 0.5)

        # body_ratio = abs(close - open) / (high - low); 1.0 = full body
        if body_ratio >= 0.7:
            return self.WEIGHT_CANDLE
        elif body_ratio >= 0.5:
            return self.WEIGHT_CANDLE * 0.7
        elif body_ratio >= 0.3:
            return self.WEIGHT_CANDLE * 0.4
        return self.WEIGHT_CANDLE * 0.1

    def _score_factor(self, factor_scores: Optional[dict]) -> float:
        """Score based on Axion factor model composite score.

        Maps composite score (0-1 range) to 0-15 conviction points.
        """
        if not factor_scores:
            return self.WEIGHT_FACTOR * 0.3  # Neutral if unavailable

        composite = factor_scores.get("composite", 0.5)
        return composite * self.WEIGHT_FACTOR
