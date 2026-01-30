"""Value at Risk (VaR) and Conditional VaR Calculations.

Implements three VaR methodologies:
1. Historical Simulation
2. Parametric (Variance-Covariance)
3. Monte Carlo Simulation

Also calculates Expected Shortfall (CVaR).
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Make scipy optional due to potential version conflicts
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except (ImportError, ValueError):
    SCIPY_AVAILABLE = False
    stats = None

logger = logging.getLogger(__name__)


# Helper functions for normal distribution when scipy is unavailable
def _norm_ppf(p: float) -> float:
    """Approximate inverse normal CDF (percent point function).

    Uses Abramowitz and Stegun approximation.
    """
    if SCIPY_AVAILABLE:
        return stats.norm.ppf(p)

    # Approximation for standard normal inverse CDF
    if p <= 0:
        return -np.inf
    if p >= 1:
        return np.inf
    if p == 0.5:
        return 0.0

    # Rational approximation
    if p < 0.5:
        t = np.sqrt(-2.0 * np.log(p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return -(t - (c0 + c1*t + c2*t*t) / (1 + d1*t + d2*t*t + d3*t*t*t))
    else:
        t = np.sqrt(-2.0 * np.log(1 - p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return t - (c0 + c1*t + c2*t*t) / (1 + d1*t + d2*t*t + d3*t*t*t)


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    if SCIPY_AVAILABLE:
        return stats.norm.pdf(x)
    return np.exp(-0.5 * x * x) / np.sqrt(2 * np.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using error function."""
    if SCIPY_AVAILABLE:
        return stats.norm.cdf(x)
    # Use math module's error function
    import math
    return 0.5 * (1 + math.erf(x / np.sqrt(2)))


@dataclass
class VaRResult:
    """Result of VaR calculation."""

    var_95: float = 0.0  # 95% VaR as positive value (loss)
    var_99: float = 0.0  # 99% VaR
    cvar_95: float = 0.0  # Expected Shortfall at 95%
    cvar_99: float = 0.0  # Expected Shortfall at 99%
    method: str = ""  # 'historical', 'parametric', 'monte_carlo'
    horizon_days: int = 1
    portfolio_value: float = 0.0
    returns_distribution: Optional[np.ndarray] = None  # For visualization

    @property
    def var_95_pct(self) -> float:
        """VaR as percentage of portfolio."""
        return self.var_95 / self.portfolio_value if self.portfolio_value > 0 else 0

    @property
    def var_99_pct(self) -> float:
        """VaR as percentage of portfolio."""
        return self.var_99 / self.portfolio_value if self.portfolio_value > 0 else 0

    @property
    def cvar_95_pct(self) -> float:
        """CVaR as percentage of portfolio."""
        return self.cvar_95 / self.portfolio_value if self.portfolio_value > 0 else 0


class VaRCalculator:
    """Calculate Value at Risk using multiple methodologies.

    Example:
        calculator = VaRCalculator()

        # Historical VaR
        var_result = calculator.historical_var(
            returns=portfolio_returns,
            portfolio_value=100_000,
        )
        print(f"95% VaR: ${var_result.var_95:,.2f}")

        # Monte Carlo VaR
        mc_result = calculator.monte_carlo_var(
            weights=weights,
            covariance_matrix=cov_matrix,
            portfolio_value=100_000,
        )
    """

    TRADING_DAYS_PER_YEAR = 252

    def __init__(
        self,
        confidence_levels: tuple[float, ...] = (0.95, 0.99),
        horizon_days: int = 1,
    ):
        """Initialize VaR calculator.

        Args:
            confidence_levels: Confidence levels for VaR calculation.
            horizon_days: Time horizon in trading days.
        """
        self.confidence_levels = confidence_levels
        self.horizon_days = horizon_days

    # =========================================================================
    # Simple VaR Methods (return percentage VaR for single return series)
    # =========================================================================

    def historical_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        portfolio_value: Optional[float] = None,
    ) -> float:
        """Calculate VaR using historical simulation.

        Args:
            returns: Historical daily returns.
            confidence: Confidence level (e.g., 0.95 for 95%).
            portfolio_value: If provided, returns dollar VaR; otherwise percentage.

        Returns:
            VaR as negative percentage or dollar amount.
        """
        returns = returns.dropna()
        if len(returns) < 10:
            logger.warning("Insufficient data for historical VaR")
            return 0.0

        # Scale for horizon
        if self.horizon_days > 1:
            scaled_returns = returns.rolling(self.horizon_days).sum().dropna()
        else:
            scaled_returns = returns

        # VaR is the (1 - confidence) percentile
        var_pct = np.percentile(scaled_returns, (1 - confidence) * 100)

        if portfolio_value is not None:
            return var_pct * portfolio_value
        return var_pct

    def parametric_var(
        self,
        returns_or_value: pd.Series | float,
        confidence: float = 0.95,
        volatility: Optional[float] = None,
    ) -> float:
        """Calculate VaR using parametric method.

        Args:
            returns_or_value: Either a returns series or portfolio value.
            confidence: Confidence level.
            volatility: Annualized volatility (required if returns_or_value is float).

        Returns:
            VaR as negative percentage or dollar amount.
        """
        if isinstance(returns_or_value, pd.Series):
            # Calculate from returns
            returns = returns_or_value.dropna()
            if len(returns) < 10:
                return 0.0

            vol = returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
            daily_vol = vol / np.sqrt(self.TRADING_DAYS_PER_YEAR)
            scaled_vol = daily_vol * np.sqrt(self.horizon_days)

            z_score = _norm_ppf(1 - confidence)
            return z_score * scaled_vol
        else:
            # Portfolio value and volatility provided
            if volatility is None:
                raise ValueError("volatility required when providing portfolio_value")
            return self._parametric_var_dollar(returns_or_value, volatility, confidence)

    def monte_carlo_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        num_simulations: int = 10_000,
    ) -> float:
        """Calculate VaR using Monte Carlo simulation on single return series.

        Args:
            returns: Historical daily returns.
            confidence: Confidence level.
            num_simulations: Number of simulations.

        Returns:
            VaR as negative percentage.
        """
        returns = returns.dropna()
        if len(returns) < 10:
            return 0.0

        mean = returns.mean()
        std = returns.std()

        # Simulate returns
        simulated = np.random.normal(mean, std, num_simulations)

        # Scale for horizon
        if self.horizon_days > 1:
            simulated = simulated * np.sqrt(self.horizon_days)

        var_pct = np.percentile(simulated, (1 - confidence) * 100)
        return var_pct

    # =========================================================================
    # Historical Simulation (Dollar VaR)
    # =========================================================================

    def _parametric_var_dollar(
        self,
        portfolio_value: float,
        volatility: float,
        confidence: float = 0.95,
    ) -> float:
        """Calculate VaR using parametric method (assumes normal distribution).

        Args:
            portfolio_value: Current portfolio value.
            volatility: Annualized portfolio volatility.
            confidence: Confidence level.

        Returns:
            VaR as negative dollar amount.
        """
        # Convert annualized vol to daily
        daily_vol = volatility / np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # Scale for horizon
        scaled_vol = daily_vol * np.sqrt(self.horizon_days)

        # Z-score for confidence level (negative for loss)
        z_score = _norm_ppf(1 - confidence)

        return portfolio_value * scaled_vol * z_score

    def historical_var_full(
        self,
        returns: pd.Series,
        portfolio_value: float,
    ) -> VaRResult:
        """Calculate comprehensive historical VaR metrics.

        Args:
            returns: Historical daily returns.
            portfolio_value: Current portfolio value.

        Returns:
            VaRResult with all VaR and CVaR values.
        """
        returns = returns.dropna()

        result = VaRResult(
            method="historical",
            horizon_days=self.horizon_days,
            portfolio_value=portfolio_value,
        )

        if len(returns) < 10:
            return result

        # Scale for horizon
        if self.horizon_days > 1:
            scaled_returns = returns.rolling(self.horizon_days).sum().dropna()
        else:
            scaled_returns = returns

        # VaR at different confidence levels
        result.var_95 = -np.percentile(scaled_returns, 5) * portfolio_value
        result.var_99 = -np.percentile(scaled_returns, 1) * portfolio_value

        # CVaR (Expected Shortfall)
        var_95_threshold = np.percentile(scaled_returns, 5)
        var_99_threshold = np.percentile(scaled_returns, 1)

        result.cvar_95 = -scaled_returns[scaled_returns <= var_95_threshold].mean() * portfolio_value
        result.cvar_99 = -scaled_returns[scaled_returns <= var_99_threshold].mean() * portfolio_value

        # Store returns for visualization
        result.returns_distribution = scaled_returns.values

        return result

    # =========================================================================
    # Parametric (Variance-Covariance) - Full Results
    # =========================================================================

    def parametric_var_full(
        self,
        portfolio_value: float,
        volatility: float,
        expected_return: float = 0.0,
    ) -> VaRResult:
        """Calculate comprehensive parametric VaR metrics.

        Args:
            portfolio_value: Current portfolio value.
            volatility: Annualized portfolio volatility.
            expected_return: Expected daily return (usually assumed 0).

        Returns:
            VaRResult with all metrics.
        """
        result = VaRResult(
            method="parametric",
            horizon_days=self.horizon_days,
            portfolio_value=portfolio_value,
        )

        # Convert to daily and scale
        daily_vol = volatility / np.sqrt(self.TRADING_DAYS_PER_YEAR)
        scaled_vol = daily_vol * np.sqrt(self.horizon_days)
        daily_return = expected_return / self.TRADING_DAYS_PER_YEAR
        scaled_return = daily_return * self.horizon_days

        # VaR at different confidence levels
        z_95 = _norm_ppf(0.95)
        z_99 = _norm_ppf(0.99)

        result.var_95 = portfolio_value * (z_95 * scaled_vol - scaled_return)
        result.var_99 = portfolio_value * (z_99 * scaled_vol - scaled_return)

        # CVaR for normal distribution
        # E[X | X > VaR] = μ + σ * φ(z) / (1 - Φ(z))
        # where φ is PDF and Φ is CDF
        def normal_cvar(z: float, sigma: float, mu: float) -> float:
            pdf = _norm_pdf(z)
            cdf = _norm_cdf(z)
            if cdf < 1:
                return mu + sigma * pdf / (1 - cdf)
            return mu + sigma * z

        result.cvar_95 = portfolio_value * normal_cvar(z_95, scaled_vol, -scaled_return)
        result.cvar_99 = portfolio_value * normal_cvar(z_99, scaled_vol, -scaled_return)

        return result

    # =========================================================================
    # Monte Carlo Simulation (Portfolio Level)
    # =========================================================================

    def monte_carlo_var_portfolio(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        portfolio_value: float,
        expected_returns: Optional[np.ndarray] = None,
        n_simulations: int = 10_000,
        confidence: float = 0.95,
    ) -> float:
        """Calculate VaR using Monte Carlo simulation on portfolio.

        Simulates correlated returns using multivariate normal distribution.

        Args:
            weights: Portfolio weights array.
            covariance_matrix: Asset covariance matrix (annualized).
            portfolio_value: Current portfolio value.
            expected_returns: Expected returns (assumed 0 if not provided).
            n_simulations: Number of Monte Carlo paths.
            confidence: Confidence level.

        Returns:
            VaR as positive dollar amount.
        """
        n_assets = len(weights)

        if expected_returns is None:
            expected_returns = np.zeros(n_assets)

        # Scale covariance for daily and horizon
        daily_cov = covariance_matrix / self.TRADING_DAYS_PER_YEAR
        scaled_cov = daily_cov * self.horizon_days
        scaled_returns = expected_returns / self.TRADING_DAYS_PER_YEAR * self.horizon_days

        # Simulate correlated returns
        try:
            simulated = np.random.multivariate_normal(
                mean=scaled_returns,
                cov=scaled_cov,
                size=n_simulations,
            )
        except (np.linalg.LinAlgError, ValueError) as e:
            logger.warning(f"Monte Carlo simulation failed: {e}, using diagonal")
            # Fall back to independent simulation
            variances = np.diag(scaled_cov)
            simulated = np.random.normal(
                loc=scaled_returns,
                scale=np.sqrt(variances),
                size=(n_simulations, n_assets),
            )

        # Calculate portfolio returns
        portfolio_returns = simulated @ weights

        # VaR
        var_pct = -np.percentile(portfolio_returns, (1 - confidence) * 100)

        return var_pct * portfolio_value

    def monte_carlo_var_full(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        portfolio_value: float,
        expected_returns: Optional[np.ndarray] = None,
        n_simulations: int = 10_000,
    ) -> VaRResult:
        """Calculate comprehensive Monte Carlo VaR metrics.

        Args:
            weights: Portfolio weights array.
            covariance_matrix: Asset covariance matrix.
            portfolio_value: Current portfolio value.
            expected_returns: Expected returns.
            n_simulations: Number of simulations.

        Returns:
            VaRResult with all metrics.
        """
        result = VaRResult(
            method="monte_carlo",
            horizon_days=self.horizon_days,
            portfolio_value=portfolio_value,
        )

        n_assets = len(weights)

        if expected_returns is None:
            expected_returns = np.zeros(n_assets)

        # Scale covariance
        daily_cov = covariance_matrix / self.TRADING_DAYS_PER_YEAR
        scaled_cov = daily_cov * self.horizon_days
        scaled_returns = expected_returns / self.TRADING_DAYS_PER_YEAR * self.horizon_days

        # Simulate
        try:
            simulated = np.random.multivariate_normal(
                mean=scaled_returns,
                cov=scaled_cov,
                size=n_simulations,
            )
        except (np.linalg.LinAlgError, ValueError):
            variances = np.diag(scaled_cov)
            simulated = np.random.normal(
                loc=scaled_returns,
                scale=np.sqrt(variances),
                size=(n_simulations, n_assets),
            )

        portfolio_returns = simulated @ weights

        # VaR at different confidence levels
        result.var_95 = -np.percentile(portfolio_returns, 5) * portfolio_value
        result.var_99 = -np.percentile(portfolio_returns, 1) * portfolio_value

        # CVaR
        var_95_threshold = np.percentile(portfolio_returns, 5)
        var_99_threshold = np.percentile(portfolio_returns, 1)

        result.cvar_95 = -portfolio_returns[portfolio_returns <= var_95_threshold].mean() * portfolio_value
        result.cvar_99 = -portfolio_returns[portfolio_returns <= var_99_threshold].mean() * portfolio_value

        return result

    # =========================================================================
    # Component VaR
    # =========================================================================

    def component_var(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        portfolio_value: float,
        symbols: list[str],
        confidence: float = 0.95,
    ) -> dict[str, float]:
        """Calculate VaR contribution by each position.

        Component VaR shows how much each position contributes to total portfolio VaR.

        Args:
            weights: Portfolio weights array.
            covariance_matrix: Asset covariance matrix.
            portfolio_value: Current portfolio value.
            symbols: List of asset symbols.
            confidence: Confidence level.

        Returns:
            Dict mapping symbol to VaR contribution.
        """
        # Portfolio variance
        portfolio_var = weights @ covariance_matrix @ weights

        if portfolio_var <= 0:
            return {s: 0.0 for s in symbols}

        portfolio_vol = np.sqrt(portfolio_var)

        # Marginal VaR for each asset
        marginal_var = (covariance_matrix @ weights) / portfolio_vol

        # Component VaR
        component_vars = weights * marginal_var

        # Scale to VaR
        z_score = _norm_ppf(confidence)
        daily_vol = portfolio_vol / np.sqrt(self.TRADING_DAYS_PER_YEAR)
        var_scalar = portfolio_value * z_score * daily_vol * np.sqrt(self.horizon_days)

        result = {}
        for i, symbol in enumerate(symbols):
            result[symbol] = component_vars[i] / portfolio_var * var_scalar

        return result

    def marginal_var(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        portfolio_value: float,
        symbols: list[str],
        confidence: float = 0.95,
    ) -> dict[str, float]:
        """Calculate marginal VaR for each position.

        Marginal VaR shows how portfolio VaR would change if position is removed.

        Args:
            weights: Portfolio weights array.
            covariance_matrix: Asset covariance matrix.
            portfolio_value: Current portfolio value.
            symbols: List of asset symbols.
            confidence: Confidence level.

        Returns:
            Dict mapping symbol to marginal VaR.
        """
        # Calculate full portfolio VaR
        full_var = self.parametric_var(
            portfolio_value=portfolio_value,
            volatility=np.sqrt(weights @ covariance_matrix @ weights),
            confidence=confidence,
        )

        result = {}

        for i, symbol in enumerate(symbols):
            # Create weights without this position
            reduced_weights = weights.copy()
            reduced_weights[i] = 0
            total_weight = reduced_weights.sum()

            if total_weight > 0:
                reduced_weights = reduced_weights / total_weight

            # Calculate reduced VaR
            reduced_vol = np.sqrt(reduced_weights @ covariance_matrix @ reduced_weights)
            reduced_value = portfolio_value * (1 - weights[i])

            reduced_var = self.parametric_var(
                portfolio_value=reduced_value,
                volatility=reduced_vol,
                confidence=confidence,
            )

            # Marginal VaR is the difference
            result[symbol] = full_var - reduced_var

        return result
