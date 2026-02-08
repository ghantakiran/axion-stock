"""ESG Scoring Engine."""

import logging
from typing import Optional

from src.esg.config import (
    ESGConfig,
    ESGRating,
    ESGPillar,
    ESGCategory,
    RATING_THRESHOLDS,
    PILLAR_CATEGORIES,
    DEFAULT_ESG_CONFIG,
)
from src.esg.models import (
    ESGScore,
    PillarScore,
    CarbonMetrics,
    ESGScreenResult,
    ESGPortfolioSummary,
)

logger = logging.getLogger(__name__)

# Sin stock sectors/industries
SIN_STOCK_INDUSTRIES = {"tobacco", "gambling", "alcohol", "adult_entertainment"}
FOSSIL_FUEL_INDUSTRIES = {"oil_gas", "coal", "fossil_fuels"}
WEAPONS_INDUSTRIES = {"weapons", "defense_controversial", "cluster_munitions"}


class ESGScorer:
    """Comprehensive ESG scoring engine.

    Features:
    - Composite scoring from E/S/G pillars with configurable weights
    - Letter rating assignment (AAA to CCC)
    - Controversy penalty application
    - ESG screening (sin stocks, fossil fuels, weapons)
    - Portfolio-level ESG aggregation
    - Sector-relative ranking
    """

    def __init__(self, config: Optional[ESGConfig] = None):
        self.config = config or DEFAULT_ESG_CONFIG
        self._scores: dict[str, ESGScore] = {}
        self._carbon: dict[str, CarbonMetrics] = {}

    def score_security(
        self,
        symbol: str,
        environmental: float = 50.0,
        social: float = 50.0,
        governance: float = 50.0,
        pillar_scores: Optional[list[PillarScore]] = None,
        controversies: Optional[list[str]] = None,
        sector: str = "",
    ) -> ESGScore:
        """Score a security on ESG dimensions.

        Args:
            symbol: Security symbol.
            environmental: Environmental score (0-100).
            social: Social score (0-100).
            governance: Governance score (0-100).
            pillar_scores: Detailed pillar-level scores.
            controversies: List of controversy descriptions.
            sector: Sector for relative ranking.

        Returns:
            ESGScore with composite rating.
        """
        # Clamp scores
        e = max(self.config.min_score, min(self.config.max_score, environmental))
        s = max(self.config.min_score, min(self.config.max_score, social))
        g = max(self.config.min_score, min(self.config.max_score, governance))

        # Weighted composite
        composite = (
            e * self.config.environmental_weight
            + s * self.config.social_weight
            + g * self.config.governance_weight
        )

        # Apply controversy penalty
        controversy_list = controversies or []
        controversy_score = len(controversy_list) * self.config.controversy_penalty
        composite = max(0, composite - controversy_score)

        # Determine rating
        rating = self._score_to_rating(composite)

        score = ESGScore(
            symbol=symbol,
            environmental_score=e,
            social_score=s,
            governance_score=g,
            composite_score=round(composite, 2),
            rating=rating,
            pillar_scores=pillar_scores or [],
            controversies=controversy_list,
            controversy_score=controversy_score,
            sector=sector,
        )

        self._scores[symbol] = score
        return score

    def screen_security(
        self,
        symbol: str,
        industry: str = "",
        min_score: float = 0.0,
    ) -> ESGScreenResult:
        """Screen a security against ESG criteria.

        Args:
            symbol: Security symbol.
            industry: Industry classification.
            min_score: Minimum ESG score required.

        Returns:
            ESGScreenResult with pass/fail and reasons.
        """
        excluded_reasons = []
        industry_lower = industry.lower()

        if self.config.exclude_sin_stocks and industry_lower in SIN_STOCK_INDUSTRIES:
            excluded_reasons.append(f"Sin stock industry: {industry}")

        if self.config.exclude_fossil_fuels and industry_lower in FOSSIL_FUEL_INDUSTRIES:
            excluded_reasons.append(f"Fossil fuel industry: {industry}")

        if self.config.exclude_weapons and industry_lower in WEAPONS_INDUSTRIES:
            excluded_reasons.append(f"Weapons industry: {industry}")

        # Check score threshold
        score_obj = self._scores.get(symbol)
        score_val = score_obj.composite_score if score_obj else None

        if score_val is not None and score_val < min_score:
            excluded_reasons.append(
                f"ESG score {score_val:.1f} below minimum {min_score:.1f}"
            )

        # Check carbon intensity
        carbon = self._carbon.get(symbol)
        if carbon and carbon.carbon_intensity > self.config.carbon_intensity_threshold:
            excluded_reasons.append(
                f"Carbon intensity {carbon.carbon_intensity:.0f} exceeds "
                f"threshold {self.config.carbon_intensity_threshold:.0f}"
            )

        return ESGScreenResult(
            symbol=symbol,
            passed=len(excluded_reasons) == 0,
            excluded_reasons=excluded_reasons,
            score=score_val,
            rating=score_obj.rating if score_obj else None,
        )

    def set_carbon_metrics(self, symbol: str, metrics: CarbonMetrics) -> None:
        """Set carbon metrics for a security."""
        metrics.symbol = symbol
        self._carbon[symbol] = metrics

    def get_carbon_metrics(self, symbol: str) -> Optional[CarbonMetrics]:
        """Get carbon metrics for a security."""
        return self._carbon.get(symbol)

    def portfolio_summary(
        self,
        holdings: dict[str, float],
    ) -> ESGPortfolioSummary:
        """Compute portfolio-level ESG summary.

        Args:
            holdings: Dict of symbol -> weight (0-1).

        Returns:
            ESGPortfolioSummary with weighted scores.
        """
        total_weight = sum(holdings.values())
        if total_weight == 0:
            return ESGPortfolioSummary()

        weighted_e = 0.0
        weighted_s = 0.0
        weighted_g = 0.0
        weighted_composite = 0.0
        weighted_carbon = 0.0
        covered_weight = 0.0
        all_controversies = []
        scored_symbols = []

        for symbol, weight in holdings.items():
            norm_weight = weight / total_weight
            score = self._scores.get(symbol)

            if score:
                weighted_e += score.environmental_score * norm_weight
                weighted_s += score.social_score * norm_weight
                weighted_g += score.governance_score * norm_weight
                weighted_composite += score.composite_score * norm_weight
                covered_weight += norm_weight
                scored_symbols.append((symbol, score.composite_score))

                if score.controversies:
                    all_controversies.extend(
                        f"{symbol}: {c}" for c in score.controversies
                    )

            carbon = self._carbon.get(symbol)
            if carbon:
                weighted_carbon += carbon.carbon_intensity * norm_weight

        # Best/worst in class
        scored_symbols.sort(key=lambda x: x[1], reverse=True)
        best = [s for s, _ in scored_symbols[:3]]
        worst = [s for s, _ in scored_symbols[-3:]] if len(scored_symbols) >= 3 else []

        rating = self._score_to_rating(weighted_composite)

        return ESGPortfolioSummary(
            weighted_esg_score=round(weighted_composite, 2),
            weighted_e_score=round(weighted_e, 2),
            weighted_s_score=round(weighted_s, 2),
            weighted_g_score=round(weighted_g, 2),
            portfolio_carbon_intensity=round(weighted_carbon, 2),
            portfolio_rating=rating,
            n_holdings=len(holdings),
            n_screened_out=0,
            coverage_pct=round(covered_weight * 100, 1),
            best_in_class=best,
            worst_in_class=worst,
            controversies=all_controversies,
        )

    def rank_by_sector(self, sector: str) -> list[ESGScore]:
        """Rank securities within a sector by ESG score.

        Args:
            sector: Sector name.

        Returns:
            List of ESGScore sorted by composite score descending.
        """
        sector_scores = [
            s for s in self._scores.values()
            if s.sector == sector
        ]
        sector_scores.sort(key=lambda x: x.composite_score, reverse=True)

        for i, score in enumerate(sector_scores):
            score.sector_rank = i + 1
            score.sector_percentile = (
                (len(sector_scores) - i) / len(sector_scores) * 100
                if sector_scores else 0
            )

        return sector_scores

    def get_score(self, symbol: str) -> Optional[ESGScore]:
        """Get ESG score for a symbol."""
        return self._scores.get(symbol)

    def get_all_scores(self) -> list[ESGScore]:
        """Get all scored securities."""
        return list(self._scores.values())

    def _score_to_rating(self, score: float) -> ESGRating:
        """Convert numeric score to letter rating."""
        for rating, threshold in RATING_THRESHOLDS.items():
            if score >= threshold:
                return rating
        return ESGRating.CCC
