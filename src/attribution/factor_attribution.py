"""Factor-based Attribution.

Decomposes portfolio returns into factor contributions and specific return.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.attribution.config import STANDARD_FACTORS
from src.attribution.models import FactorAttribution, FactorContribution

logger = logging.getLogger(__name__)


class FactorAnalyzer:
    """Factor-based return attribution.

    Decomposes portfolio return into:
    - Factor contributions: exposure × factor return for each factor
    - Specific return: residual alpha not explained by factors

    Uses cross-sectional regression or provided factor exposures.
    """

    def analyze(
        self,
        portfolio_return: float,
        factor_exposures: dict[str, float],
        factor_returns: dict[str, float],
    ) -> FactorAttribution:
        """Perform factor attribution from exposures and returns.

        Args:
            portfolio_return: Total portfolio return for the period.
            factor_exposures: Factor name -> portfolio exposure.
            factor_returns: Factor name -> factor return.

        Returns:
            FactorAttribution with per-factor breakdown.
        """
        contributions: list[FactorContribution] = []
        total_factor_return = 0.0

        all_factors = sorted(
            set(factor_exposures) | set(factor_returns)
        )

        for factor in all_factors:
            exposure = factor_exposures.get(factor, 0.0)
            factor_ret = factor_returns.get(factor, 0.0)
            contribution = exposure * factor_ret

            contributions.append(FactorContribution(
                factor=factor,
                exposure=exposure,
                factor_return=factor_ret,
                contribution=contribution,
            ))
            total_factor_return += contribution

        specific_return = portfolio_return - total_factor_return

        # Compute R² (factor explained variance / total variance)
        if abs(portfolio_return) > 1e-10:
            r_squared = min(1.0, max(0.0, abs(total_factor_return / portfolio_return)))
        else:
            r_squared = 0.0

        return FactorAttribution(
            portfolio_return=portfolio_return,
            factor_return_total=total_factor_return,
            specific_return=specific_return,
            factors=contributions,
            r_squared=r_squared,
        )

    def analyze_from_returns(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame,
    ) -> FactorAttribution:
        """Perform factor attribution using regression.

        Uses OLS regression to estimate factor exposures from
        historical return series.

        Args:
            portfolio_returns: Portfolio daily return series.
            factor_returns: DataFrame with factor daily returns (columns = factors).

        Returns:
            FactorAttribution.
        """
        # Align dates
        common_idx = portfolio_returns.index.intersection(factor_returns.index)
        if len(common_idx) < 10:
            return FactorAttribution(
                portfolio_return=float(portfolio_returns.sum()),
            )

        y = portfolio_returns.loc[common_idx].values
        X = factor_returns.loc[common_idx].values

        # Add intercept
        X_with_const = np.column_stack([np.ones(len(X)), X])

        # OLS: beta = (X'X)^-1 X'y
        try:
            beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            return FactorAttribution(
                portfolio_return=float(portfolio_returns.sum()),
            )

        intercept = beta[0]
        exposures = beta[1:]

        # Factor contributions (cumulative)
        factor_names = list(factor_returns.columns)
        cum_factor_returns = factor_returns.loc[common_idx].sum()

        contributions: list[FactorContribution] = []
        total_factor_ret = 0.0

        for i, factor in enumerate(factor_names):
            exp = float(exposures[i])
            f_ret = float(cum_factor_returns.iloc[i])
            contrib = exp * f_ret
            contributions.append(FactorContribution(
                factor=factor,
                exposure=exp,
                factor_return=f_ret,
                contribution=contrib,
            ))
            total_factor_ret += contrib

        port_total = float(portfolio_returns.loc[common_idx].sum())
        specific = port_total - total_factor_ret

        # R²
        y_pred = X_with_const @ beta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        return FactorAttribution(
            portfolio_return=port_total,
            factor_return_total=total_factor_ret,
            specific_return=specific,
            factors=contributions,
            r_squared=max(0.0, float(r_squared)),
        )
