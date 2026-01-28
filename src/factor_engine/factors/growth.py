"""Growth factor category: Revenue, earnings, and asset expansion."""

import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    safe_divide,
)


class GrowthFactors(FactorCategory):
    """Growth factors: Companies with expanding revenues, earnings, and assets.

    Sub-factors:
    - Revenue Growth (YoY) - top-line expansion
    - Earnings Growth (YoY) - bottom-line expansion
    - FCF Growth - cash flow expansion
    - Revenue Growth Acceleration - improving trajectory
    - R&D Intensity - innovation investment
    - Asset Growth - balance sheet expansion (can be negative factor)

    Higher growth rates = higher growth score.
    """

    name = "growth"
    sub_factors = [
        "revenue_growth",
        "earnings_growth",
        "fcf_growth",
        "revenue_acceleration",
        "rd_intensity",
        "asset_growth",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "revenue_growth": 0.30,
        "earnings_growth": 0.30,
        "fcf_growth": 0.15,
        "revenue_acceleration": 0.10,
        "rd_intensity": 0.10,
        "asset_growth": 0.05,  # Can be negative factor, low weight
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute growth factor score for all tickers."""
        sub_scores = self.compute_sub_factors(prices, fundamentals, returns)

        # Weighted average of available sub-factors
        score = pd.Series(0.0, index=fundamentals.index)
        total_weight = 0.0

        for factor, weight in self.weights.items():
            if factor in sub_scores.columns:
                col = sub_scores[factor]
                valid_mask = col.notna()
                score = score.add(weight * col.fillna(0), fill_value=0)
                total_weight += weight * valid_mask.astype(float).fillna(0)

        # Normalize by actual weights used
        score = safe_divide(score, total_weight.replace(0, 1))
        return score.reindex(fundamentals.index).fillna(0.5)

    def compute_sub_factors(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute individual growth sub-factor scores."""
        result = pd.DataFrame(index=fundamentals.index)

        # Revenue Growth - higher is better
        if "revenueGrowth" in fundamentals.columns:
            rg = fundamentals["revenueGrowth"]
            result["revenue_growth"] = percentile_rank(rg)

        # Earnings Growth - higher is better
        if "earningsGrowth" in fundamentals.columns:
            eg = fundamentals["earningsGrowth"]
            result["earnings_growth"] = percentile_rank(eg)

        # FCF Growth (if available)
        if "freeCashflowGrowth" in fundamentals.columns:
            fcfg = fundamentals["freeCashflowGrowth"]
            result["fcf_growth"] = percentile_rank(fcfg)

        # Revenue Growth Acceleration (quarter-over-quarter improvement)
        # Approximated as revenue growth itself for now (need historical data)
        if "revenueGrowth" in fundamentals.columns:
            # Use revenue growth as proxy for acceleration
            rg = fundamentals["revenueGrowth"]
            result["revenue_acceleration"] = percentile_rank(rg)

        # R&D Intensity = R&D / Revenue (higher for innovative companies)
        if "researchAndDevelopment" in fundamentals.columns and "totalRevenue" in fundamentals.columns:
            rd = fundamentals["researchAndDevelopment"].fillna(0)
            revenue = fundamentals["totalRevenue"].clip(lower=1)
            rd_intensity = safe_divide(rd, revenue)
            result["rd_intensity"] = percentile_rank(rd_intensity)

        # Asset Growth - moderate growth is good, extreme can be bad
        # Using a modified rank where moderate growth scores highest
        if "assetGrowth" in fundamentals.columns:
            ag = fundamentals["assetGrowth"]
            result["asset_growth"] = percentile_rank(ag)

        return result
