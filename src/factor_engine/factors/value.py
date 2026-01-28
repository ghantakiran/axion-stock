"""Value factor category: Low valuations relative to fundamentals."""

import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    invert_rank,
    safe_divide,
)


class ValueFactors(FactorCategory):
    """Value factors: Stocks trading cheaply relative to fundamentals.

    Sub-factors:
    - Earnings Yield (EBIT/EV) - inverted PE, better for capital structure
    - Price-to-Book - classic book value metric
    - EV/EBITDA - debt-inclusive valuation
    - Dividend Yield - income component
    - Free Cash Flow Yield - cash-based valuation
    - Forward P/E (if available) - forward-looking value

    Lower valuation multiples = higher value score.
    """

    name = "value"
    sub_factors = [
        "earnings_yield",
        "price_to_book",
        "ev_ebitda",
        "dividend_yield",
        "fcf_yield",
        "trailing_pe",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "earnings_yield": 0.20,
        "price_to_book": 0.15,
        "ev_ebitda": 0.20,
        "dividend_yield": 0.15,
        "fcf_yield": 0.20,
        "trailing_pe": 0.10,
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute value factor score for all tickers."""
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
        """Compute individual value sub-factor scores."""
        result = pd.DataFrame(index=fundamentals.index)

        # Trailing P/E - lower is better (inverted)
        if "trailingPE" in fundamentals.columns:
            pe = fundamentals["trailingPE"].clip(lower=0)  # Remove negative PE
            result["trailing_pe"] = invert_rank(pe)

        # Price-to-Book - lower is better (inverted)
        if "priceToBook" in fundamentals.columns:
            pb = fundamentals["priceToBook"].clip(lower=0)
            result["price_to_book"] = invert_rank(pb)

        # EV/EBITDA - lower is better (inverted)
        if "enterpriseToEbitda" in fundamentals.columns:
            ev = fundamentals["enterpriseToEbitda"].clip(lower=0)
            result["ev_ebitda"] = invert_rank(ev)

        # Dividend Yield - higher is better (direct rank)
        if "dividendYield" in fundamentals.columns:
            dy = fundamentals["dividendYield"].clip(lower=0)
            result["dividend_yield"] = percentile_rank(dy)

        # Earnings Yield = 1/PE (higher is better)
        if "trailingPE" in fundamentals.columns:
            pe = fundamentals["trailingPE"].clip(lower=0.1)  # Avoid division issues
            earnings_yield = safe_divide(pd.Series(1.0, index=pe.index), pe)
            result["earnings_yield"] = percentile_rank(earnings_yield)

        # FCF Yield approximation (if we have FCF data, otherwise skip)
        # Using freeCashflow / marketCap if available
        if "freeCashflow" in fundamentals.columns and "marketCap" in fundamentals.columns:
            fcf = fundamentals["freeCashflow"]
            mcap = fundamentals["marketCap"].clip(lower=1)
            fcf_yield = safe_divide(fcf, mcap)
            result["fcf_yield"] = percentile_rank(fcf_yield)

        return result
