"""Pair Selection and Scoring.

Screens a universe of assets for tradable pairs,
scores them on multiple criteria, and ranks by quality.
"""

import logging
from typing import Optional

import pandas as pd

from src.pairs.config import (
    SelectorConfig,
    PairsConfig,
    DEFAULT_SELECTOR_CONFIG,
    DEFAULT_CONFIG,
)
from src.pairs.models import CointegrationResult, SpreadAnalysis, PairScore
from src.pairs.cointegration import CointegrationTester
from src.pairs.spread import SpreadAnalyzer

logger = logging.getLogger(__name__)


class PairSelector:
    """Screens and ranks pairs for trading."""

    def __init__(
        self,
        config: Optional[PairsConfig] = None,
        selector_config: Optional[SelectorConfig] = None,
    ) -> None:
        self.pairs_config = config or DEFAULT_CONFIG
        self.selector_config = selector_config or self.pairs_config.selector
        self.tester = CointegrationTester(self.pairs_config.cointegration)
        self.analyzer = SpreadAnalyzer(self.pairs_config.spread)

    def screen_universe(
        self,
        prices: pd.DataFrame,
    ) -> list[PairScore]:
        """Screen all pairs in a price universe.

        Args:
            prices: DataFrame with columns as symbols, rows as dates.

        Returns:
            Ranked list of PairScore, best first.
        """
        # Step 1: Test all pairs for cointegration
        coint_results = self.tester.test_universe(prices)

        # Step 2: Filter cointegrated/weak pairs
        candidates = [r for r in coint_results if r.is_cointegrated]

        # Step 3: Analyze spreads and score
        scored: list[PairScore] = []
        for coint in candidates:
            if coint.asset_a not in prices.columns or coint.asset_b not in prices.columns:
                continue

            spread_result = self.analyzer.analyze(
                prices[coint.asset_a], prices[coint.asset_b],
                hedge_ratio=coint.hedge_ratio,
                intercept=coint.intercept,
                asset_a=coint.asset_a,
                asset_b=coint.asset_b,
            )

            score = self.score_pair(coint, spread_result)
            scored.append(score)

        # Step 4: Filter by min score
        scored = [s for s in scored if s.total_score >= self.selector_config.min_score]

        # Step 5: Sort and rank
        scored.sort(key=lambda s: s.total_score, reverse=True)
        for i, s in enumerate(scored):
            s.rank = i + 1

        # Step 6: Limit to max pairs
        return scored[: self.selector_config.max_pairs]

    def score_pair(
        self,
        coint: CointegrationResult,
        spread: SpreadAnalysis,
    ) -> PairScore:
        """Score a pair on multiple criteria.

        Args:
            coint: Cointegration test result.
            spread: Spread analysis result.

        Returns:
            PairScore with component breakdown.
        """
        cfg = self.selector_config

        # Cointegration score: lower p-value = higher score
        coint_score = max(0, (1 - coint.pvalue / 0.10)) * 100

        # Half-life score: closer to ideal (5-30 days) = higher
        hl = spread.half_life
        max_hl = self.pairs_config.spread.max_half_life
        if hl <= 0 or hl > max_hl:
            hl_score = 0.0
        elif hl <= 30:
            hl_score = 100.0 * (1 - abs(hl - 15) / 30)
        else:
            hl_score = max(0, 100.0 * (1 - (hl - 30) / (max_hl - 30)))

        # Correlation score: higher absolute correlation = higher
        corr_score = min(abs(coint.correlation) * 100, 100.0)

        # Hurst score: lower Hurst (more mean-reverting) = higher
        hurst = spread.hurst_exponent
        if hurst < 0.5:
            hurst_score = (0.5 - hurst) / 0.5 * 100
        else:
            hurst_score = 0.0

        # Weighted total
        total = (
            cfg.weight_cointegration * coint_score
            + cfg.weight_half_life * hl_score
            + cfg.weight_correlation * corr_score
            + cfg.weight_hurst * hurst_score
        )

        return PairScore(
            asset_a=coint.asset_a,
            asset_b=coint.asset_b,
            total_score=round(total, 2),
            cointegration_score=round(coint_score, 2),
            half_life_score=round(hl_score, 2),
            correlation_score=round(corr_score, 2),
            hurst_score=round(hurst_score, 2),
        )
