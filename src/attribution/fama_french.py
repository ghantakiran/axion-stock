"""Fama-French Factor Models.

Implements Fama-French 3-factor and 5-factor models for
performance attribution and alpha estimation.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.attribution.config import AttributionConfig, DEFAULT_ATTRIBUTION_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class FFFactorExposure:
    """Exposure to a single Fama-French factor."""
    factor: str = ""
    beta: float = 0.0
    t_statistic: float = 0.0
    p_value: float = 0.0
    contribution: float = 0.0

    @property
    def is_significant(self) -> bool:
        return abs(self.t_statistic) > 1.96


@dataclass
class FFModelResult:
    """Fama-French model regression result."""
    model_name: str = "ff3"
    alpha: float = 0.0
    alpha_annualized: float = 0.0
    alpha_t_stat: float = 0.0
    r_squared: float = 0.0
    adjusted_r_squared: float = 0.0
    factors: list[FFFactorExposure] = field(default_factory=list)
    residual_volatility: float = 0.0
    n_observations: int = 0

    @property
    def alpha_is_significant(self) -> bool:
        return abs(self.alpha_t_stat) > 1.96

    @property
    def total_factor_return(self) -> float:
        return sum(f.contribution for f in self.factors)

    @property
    def specific_return(self) -> float:
        return self.alpha


@dataclass
class FFComparison:
    """Comparison between FF3 and FF5 models."""
    ff3: FFModelResult = field(default_factory=FFModelResult)
    ff5: FFModelResult = field(default_factory=FFModelResult)
    preferred_model: str = "ff3"
    reason: str = ""

    @property
    def r_squared_improvement(self) -> float:
        return self.ff5.r_squared - self.ff3.r_squared


# ---------------------------------------------------------------------------
# Fama-French Analyzer
# ---------------------------------------------------------------------------
class FamaFrenchAnalyzer:
    """Fama-French factor model analysis.

    Supports FF3 (Mkt-RF, SMB, HML) and FF5 (+ RMW, CMA).
    """

    FF3_FACTORS = ["Mkt-RF", "SMB", "HML"]
    FF5_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def fit_ff3(
        self,
        portfolio_excess_returns: list[float],
        mkt_rf: list[float],
        smb: list[float],
        hml: list[float],
    ) -> FFModelResult:
        """Fit Fama-French 3-factor model.

        R_p - R_f = alpha + beta_mkt*(Mkt-RF) + beta_smb*SMB + beta_hml*HML + e

        Args:
            portfolio_excess_returns: Portfolio returns minus risk-free rate.
            mkt_rf: Market excess returns.
            smb: Small Minus Big factor returns.
            hml: High Minus Low (value) factor returns.

        Returns:
            FFModelResult with exposures, alpha, and R-squared.
        """
        factor_data = {
            "Mkt-RF": mkt_rf,
            "SMB": smb,
            "HML": hml,
        }
        return self._fit_model(
            portfolio_excess_returns, factor_data, "ff3"
        )

    def fit_ff5(
        self,
        portfolio_excess_returns: list[float],
        mkt_rf: list[float],
        smb: list[float],
        hml: list[float],
        rmw: list[float],
        cma: list[float],
    ) -> FFModelResult:
        """Fit Fama-French 5-factor model.

        R_p - R_f = alpha + beta_mkt*(Mkt-RF) + beta_smb*SMB
                   + beta_hml*HML + beta_rmw*RMW + beta_cma*CMA + e

        Args:
            portfolio_excess_returns: Portfolio returns minus risk-free rate.
            mkt_rf: Market excess returns.
            smb: Small Minus Big factor returns.
            hml: High Minus Low (value) factor returns.
            rmw: Robust Minus Weak (profitability) factor returns.
            cma: Conservative Minus Aggressive (investment) factor returns.

        Returns:
            FFModelResult with 5-factor exposures.
        """
        factor_data = {
            "Mkt-RF": mkt_rf,
            "SMB": smb,
            "HML": hml,
            "RMW": rmw,
            "CMA": cma,
        }
        return self._fit_model(
            portfolio_excess_returns, factor_data, "ff5"
        )

    def compare_models(
        self,
        portfolio_excess_returns: list[float],
        mkt_rf: list[float],
        smb: list[float],
        hml: list[float],
        rmw: list[float],
        cma: list[float],
    ) -> FFComparison:
        """Compare FF3 and FF5 models.

        Args:
            portfolio_excess_returns: Portfolio excess returns.
            mkt_rf, smb, hml, rmw, cma: Factor return series.

        Returns:
            FFComparison with both models and recommendation.
        """
        ff3 = self.fit_ff3(portfolio_excess_returns, mkt_rf, smb, hml)
        ff5 = self.fit_ff5(portfolio_excess_returns, mkt_rf, smb, hml, rmw, cma)

        # Prefer FF5 if it materially improves R² and new factors significant
        improvement = ff5.r_squared - ff3.r_squared
        new_factors_significant = any(
            f.is_significant for f in ff5.factors
            if f.factor in ("RMW", "CMA")
        )

        if improvement > 0.02 and new_factors_significant:
            preferred = "ff5"
            reason = (
                f"FF5 improves R² by {improvement:.1%} with significant "
                "profitability/investment factors"
            )
        else:
            preferred = "ff3"
            reason = "FF3 is sufficient; additional factors do not materially improve fit"

        return FFComparison(
            ff3=ff3,
            ff5=ff5,
            preferred_model=preferred,
            reason=reason,
        )

    def alpha_summary(self, result: FFModelResult) -> dict[str, float]:
        """Summarize alpha statistics.

        Args:
            result: FFModelResult from fit.

        Returns:
            Dict with alpha metrics.
        """
        tdy = self.config.trading_days_per_year
        return {
            "alpha_daily": round(result.alpha, 6),
            "alpha_annualized": round(result.alpha * tdy, 4),
            "alpha_t_stat": round(result.alpha_t_stat, 2),
            "alpha_significant": result.alpha_is_significant,
            "r_squared": round(result.r_squared, 4),
            "residual_vol_annualized": round(
                result.residual_volatility * np.sqrt(tdy), 4
            ),
        }

    def _fit_model(
        self,
        y: list[float],
        factor_data: dict[str, list[float]],
        model_name: str,
    ) -> FFModelResult:
        """Fit multi-factor OLS regression.

        Uses normal equation: beta = (X'X)^-1 X'y with intercept.
        """
        n = len(y)
        if n < 10:
            return FFModelResult(model_name=model_name, n_observations=n)

        y_arr = np.array(y)
        factor_names = list(factor_data.keys())
        k = len(factor_names)

        # Build design matrix with intercept
        X = np.ones((n, k + 1))
        for i, name in enumerate(factor_names):
            X[:, i + 1] = np.array(factor_data[name][:n])

        # OLS: beta = (X'X)^-1 X'y
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
        except np.linalg.LinAlgError:
            return FFModelResult(model_name=model_name, n_observations=n)

        betas = XtX_inv @ X.T @ y_arr

        # Residuals and R²
        y_hat = X @ betas
        residuals = y_arr - y_hat
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y_arr - np.mean(y_arr)) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1) if n > k + 1 else 0.0

        # Standard errors
        residual_var = ss_res / (n - k - 1) if n > k + 1 else 0.0
        se = np.sqrt(np.diag(XtX_inv) * residual_var)
        residual_vol = float(np.std(residuals))

        # Alpha (intercept)
        alpha = float(betas[0])
        alpha_se = float(se[0]) if se[0] > 0 else 1e-10
        alpha_t = alpha / alpha_se

        # Factor exposures
        tdy = self.config.trading_days_per_year
        factors = []
        for i, name in enumerate(factor_names):
            beta_i = float(betas[i + 1])
            se_i = float(se[i + 1]) if se[i + 1] > 0 else 1e-10
            t_stat = beta_i / se_i
            mean_factor = float(np.mean(X[:, i + 1]))
            contribution = beta_i * mean_factor

            # Simple p-value approximation using normal distribution
            p_value = float(2 * (1 - self._norm_cdf(abs(t_stat))))

            factors.append(FFFactorExposure(
                factor=name,
                beta=round(beta_i, 4),
                t_statistic=round(t_stat, 2),
                p_value=round(p_value, 4),
                contribution=round(contribution, 6),
            ))

        return FFModelResult(
            model_name=model_name,
            alpha=round(alpha, 6),
            alpha_annualized=round(alpha * tdy, 4),
            alpha_t_stat=round(alpha_t, 2),
            r_squared=round(max(0, r_squared), 4),
            adjusted_r_squared=round(max(0, adj_r_squared), 4),
            factors=factors,
            residual_volatility=round(residual_vol, 6),
            n_observations=n,
        )

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Approximate standard normal CDF."""
        import math
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
