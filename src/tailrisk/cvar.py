"""CVaR (Expected Shortfall) Calculator.

Computes Conditional Value-at-Risk using historical, parametric
(Gaussian), and Cornish-Fisher methods with position-level
decomposition.
"""

import logging
from typing import Optional

import numpy as np
from scipy import stats as sp_stats

from src.tailrisk.config import CVaRConfig, CVaRMethod
from src.tailrisk.models import CVaRResult, CVaRContribution

logger = logging.getLogger(__name__)


class CVaRCalculator:
    """Computes CVaR (Expected Shortfall) for portfolios."""

    def __init__(self, config: Optional[CVaRConfig] = None) -> None:
        self.config = config or CVaRConfig()

    def compute(
        self,
        returns: list[float],
        portfolio_value: float = 0.0,
        confidence: Optional[float] = None,
        horizon_days: Optional[int] = None,
        method: Optional[str] = None,
    ) -> CVaRResult:
        """Compute CVaR for a return series.

        Args:
            returns: Historical portfolio returns (daily).
            portfolio_value: Current portfolio value.
            confidence: Confidence level (default: config).
            horizon_days: Holding period (default: config).
            method: "historical", "parametric", or "cornish_fisher".

        Returns:
            CVaRResult.
        """
        conf = confidence or self.config.confidence
        horizon = horizon_days or self.config.horizon_days
        meth = method or self.config.method.value

        if len(returns) < self.config.min_observations:
            return CVaRResult(
                confidence=conf, horizon_days=horizon,
                portfolio_value=portfolio_value, method=meth,
            )

        arr = np.array(returns)

        if meth == CVaRMethod.PARAMETRIC.value:
            var_pct, cvar_pct = self._parametric(arr, conf)
        elif meth == CVaRMethod.CORNISH_FISHER.value:
            var_pct, cvar_pct = self._cornish_fisher(arr, conf)
        else:
            var_pct, cvar_pct = self._historical(arr, conf)

        # Horizon scaling (sqrt-T)
        scale = np.sqrt(horizon)
        var_pct *= scale
        cvar_pct *= scale

        # Tail ratio: CVaR / VaR
        tail_ratio = cvar_pct / var_pct if var_pct > 0 else 1.0

        return CVaRResult(
            confidence=conf,
            horizon_days=horizon,
            var_pct=round(float(var_pct), 6),
            cvar_pct=round(float(cvar_pct), 6),
            var_dollar=round(float(var_pct * portfolio_value), 2),
            cvar_dollar=round(float(cvar_pct * portfolio_value), 2),
            portfolio_value=portfolio_value,
            method=meth,
            n_observations=len(returns),
            tail_ratio=round(float(tail_ratio), 4),
        )

    def decompose(
        self,
        asset_returns: dict[str, list[float]],
        weights: dict[str, float],
        portfolio_value: float = 0.0,
        confidence: Optional[float] = None,
    ) -> list[CVaRContribution]:
        """Decompose CVaR by asset contribution.

        Uses marginal CVaR: dCVaR/dw_i.

        Args:
            asset_returns: Dict of {asset: return_series}.
            weights: Dict of {asset: weight}.
            portfolio_value: Portfolio value.
            confidence: Confidence level.

        Returns:
            List of CVaRContribution.
        """
        conf = confidence or self.config.confidence
        assets = list(asset_returns.keys())

        if not assets:
            return []

        # Align lengths
        min_len = min(len(r) for r in asset_returns.values())
        if min_len < self.config.min_observations:
            return []

        # Compute portfolio returns
        port_returns = np.zeros(min_len)
        for asset in assets:
            w = weights.get(asset, 0.0)
            r = np.array(asset_returns[asset][-min_len:])
            port_returns += w * r

        # Portfolio CVaR
        _, port_cvar = self._historical(port_returns, conf)
        if port_cvar == 0:
            return []

        # Identify tail observations
        cutoff = np.percentile(port_returns, (1 - conf) * 100)
        tail_mask = port_returns <= cutoff

        results = []
        for asset in assets:
            w = weights.get(asset, 0.0)
            r = np.array(asset_returns[asset][-min_len:])

            # Marginal CVaR: E[r_i | portfolio in tail]
            if tail_mask.sum() > 0:
                marginal = abs(float(np.mean(r[tail_mask])))
            else:
                marginal = 0.0

            # Component CVaR: w_i * marginal_cvar_i
            component = w * marginal
            pct = component / port_cvar if port_cvar > 0 else 0.0

            results.append(CVaRContribution(
                asset=asset,
                weight=round(w, 4),
                marginal_cvar=round(marginal, 6),
                component_cvar=round(component, 6),
                pct_of_total=round(float(pct), 4),
            ))

        results.sort(key=lambda x: x.component_cvar, reverse=True)
        return results

    def multi_horizon(
        self,
        returns: list[float],
        portfolio_value: float,
        horizons: Optional[list[int]] = None,
        confidence: Optional[float] = None,
    ) -> list[CVaRResult]:
        """Compute CVaR at multiple horizons.

        Args:
            returns: Return series.
            portfolio_value: Portfolio value.
            horizons: List of horizon days (default: [1,5,10,20]).
            confidence: Confidence level.

        Returns:
            List of CVaRResult.
        """
        horizons = horizons or [1, 5, 10, 20]
        return [
            self.compute(returns, portfolio_value, confidence, h)
            for h in horizons
        ]

    def _historical(self, arr: np.ndarray, confidence: float) -> tuple[float, float]:
        """Historical VaR and CVaR."""
        cutoff = np.percentile(arr, (1 - confidence) * 100)
        var = abs(float(cutoff))
        tail = arr[arr <= cutoff]
        cvar = abs(float(np.mean(tail))) if len(tail) > 0 else var
        return var, cvar

    def _parametric(self, arr: np.ndarray, confidence: float) -> tuple[float, float]:
        """Parametric (Gaussian) VaR and CVaR."""
        mu = np.mean(arr)
        sigma = np.std(arr, ddof=1)
        z_var = sp_stats.norm.ppf(1 - confidence)
        var = abs(mu + z_var * sigma)

        # Gaussian CVaR: mu - sigma * phi(z) / (1-alpha)
        phi_z = sp_stats.norm.pdf(z_var)
        cvar = abs(mu - sigma * phi_z / (1 - confidence))
        return var, cvar

    def _cornish_fisher(self, arr: np.ndarray, confidence: float) -> tuple[float, float]:
        """Cornish-Fisher adjusted VaR and CVaR.

        Adjusts the Gaussian quantile for skewness and excess kurtosis.
        """
        mu = np.mean(arr)
        sigma = np.std(arr, ddof=1)
        skew = float(sp_stats.skew(arr))
        kurt = float(sp_stats.kurtosis(arr))

        z = sp_stats.norm.ppf(1 - confidence)

        # Cornish-Fisher expansion
        z_cf = (
            z
            + (z**2 - 1) * skew / 6
            + (z**3 - 3 * z) * kurt / 24
            - (2 * z**3 - 5 * z) * skew**2 / 36
        )

        var = abs(mu + z_cf * sigma)

        # CVaR approximation: use historical tail beyond CF-VaR
        cutoff = mu + z_cf * sigma
        tail = arr[arr <= cutoff]
        cvar = abs(float(np.mean(tail))) if len(tail) > 0 else var

        return var, cvar
