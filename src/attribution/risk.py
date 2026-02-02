"""Risk-based Return Decomposition.

Euler decomposition of portfolio risk into component and marginal
risk contributions per position and sector.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.attribution.config import (
    TRADING_DAYS_PER_YEAR,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)

logger = logging.getLogger(__name__)


class RiskDecomposer:
    """Decomposes portfolio risk into position-level contributions.

    Uses Euler's theorem for homogeneous functions:
        sigma_p = sum(w_i * marginal_risk_i)

    Component risk for position i:
        CR_i = w_i * (Sigma @ w)_i / sigma_p

    Marginal risk:
        MR_i = (Sigma @ w)_i / sigma_p
    """

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def decompose(
        self,
        weights: dict[str, float],
        returns: pd.DataFrame,
        annualize: bool = True,
    ) -> list[dict]:
        """Decompose portfolio risk by position.

        Args:
            weights: Position name -> weight.
            returns: DataFrame with columns matching weight keys.
            annualize: Whether to annualize risk figures.

        Returns:
            List of dicts with name, weight, volatility, component_risk,
            marginal_risk, and pct_contribution.
        """
        names = sorted(weights.keys())
        if len(names) < 2 or len(returns) < 3:
            return []

        # Ensure columns exist
        available = [n for n in names if n in returns.columns]
        if len(available) < 2:
            return []

        w = np.array([weights[n] for n in available])
        R = returns[available].values
        n_obs = len(R)

        # Sample covariance matrix
        cov = np.cov(R, rowvar=False, ddof=1)
        if cov.ndim == 0:
            return []

        scale = self.config.trading_days_per_year if annualize else 1.0
        cov_ann = cov * scale

        # Portfolio variance and volatility
        port_var = float(w @ cov_ann @ w)
        if port_var <= 0:
            return []
        port_vol = np.sqrt(port_var)

        # Marginal risk: d(sigma_p) / d(w_i) = (Sigma @ w)_i / sigma_p
        sigma_w = cov_ann @ w
        marginal = sigma_w / port_vol

        # Component risk: CR_i = w_i * MR_i
        component = w * marginal

        # Percentage contribution
        pct = component / port_vol

        # Individual volatilities
        individual_vol = np.sqrt(np.diag(cov_ann))

        results = []
        for i, name in enumerate(available):
            results.append({
                "name": name,
                "weight": float(w[i]),
                "volatility": float(individual_vol[i]),
                "component_risk": float(component[i]),
                "marginal_risk": float(marginal[i]),
                "pct_contribution": float(pct[i]),
            })

        return results

    def decompose_by_sector(
        self,
        weights: dict[str, float],
        returns: pd.DataFrame,
        sector_map: dict[str, str],
        annualize: bool = True,
    ) -> list[dict]:
        """Decompose risk by sector.

        Args:
            weights: Position name -> weight.
            returns: DataFrame with columns matching weight keys.
            sector_map: Position name -> sector name.
            annualize: Whether to annualize.

        Returns:
            List of dicts with sector, weight, component_risk, pct_contribution.
        """
        position_decomp = self.decompose(weights, returns, annualize)
        if not position_decomp:
            return []

        sector_agg: dict[str, dict] = {}
        for pos in position_decomp:
            sector = sector_map.get(pos["name"], "Other")
            if sector not in sector_agg:
                sector_agg[sector] = {
                    "sector": sector,
                    "weight": 0.0,
                    "component_risk": 0.0,
                    "pct_contribution": 0.0,
                }
            sector_agg[sector]["weight"] += pos["weight"]
            sector_agg[sector]["component_risk"] += pos["component_risk"]
            sector_agg[sector]["pct_contribution"] += pos["pct_contribution"]

        return sorted(
            sector_agg.values(),
            key=lambda x: abs(x["component_risk"]),
            reverse=True,
        )

    def tracking_error_decomposition(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        returns: pd.DataFrame,
        annualize: bool = True,
    ) -> list[dict]:
        """Decompose tracking error by position.

        Args:
            portfolio_weights: Portfolio position weights.
            benchmark_weights: Benchmark position weights.
            returns: DataFrame with columns matching position names.
            annualize: Whether to annualize.

        Returns:
            List of dicts with name, active_weight, te_contribution.
        """
        all_names = sorted(
            set(portfolio_weights) | set(benchmark_weights)
        )
        available = [n for n in all_names if n in returns.columns]
        if len(available) < 2 or len(returns) < 3:
            return []

        active_w = np.array([
            portfolio_weights.get(n, 0.0) - benchmark_weights.get(n, 0.0)
            for n in available
        ])

        R = returns[available].values
        cov = np.cov(R, rowvar=False, ddof=1)
        if cov.ndim == 0:
            return []

        scale = self.config.trading_days_per_year if annualize else 1.0
        cov_ann = cov * scale

        te_var = float(active_w @ cov_ann @ active_w)
        if te_var <= 0:
            return []
        te = np.sqrt(te_var)

        sigma_w = cov_ann @ active_w
        marginal = sigma_w / te
        component = active_w * marginal

        results = []
        for i, name in enumerate(available):
            results.append({
                "name": name,
                "active_weight": float(active_w[i]),
                "te_contribution": float(component[i]),
                "te_pct": float(component[i] / te) if te > 0 else 0.0,
            })

        return results
