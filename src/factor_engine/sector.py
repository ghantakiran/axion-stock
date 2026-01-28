"""Sector-relative scoring for factor adjustments."""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default blending weights for dual scoring
UNIVERSE_WEIGHT = 0.60
SECTOR_WEIGHT = 0.40


class SectorRelativeScorer:
    """Compute sector-relative scores and blend with universe scores.

    Sector-relative scoring addresses issues like:
    - Banks always appearing "cheap" on value metrics
    - Tech stocks always appearing "expensive"
    - Different norms for different industry groups

    Dual scoring system:
    1. Universe Score: Percentile rank vs all 8,000+ stocks
    2. Sector Score: Percentile rank vs same GICS sector peers

    Final = 60% Universe + 40% Sector (configurable)
    """

    def __init__(
        self,
        universe_weight: float = UNIVERSE_WEIGHT,
        sector_weight: float = SECTOR_WEIGHT,
    ):
        """Initialize sector scorer.

        Args:
            universe_weight: Weight for universe-relative scores (default: 0.60)
            sector_weight: Weight for sector-relative scores (default: 0.40)
        """
        if abs(universe_weight + sector_weight - 1.0) > 0.01:
            raise ValueError("Universe and sector weights must sum to 1.0")

        self.universe_weight = universe_weight
        self.sector_weight = sector_weight

    def compute_blended_scores(
        self,
        universe_scores: pd.DataFrame,
        sector_mapping: pd.Series,
        min_sector_size: int = 5,
    ) -> pd.DataFrame:
        """Compute blended universe + sector-relative scores.

        Args:
            universe_scores: DataFrame[tickers x factors] with universe percentile scores
            sector_mapping: Series[tickers] -> sector names (e.g., "Technology", "Healthcare")
            min_sector_size: Minimum number of stocks in sector for sector scoring

        Returns:
            DataFrame[tickers x factors] with blended scores
        """
        if sector_mapping.empty or self.sector_weight == 0:
            return universe_scores

        # Align sector mapping with scores
        aligned_sectors = sector_mapping.reindex(universe_scores.index)

        # Compute sector-relative scores
        sector_scores = self._compute_sector_scores(
            universe_scores, aligned_sectors, min_sector_size
        )

        # Blend scores
        blended = (
            self.universe_weight * universe_scores +
            self.sector_weight * sector_scores
        )

        return blended

    def _compute_sector_scores(
        self,
        scores: pd.DataFrame,
        sectors: pd.Series,
        min_sector_size: int,
    ) -> pd.DataFrame:
        """Compute sector-relative percentile scores."""
        result = pd.DataFrame(index=scores.index, columns=scores.columns)

        # Get unique sectors
        valid_sectors = sectors.dropna().unique()

        for sector in valid_sectors:
            # Get tickers in this sector
            sector_mask = sectors == sector
            sector_tickers = scores.index[sector_mask]

            if len(sector_tickers) < min_sector_size:
                # Too few stocks in sector, use universe scores
                result.loc[sector_tickers] = scores.loc[sector_tickers]
                continue

            # Compute sector-relative percentile ranks
            sector_scores = scores.loc[sector_tickers]
            sector_ranks = sector_scores.rank(pct=True)
            result.loc[sector_tickers] = sector_ranks

        # Fill any remaining NaN with universe scores
        result = result.fillna(scores)

        return result

    def get_sector_statistics(
        self,
        scores: pd.DataFrame,
        sectors: pd.Series,
    ) -> pd.DataFrame:
        """Get summary statistics by sector for analysis.

        Returns DataFrame with sector-level statistics for each factor.
        """
        aligned_sectors = sectors.reindex(scores.index)
        stats = []

        for sector in aligned_sectors.dropna().unique():
            sector_mask = aligned_sectors == sector
            sector_scores = scores.loc[sector_mask]

            sector_stats = {
                "sector": sector,
                "count": len(sector_scores),
            }

            for col in scores.columns:
                sector_stats[f"{col}_mean"] = sector_scores[col].mean()
                sector_stats[f"{col}_std"] = sector_scores[col].std()

            stats.append(sector_stats)

        return pd.DataFrame(stats).sort_values("count", ascending=False)


def get_sector_from_instruments(tickers: list[str]) -> pd.Series:
    """Fetch sector mapping from instruments table.

    Args:
        tickers: List of ticker symbols

    Returns:
        Series[ticker] -> sector name
    """
    try:
        from src.services.sync_adapter import sync_data_service

        # Try to get from database
        # For now, return empty - would need to add method to data service
        logger.debug("Sector mapping from DB not yet implemented")
        return pd.Series(dtype=str)
    except ImportError:
        return pd.Series(dtype=str)


def get_sector_from_fundamentals(fundamentals: pd.DataFrame) -> pd.Series:
    """Extract sector from fundamentals DataFrame if available.

    Some yfinance data includes sector information.
    """
    if "sector" in fundamentals.columns:
        return fundamentals["sector"]

    return pd.Series(index=fundamentals.index, dtype=str)
