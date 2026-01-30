"""Portfolio Optimization Objectives.

Implements Mean-Variance, Risk Parity, Minimum Variance,
and Hierarchical Risk Parity optimization methods.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import OptimizationConfig

try:
    from scipy.optimize import minimize
    from scipy.cluster.hierarchy import linkage, leaves_list
    from scipy.spatial.distance import squareform
    SCIPY_AVAILABLE = True
except (ImportError, ValueError):
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result from portfolio optimization."""

    weights: dict = field(default_factory=dict)
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    method: str = ""
    converged: bool = True
    message: str = ""

    def to_series(self) -> pd.Series:
        return pd.Series(self.weights)

    def to_dict(self) -> dict:
        return {
            "weights": self.weights,
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "method": self.method,
            "converged": self.converged,
        }


class MeanVarianceOptimizer:
    """Mean-Variance (Markowitz) portfolio optimization.

    Minimizes portfolio variance for a given return target,
    or maximizes Sharpe ratio.

    Example:
        opt = MeanVarianceOptimizer()
        result = opt.max_sharpe(expected_returns, cov_matrix)
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        target_return: Optional[float] = None,
        min_weight: float = 0.0,
        max_weight: float = 0.15,
    ) -> OptimizationResult:
        """Optimize for minimum variance at target return.

        Args:
            expected_returns: Expected returns per asset.
            cov_matrix: Covariance matrix.
            target_return: Target portfolio return (None = max Sharpe).
            min_weight: Minimum weight per asset.
            max_weight: Maximum weight per asset.

        Returns:
            OptimizationResult with optimal weights.
        """
        if target_return is None:
            return self.max_sharpe(expected_returns, cov_matrix, min_weight, max_weight)

        n = len(expected_returns)
        cov = cov_matrix.values

        def objective(w):
            return float(w @ cov @ w)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "ineq", "fun": lambda w: w @ expected_returns.values - target_return},
        ]
        bounds = [(min_weight, max_weight)] * n

        result = minimize(
            objective,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.config.max_iterations},
        )

        weights = dict(zip(expected_returns.index, result.x))
        w = result.x
        vol = float(np.sqrt(w @ cov @ w))
        ret = float(w @ expected_returns.values)
        rf = self.config.risk_free_rate
        sharpe = (ret - rf) / vol if vol > 0 else 0.0

        return OptimizationResult(
            weights=weights,
            expected_return=ret,
            expected_volatility=vol,
            sharpe_ratio=sharpe,
            method="mean_variance",
            converged=result.success,
            message=result.message,
        )

    def max_sharpe(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        min_weight: float = 0.0,
        max_weight: float = 0.15,
    ) -> OptimizationResult:
        """Maximize Sharpe ratio (tangency portfolio).

        Args:
            expected_returns: Expected returns.
            cov_matrix: Covariance matrix.
            min_weight: Minimum weight.
            max_weight: Maximum weight.

        Returns:
            OptimizationResult.
        """
        n = len(expected_returns)
        cov = cov_matrix.values
        rf = self.config.risk_free_rate

        def neg_sharpe(w):
            ret = float(w @ expected_returns.values)
            vol = float(np.sqrt(w @ cov @ w))
            if vol < 1e-10:
                return 0.0
            return -(ret - rf) / vol

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(min_weight, max_weight)] * n

        result = minimize(
            neg_sharpe,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.config.max_iterations},
        )

        w = result.x
        weights = dict(zip(expected_returns.index, w))
        ret = float(w @ expected_returns.values)
        vol = float(np.sqrt(w @ cov @ w))
        sharpe = (ret - rf) / vol if vol > 0 else 0.0

        return OptimizationResult(
            weights=weights,
            expected_return=ret,
            expected_volatility=vol,
            sharpe_ratio=sharpe,
            method="max_sharpe",
            converged=result.success,
            message=result.message,
        )

    def min_variance(
        self,
        cov_matrix: pd.DataFrame,
        min_weight: float = 0.0,
        max_weight: float = 0.15,
    ) -> OptimizationResult:
        """Find minimum variance portfolio.

        Args:
            cov_matrix: Covariance matrix.
            min_weight: Minimum weight.
            max_weight: Maximum weight.

        Returns:
            OptimizationResult.
        """
        n = len(cov_matrix)
        cov = cov_matrix.values

        def objective(w):
            return float(w @ cov @ w)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(min_weight, max_weight)] * n

        result = minimize(
            objective,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.config.max_iterations},
        )

        w = result.x
        weights = dict(zip(cov_matrix.index, w))
        vol = float(np.sqrt(w @ cov @ w))

        return OptimizationResult(
            weights=weights,
            expected_volatility=vol,
            method="min_variance",
            converged=result.success,
            message=result.message,
        )

    def efficient_frontier(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        n_points: int = 20,
        min_weight: float = 0.0,
        max_weight: float = 0.15,
    ) -> list[OptimizationResult]:
        """Generate efficient frontier points.

        Args:
            expected_returns: Expected returns.
            cov_matrix: Covariance matrix.
            n_points: Number of frontier points.
            min_weight: Minimum weight.
            max_weight: Maximum weight.

        Returns:
            List of OptimizationResult along the frontier.
        """
        # Find return range
        min_var = self.min_variance(cov_matrix, min_weight, max_weight)
        max_ret_port = self.max_sharpe(expected_returns, cov_matrix, min_weight, max_weight)

        min_ret = min_var.expected_return if min_var.expected_return > 0 else expected_returns.min()
        max_ret = max(expected_returns.max(), max_ret_port.expected_return)

        target_returns = np.linspace(min_ret, max_ret * 0.95, n_points)
        frontier = []

        for target in target_returns:
            try:
                result = self.optimize(
                    expected_returns, cov_matrix,
                    target_return=target,
                    min_weight=min_weight, max_weight=max_weight,
                )
                if result.converged:
                    frontier.append(result)
            except Exception:
                continue

        return frontier


class RiskParityOptimizer:
    """Risk Parity portfolio optimization.

    Equalizes risk contribution from each asset.

    Example:
        opt = RiskParityOptimizer()
        result = opt.optimize(cov_matrix)
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        self.config = config or OptimizationConfig()

    def optimize(
        self,
        cov_matrix: pd.DataFrame,
        min_weight: float = 0.01,
        max_weight: float = 0.30,
    ) -> OptimizationResult:
        """Find risk parity weights.

        Args:
            cov_matrix: Covariance matrix.
            min_weight: Minimum weight per asset.
            max_weight: Maximum weight per asset.

        Returns:
            OptimizationResult with risk parity weights.
        """
        n = len(cov_matrix)
        cov = cov_matrix.values

        def risk_contribution_error(w):
            port_var = w @ cov @ w
            if port_var < 1e-12:
                return 1e10
            port_vol = np.sqrt(port_var)
            marginal = cov @ w
            risk_contrib = w * marginal / port_vol
            target = port_vol / n
            return float(np.sum((risk_contrib - target) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(min_weight, max_weight)] * n

        result = minimize(
            risk_contribution_error,
            x0=np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": self.config.max_iterations},
        )

        w = result.x
        weights = dict(zip(cov_matrix.index, w))
        vol = float(np.sqrt(w @ cov @ w))

        return OptimizationResult(
            weights=weights,
            expected_volatility=vol,
            method="risk_parity",
            converged=result.success,
            message=result.message,
        )

    def get_risk_contributions(
        self,
        weights: pd.Series,
        cov_matrix: pd.DataFrame,
    ) -> pd.Series:
        """Compute risk contribution of each asset.

        Args:
            weights: Portfolio weights.
            cov_matrix: Covariance matrix.

        Returns:
            Series of risk contributions (sum to 1).
        """
        w = weights.values
        cov = cov_matrix.values
        port_vol = np.sqrt(w @ cov @ w)

        if port_vol < 1e-12:
            return pd.Series(0, index=weights.index)

        marginal = cov @ w
        risk_contrib = w * marginal / port_vol
        total = risk_contrib.sum()

        if total > 0:
            risk_contrib = risk_contrib / total

        return pd.Series(risk_contrib, index=weights.index)


class HRPOptimizer:
    """Hierarchical Risk Parity optimization.

    Uses correlation-based hierarchical clustering and recursive
    bisection. More stable than MVO, requires no matrix inversion.

    Example:
        opt = HRPOptimizer()
        result = opt.optimize(returns_df)
    """

    def optimize(
        self,
        returns: pd.DataFrame,
    ) -> OptimizationResult:
        """Run HRP optimization.

        Args:
            returns: Historical returns DataFrame (assets as columns).

        Returns:
            OptimizationResult.
        """
        if not SCIPY_AVAILABLE:
            # Fallback: equal weight
            n = returns.shape[1]
            weights = dict(zip(returns.columns, [1.0 / n] * n))
            return OptimizationResult(
                weights=weights, method="hrp_equal_weight_fallback",
                message="scipy not available, using equal weights",
            )

        cov = returns.cov()
        corr = returns.corr()

        # 1. Correlation distance
        dist = self._correlation_distance(corr)

        # 2. Hierarchical clustering
        condensed = squareform(dist, checks=False)
        link = linkage(condensed, method="single")

        # 3. Quasi-diagonalization
        sort_ix = list(leaves_list(link))

        # 4. Recursive bisection
        sorted_cols = [returns.columns[i] for i in sort_ix]
        weights = self._recursive_bisection(cov, sorted_cols)

        w_arr = np.array([weights[c] for c in returns.columns])
        vol = float(np.sqrt(w_arr @ cov.values @ w_arr))

        return OptimizationResult(
            weights=weights,
            expected_volatility=vol,
            method="hrp",
            converged=True,
        )

    def _correlation_distance(self, corr: pd.DataFrame) -> np.ndarray:
        """Convert correlation matrix to distance matrix."""
        return np.sqrt(0.5 * (1 - corr.values))

    def _recursive_bisection(
        self,
        cov: pd.DataFrame,
        sorted_cols: list[str],
    ) -> dict[str, float]:
        """Recursively bisect the portfolio by cluster."""
        weights = {c: 1.0 for c in sorted_cols}

        clusters = [sorted_cols]

        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue

                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]

                # Cluster variances
                left_var = self._cluster_variance(cov, left)
                right_var = self._cluster_variance(cov, right)

                total_var = left_var + right_var
                if total_var < 1e-12:
                    alpha = 0.5
                else:
                    alpha = 1 - left_var / total_var  # Inverse variance weighting

                for c in left:
                    weights[c] *= alpha
                for c in right:
                    weights[c] *= (1 - alpha)

                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)

            clusters = new_clusters

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _cluster_variance(self, cov: pd.DataFrame, assets: list[str]) -> float:
        """Compute inverse-variance weighted cluster variance."""
        sub_cov = cov.loc[assets, assets].values
        ivp = 1.0 / np.diag(sub_cov)
        ivp = ivp / ivp.sum()
        return float(ivp @ sub_cov @ ivp)
