"""Black-Litterman Model.

Combines market equilibrium returns with investor views
to produce posterior expected returns for optimization.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import OptimizationConfig

logger = logging.getLogger(__name__)


@dataclass
class View:
    """Single investor view for Black-Litterman.

    Absolute view: "AAPL returns 12% annually" (assets=['AAPL'], weights=[1], return_=0.12)
    Relative view: "AAPL outperforms MSFT by 2%" (assets=['AAPL','MSFT'], weights=[1,-1], return_=0.02)
    """

    assets: list = field(default_factory=list)
    weights: list = field(default_factory=list)
    expected_return: float = 0.0
    confidence: float = 0.5  # 0 to 1


@dataclass
class BLResult:
    """Black-Litterman posterior result."""

    prior_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    posterior_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    posterior_cov: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())

    def to_dict(self) -> dict:
        return {
            "prior_returns": self.prior_returns.to_dict(),
            "posterior_returns": self.posterior_returns.to_dict(),
        }


class BlackLittermanModel:
    """Black-Litterman asset allocation model.

    Combines market-implied equilibrium returns with factor model
    views to produce posterior expected returns.

    Example:
        bl = BlackLittermanModel()
        views = [
            View(assets=["AAPL"], weights=[1], expected_return=0.12, confidence=0.8),
            View(assets=["NVDA","INTC"], weights=[1,-1], expected_return=0.05, confidence=0.6),
        ]
        result = bl.compute_posterior(cov_matrix, market_weights, views)
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def implied_equilibrium_returns(
        self,
        cov_matrix: pd.DataFrame,
        market_weights: pd.Series,
        risk_aversion: Optional[float] = None,
    ) -> pd.Series:
        """Compute implied equilibrium returns (pi).

        pi = lambda * Sigma * w_mkt

        Args:
            cov_matrix: Covariance matrix.
            market_weights: Market capitalization weights.
            risk_aversion: Risk aversion coefficient.

        Returns:
            Series of implied equilibrium returns.
        """
        lam = risk_aversion or self.config.risk_aversion
        pi = lam * cov_matrix.values @ market_weights.values
        return pd.Series(pi, index=cov_matrix.index)

    def compute_posterior(
        self,
        cov_matrix: pd.DataFrame,
        market_weights: pd.Series,
        views: list[View],
        tau: Optional[float] = None,
        risk_aversion: Optional[float] = None,
    ) -> BLResult:
        """Compute Black-Litterman posterior returns.

        Args:
            cov_matrix: Covariance matrix.
            market_weights: Market cap weights.
            views: Investor views.
            tau: Uncertainty scalar.
            risk_aversion: Risk aversion parameter.

        Returns:
            BLResult with prior and posterior returns.
        """
        tau = tau or self.config.tau
        assets = cov_matrix.index.tolist()
        n = len(assets)

        # Prior: implied equilibrium
        pi = self.implied_equilibrium_returns(cov_matrix, market_weights, risk_aversion)

        if not views:
            return BLResult(
                prior_returns=pi,
                posterior_returns=pi,
                posterior_cov=cov_matrix * (1 + tau),
            )

        Sigma = cov_matrix.values
        tau_Sigma = tau * Sigma

        # Build view matrices
        P, Q, Omega = self._build_view_matrices(views, assets, Sigma, tau)

        # Posterior returns: combined formula
        inv_tau_Sigma = np.linalg.inv(tau_Sigma)
        inv_Omega = np.linalg.inv(Omega)

        M = np.linalg.inv(inv_tau_Sigma + P.T @ inv_Omega @ P)
        posterior = M @ (inv_tau_Sigma @ pi.values + P.T @ inv_Omega @ Q)

        posterior_returns = pd.Series(posterior, index=assets)

        # Posterior covariance
        posterior_cov = pd.DataFrame(
            Sigma + M,
            index=assets,
            columns=assets,
        )

        return BLResult(
            prior_returns=pi,
            posterior_returns=posterior_returns,
            posterior_cov=posterior_cov,
        )

    def _build_view_matrices(
        self,
        views: list[View],
        assets: list[str],
        Sigma: np.ndarray,
        tau: float,
    ) -> tuple:
        """Build P (pick matrix), Q (view returns), Omega (view uncertainty).

        Returns:
            Tuple of (P, Q, Omega).
        """
        n_assets = len(assets)
        n_views = len(views)
        asset_idx = {a: i for i, a in enumerate(assets)}

        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)

        for i, view in enumerate(views):
            Q[i] = view.expected_return
            for asset, weight in zip(view.assets, view.weights):
                if asset in asset_idx:
                    P[i, asset_idx[asset]] = weight

        # Omega: diagonal view uncertainty matrix
        # Higher confidence -> lower uncertainty
        Omega = np.zeros((n_views, n_views))
        for i, view in enumerate(views):
            # Proportional to implied variance of the view portfolio
            view_var = float(P[i] @ (tau * Sigma) @ P[i])
            confidence_scale = max(1 - view.confidence, 0.01)
            Omega[i, i] = view_var / confidence_scale

        return P, Q, Omega
