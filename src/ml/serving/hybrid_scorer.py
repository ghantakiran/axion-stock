"""Hybrid Score Blending.

Blends rule-based factor scores (PRD-02) with ML predictions
for improved stock ranking.
"""

import logging
from typing import Optional

import pandas as pd

from src.ml.config import HybridScoringConfig

logger = logging.getLogger(__name__)


class HybridScorer:
    """Blend rule-based and ML scores.

    Combines the factor engine's composite score with the ML model's
    predicted ranking, weighted by a configurable blend parameter.

    Includes automatic fallback to rules-only if ML model degrades.

    Example:
        scorer = HybridScorer(ml_weight=0.30)
        hybrid = scorer.compute_hybrid_scores(
            rule_scores=factor_composites,
            ml_scores=ml_rankings,
        )
    """

    def __init__(self, config: Optional[HybridScoringConfig] = None):
        self.config = config or HybridScoringConfig()
        self._ml_active = True
        self._ml_ic: float = 0.0

    def compute_hybrid_scores(
        self,
        rule_scores: pd.Series,
        ml_scores: Optional[pd.Series] = None,
        ml_weight: Optional[float] = None,
    ) -> pd.Series:
        """Compute blended hybrid scores.

        Args:
            rule_scores: Factor engine composite scores (0-1).
            ml_scores: ML model predicted scores (0-1).
            ml_weight: Override weight for ML (0-1).

        Returns:
            Series of hybrid scores (0-1).
        """
        weight = ml_weight if ml_weight is not None else self.config.ml_weight

        # Fallback to rules only if ML not available or degraded
        if ml_scores is None or ml_scores.empty:
            return rule_scores

        if not self._ml_active and self.config.fallback_to_rules:
            logger.info("ML model degraded, using rules only")
            return rule_scores

        # Align indices
        common = rule_scores.index.intersection(ml_scores.index)
        if len(common) == 0:
            return rule_scores

        rules = rule_scores.loc[common]
        ml = ml_scores.loc[common]

        # Normalize both to 0-1 range
        rules_norm = self._normalize(rules)
        ml_norm = self._normalize(ml)

        # Blend
        hybrid = (1 - weight) * rules_norm + weight * ml_norm

        # Re-normalize
        hybrid = self._normalize(hybrid)

        # Append any symbols only in rules
        rules_only = rule_scores.index.difference(common)
        if len(rules_only) > 0:
            hybrid = pd.concat([hybrid, rule_scores.loc[rules_only]])

        return hybrid

    def compute_hybrid_score_single(
        self,
        rule_score: float,
        ml_score: Optional[float] = None,
        ml_weight: Optional[float] = None,
    ) -> float:
        """Compute hybrid score for a single stock.

        Args:
            rule_score: Factor engine composite score.
            ml_score: ML model score.
            ml_weight: Override weight.

        Returns:
            Blended score.
        """
        weight = ml_weight if ml_weight is not None else self.config.ml_weight

        if ml_score is None or not self._ml_active:
            return rule_score

        return (1 - weight) * rule_score + weight * ml_score

    def update_ml_performance(self, ic: float) -> None:
        """Update ML model performance metric.

        If IC drops below threshold, ML is deactivated.

        Args:
            ic: Current Information Coefficient of ML model.
        """
        self._ml_ic = ic

        if ic < self.config.min_ic_for_ml:
            if self._ml_active:
                logger.warning(f"ML IC ({ic:.4f}) below threshold ({self.config.min_ic_for_ml}), deactivating ML")
                self._ml_active = False
        else:
            if not self._ml_active:
                logger.info(f"ML IC ({ic:.4f}) recovered, reactivating ML")
                self._ml_active = True

    @property
    def is_ml_active(self) -> bool:
        return self._ml_active

    @property
    def current_ml_weight(self) -> float:
        if not self._ml_active:
            return 0.0
        return self.config.ml_weight

    def _normalize(self, series: pd.Series) -> pd.Series:
        """Normalize to 0-1 range."""
        smin = series.min()
        smax = series.max()
        if smax > smin:
            return (series - smin) / (smax - smin)
        return series * 0 + 0.5
