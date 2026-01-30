"""Portfolio Analytics & What-If Analysis.

Provides portfolio X-ray, what-if scenario analysis,
and performance attribution.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import OptimizationConfig

logger = logging.getLogger(__name__)


@dataclass
class PortfolioXRay:
    """Comprehensive portfolio analysis snapshot."""

    num_positions: int = 0
    total_weight: float = 0.0
    cash_weight: float = 0.0

    # Sector allocation
    sector_weights: dict = field(default_factory=dict)

    # Factor exposure
    factor_exposures: dict = field(default_factory=dict)

    # Risk metrics
    portfolio_beta: float = 0.0
    portfolio_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    var_95: float = 0.0

    # Concentration
    top5_weight: float = 0.0
    hhi: float = 0.0
    effective_n: float = 0.0
    avg_correlation: float = 0.0

    def to_dict(self) -> dict:
        return {
            "num_positions": self.num_positions,
            "cash_weight": self.cash_weight,
            "sector_weights": self.sector_weights,
            "factor_exposures": self.factor_exposures,
            "portfolio_beta": self.portfolio_beta,
            "portfolio_volatility": self.portfolio_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "var_95": self.var_95,
            "top5_weight": self.top5_weight,
            "hhi": self.hhi,
            "effective_n": self.effective_n,
            "avg_correlation": self.avg_correlation,
        }


@dataclass
class WhatIfResult:
    """Result of a what-if scenario analysis."""

    risk_change: float = 0.0
    return_change: float = 0.0
    sharpe_change: float = 0.0
    sector_impact: dict = field(default_factory=dict)
    factor_impact: dict = field(default_factory=dict)
    new_volatility: float = 0.0
    new_return: float = 0.0
    new_sharpe: float = 0.0

    def to_dict(self) -> dict:
        return {
            "risk_change": self.risk_change,
            "return_change": self.return_change,
            "sharpe_change": self.sharpe_change,
            "sector_impact": self.sector_impact,
            "factor_impact": self.factor_impact,
            "new_volatility": self.new_volatility,
            "new_return": self.new_return,
            "new_sharpe": self.new_sharpe,
        }


class PortfolioAnalytics:
    """Compute portfolio-level analytics.

    Example:
        analytics = PortfolioAnalytics()
        xray = analytics.compute_xray(weights, cov, sectors, factor_scores)
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def compute_xray(
        self,
        weights: pd.Series,
        cov_matrix: Optional[pd.DataFrame] = None,
        sectors: Optional[dict[str, str]] = None,
        factor_scores: Optional[pd.DataFrame] = None,
        expected_returns: Optional[pd.Series] = None,
        betas: Optional[pd.Series] = None,
    ) -> PortfolioXRay:
        """Compute comprehensive portfolio X-ray.

        Args:
            weights: Portfolio weights.
            cov_matrix: Covariance matrix.
            sectors: Symbol -> sector mapping.
            factor_scores: Factor scores DataFrame.
            expected_returns: Expected returns per asset.
            betas: Asset betas.

        Returns:
            PortfolioXRay with all analytics.
        """
        active = weights[weights > 1e-6]
        xray = PortfolioXRay()

        xray.num_positions = len(active)
        xray.total_weight = float(active.sum())
        xray.cash_weight = max(0, 1.0 - xray.total_weight)

        # Sector allocation
        if sectors:
            sector_w: dict[str, float] = {}
            for symbol, w in active.items():
                sec = sectors.get(str(symbol), "Other")
                sector_w[sec] = sector_w.get(sec, 0) + w
            xray.sector_weights = dict(sorted(sector_w.items(), key=lambda x: -x[1]))

        # Factor exposure
        if factor_scores is not None:
            common = active.index.intersection(factor_scores.index)
            if len(common) > 0:
                w_common = active.reindex(common).fillna(0)
                w_norm = w_common / w_common.sum() if w_common.sum() > 0 else w_common
                for col in factor_scores.columns:
                    exposure = float(w_norm @ factor_scores.loc[common, col])
                    xray.factor_exposures[col] = round(exposure, 4)

        # Risk metrics
        if cov_matrix is not None:
            common = active.index.intersection(cov_matrix.index)
            if len(common) > 0:
                w = active.reindex(common).fillna(0).values
                cov = cov_matrix.loc[common, common].values
                port_var = float(w @ cov @ w)
                xray.portfolio_volatility = float(np.sqrt(port_var))

                # VaR (95%) assuming normal
                xray.var_95 = -1.645 * xray.portfolio_volatility

                # Avg pairwise correlation
                std = np.sqrt(np.diag(cov))
                with np.errstate(divide="ignore", invalid="ignore"):
                    corr = cov / np.outer(std, std)
                corr = np.nan_to_num(corr, nan=0)
                n = len(common)
                if n > 1:
                    mask = np.ones((n, n), dtype=bool)
                    np.fill_diagonal(mask, False)
                    xray.avg_correlation = float(corr[mask].mean())

        # Beta
        if betas is not None:
            common = active.index.intersection(betas.index)
            if len(common) > 0:
                w = active.reindex(common).fillna(0)
                xray.portfolio_beta = float(w @ betas.reindex(common).fillna(1))

        # Expected return and Sharpe
        if expected_returns is not None:
            common = active.index.intersection(expected_returns.index)
            if len(common) > 0:
                w = active.reindex(common).fillna(0)
                port_ret = float(w @ expected_returns.reindex(common).fillna(0))
                if xray.portfolio_volatility > 0:
                    xray.sharpe_ratio = (port_ret - self.config.risk_free_rate) / xray.portfolio_volatility

        # Concentration
        if len(active) >= 5:
            xray.top5_weight = float(active.nlargest(5).sum())
        else:
            xray.top5_weight = float(active.sum())

        sq_sum = float((active ** 2).sum())
        xray.hhi = sq_sum * 10_000
        xray.effective_n = 1.0 / sq_sum if sq_sum > 0 else 0

        return xray

    def compute_risk_contribution(
        self,
        weights: pd.Series,
        cov_matrix: pd.DataFrame,
    ) -> pd.Series:
        """Compute each asset's contribution to total portfolio risk.

        Args:
            weights: Portfolio weights.
            cov_matrix: Covariance matrix.

        Returns:
            Series of risk contributions (sum to 1).
        """
        common = weights.index.intersection(cov_matrix.index)
        w = weights.reindex(common).fillna(0).values
        cov = cov_matrix.loc[common, common].values

        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < 1e-12:
            return pd.Series(0, index=common)

        marginal = cov @ w
        risk_contrib = w * marginal / port_vol
        total = risk_contrib.sum()
        if total > 0:
            risk_contrib = risk_contrib / total

        return pd.Series(risk_contrib, index=common)


class WhatIfAnalyzer:
    """Analyze the impact of portfolio changes.

    Example:
        analyzer = WhatIfAnalyzer()
        result = analyzer.analyze(
            weights, changes={"NVDA": 0.05, "AAPL": -0.05},
            cov_matrix=cov, expected_returns=returns,
        )
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def analyze(
        self,
        weights: pd.Series,
        changes: dict[str, float],
        cov_matrix: Optional[pd.DataFrame] = None,
        expected_returns: Optional[pd.Series] = None,
        sectors: Optional[dict[str, str]] = None,
        factor_scores: Optional[pd.DataFrame] = None,
    ) -> WhatIfResult:
        """Analyze impact of weight changes.

        Args:
            weights: Current portfolio weights.
            changes: Dict of symbol -> weight delta (e.g. {"NVDA": +0.05, "AAPL": -0.05}).
            cov_matrix: Covariance matrix.
            expected_returns: Expected returns.
            sectors: Sector mapping.
            factor_scores: Factor scores.

        Returns:
            WhatIfResult with impact analysis.
        """
        new_weights = weights.copy()
        for symbol, delta in changes.items():
            current = new_weights.get(symbol, 0)
            new_weights[symbol] = max(0, current + delta)

        # Re-normalize
        total = new_weights.sum()
        if total > 0:
            new_weights = new_weights / total

        result = WhatIfResult()

        # Risk change
        if cov_matrix is not None:
            old_vol = self._portfolio_vol(weights, cov_matrix)
            new_vol = self._portfolio_vol(new_weights, cov_matrix)
            result.risk_change = new_vol - old_vol
            result.new_volatility = new_vol

        # Return change
        if expected_returns is not None:
            old_ret = self._portfolio_return(weights, expected_returns)
            new_ret = self._portfolio_return(new_weights, expected_returns)
            result.return_change = new_ret - old_ret
            result.new_return = new_ret

        # Sharpe change
        if cov_matrix is not None and expected_returns is not None:
            rf = self.config.risk_free_rate
            old_vol = self._portfolio_vol(weights, cov_matrix)
            new_vol = result.new_volatility
            old_ret = self._portfolio_return(weights, expected_returns)
            new_ret = result.new_return
            old_sharpe = (old_ret - rf) / old_vol if old_vol > 0 else 0
            new_sharpe = (new_ret - rf) / new_vol if new_vol > 0 else 0
            result.sharpe_change = new_sharpe - old_sharpe
            result.new_sharpe = new_sharpe

        # Sector impact
        if sectors:
            old_sectors = self._sector_weights(weights, sectors)
            new_sectors = self._sector_weights(new_weights, sectors)
            all_sectors = set(old_sectors) | set(new_sectors)
            result.sector_impact = {
                s: new_sectors.get(s, 0) - old_sectors.get(s, 0)
                for s in all_sectors
                if abs(new_sectors.get(s, 0) - old_sectors.get(s, 0)) > 1e-6
            }

        # Factor impact
        if factor_scores is not None:
            old_exp = self._factor_exposure(weights, factor_scores)
            new_exp = self._factor_exposure(new_weights, factor_scores)
            result.factor_impact = {
                f: new_exp.get(f, 0) - old_exp.get(f, 0)
                for f in set(old_exp) | set(new_exp)
                if abs(new_exp.get(f, 0) - old_exp.get(f, 0)) > 1e-6
            }

        return result

    def _portfolio_vol(self, weights: pd.Series, cov_matrix: pd.DataFrame) -> float:
        common = weights.index.intersection(cov_matrix.index)
        if len(common) == 0:
            return 0.0
        w = weights.reindex(common).fillna(0).values
        cov = cov_matrix.loc[common, common].values
        return float(np.sqrt(max(0, w @ cov @ w)))

    def _portfolio_return(self, weights: pd.Series, expected_returns: pd.Series) -> float:
        common = weights.index.intersection(expected_returns.index)
        if len(common) == 0:
            return 0.0
        w = weights.reindex(common).fillna(0)
        return float(w @ expected_returns.reindex(common).fillna(0))

    def _sector_weights(self, weights: pd.Series, sectors: dict) -> dict:
        result: dict[str, float] = {}
        for symbol, w in weights.items():
            sec = sectors.get(str(symbol), "Other")
            result[sec] = result.get(sec, 0) + w
        return result

    def _factor_exposure(self, weights: pd.Series, factor_scores: pd.DataFrame) -> dict:
        common = weights.index.intersection(factor_scores.index)
        if len(common) == 0:
            return {}
        w = weights.reindex(common).fillna(0)
        w_norm = w / w.sum() if w.sum() > 0 else w
        exposures = {}
        for col in factor_scores.columns:
            exposures[col] = float(w_norm @ factor_scores.loc[common, col])
        return exposures
