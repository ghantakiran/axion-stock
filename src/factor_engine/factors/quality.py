"""Quality factor category: Profitability, stability, and financial health."""

import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    invert_rank,
    safe_divide,
)


class QualityFactors(FactorCategory):
    """Quality factors: Profitable, stable companies with strong balance sheets.

    Sub-factors:
    - Return on Equity (ROE) - profitability relative to equity
    - Return on Assets (ROA) - asset efficiency
    - Gross Profit / Assets - Novy-Marx quality metric
    - Debt/Equity - leverage risk (lower is better)
    - Accruals - earnings quality (lower accruals = higher quality)
    - Interest Coverage - debt service ability
    - Gross Margin - pricing power

    Higher profitability + lower leverage = higher quality score.
    """

    name = "quality"
    sub_factors = [
        "roe",
        "roa",
        "gross_profit_assets",
        "debt_equity",
        "accruals",
        "interest_coverage",
        "gross_margin",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "roe": 0.25,
        "roa": 0.15,
        "gross_profit_assets": 0.15,
        "debt_equity": 0.20,
        "accruals": 0.10,
        "interest_coverage": 0.05,
        "gross_margin": 0.10,
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute quality factor score for all tickers."""
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
        """Compute individual quality sub-factor scores."""
        result = pd.DataFrame(index=fundamentals.index)

        # Return on Equity - higher is better
        if "returnOnEquity" in fundamentals.columns:
            roe = fundamentals["returnOnEquity"]
            result["roe"] = percentile_rank(roe)

        # Debt/Equity - lower is better (inverted)
        if "debtToEquity" in fundamentals.columns:
            de = fundamentals["debtToEquity"].clip(lower=0)
            result["debt_equity"] = invert_rank(de)

        # Return on Assets - higher is better
        if "returnOnAssets" in fundamentals.columns:
            roa = fundamentals["returnOnAssets"]
            result["roa"] = percentile_rank(roa)

        # Gross Profit / Assets - higher is better (Novy-Marx)
        if "grossProfits" in fundamentals.columns and "totalAssets" in fundamentals.columns:
            gp = fundamentals["grossProfits"]
            assets = fundamentals["totalAssets"].clip(lower=1)
            gp_assets = safe_divide(gp, assets)
            result["gross_profit_assets"] = percentile_rank(gp_assets)

        # Gross Margin - higher is better
        if "grossMargins" in fundamentals.columns:
            gm = fundamentals["grossMargins"]
            result["gross_margin"] = percentile_rank(gm)

        # Accruals = (Net Income - Operating Cash Flow) / Total Assets
        # Lower accruals = higher quality (inverted)
        if all(col in fundamentals.columns for col in ["netIncome", "operatingCashflow", "totalAssets"]):
            ni = fundamentals["netIncome"]
            ocf = fundamentals["operatingCashflow"]
            assets = fundamentals["totalAssets"].clip(lower=1)
            accruals = safe_divide(ni - ocf, assets)
            result["accruals"] = invert_rank(accruals)  # Lower is better

        # Interest Coverage = EBIT / Interest Expense (higher is better)
        if "ebit" in fundamentals.columns and "interestExpense" in fundamentals.columns:
            ebit = fundamentals["ebit"]
            interest = fundamentals["interestExpense"].clip(lower=1)
            coverage = safe_divide(ebit, interest)
            result["interest_coverage"] = percentile_rank(coverage)

        return result
