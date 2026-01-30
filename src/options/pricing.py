"""Options Pricing Engine.

Implements Black-Scholes, Binomial Tree, Monte Carlo pricing
with full Greeks calculation and implied volatility solver.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from src.options.config import PricingConfig

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except (ImportError, ValueError):
    SCIPY_AVAILABLE = False
    norm = None

logger = logging.getLogger(__name__)


# ============================================================================
# Fallback normal distribution functions
# ============================================================================

def _norm_cdf(x: float) -> float:
    """Standard normal CDF."""
    if SCIPY_AVAILABLE:
        return float(norm.cdf(x))
    import math
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    if SCIPY_AVAILABLE:
        return float(norm.pdf(x))
    return np.exp(-0.5 * x * x) / np.sqrt(2.0 * np.pi)


def _norm_cdf_array(x: np.ndarray) -> np.ndarray:
    """Vectorized standard normal CDF."""
    if SCIPY_AVAILABLE:
        return norm.cdf(x)
    from numpy import vectorize
    import math
    vfunc = vectorize(lambda v: 0.5 * (1.0 + math.erf(v / math.sqrt(2.0))))
    return vfunc(x)


# ============================================================================
# Data Structures
# ============================================================================

class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class OptionPrice:
    """Complete option pricing result with Greeks."""

    price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    option_type: str = "call"
    model: str = "black_scholes"

    @property
    def intrinsic_value(self) -> float:
        return max(0, self.price)

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "option_type": self.option_type,
            "model": self.model,
        }


@dataclass
class OptionLeg:
    """Single leg of an options strategy."""

    option_type: str = "call"
    strike: float = 0.0
    premium: float = 0.0
    quantity: int = 1  # positive=long, negative=short
    expiry_days: int = 30
    iv: float = 0.30
    greeks: Optional[OptionPrice] = None


# ============================================================================
# Pricing Engine
# ============================================================================

class OptionsPricingEngine:
    """Options pricing with multiple models and Greeks.

    Supports Black-Scholes (European), Binomial Tree (American),
    and Monte Carlo (exotic/path-dependent) pricing.

    Example:
        engine = OptionsPricingEngine()
        result = engine.black_scholes(S=100, K=105, T=0.25, r=0.05, sigma=0.20)
        iv = engine.implied_volatility(market_price=5.0, S=100, K=105, T=0.25, r=0.05)
    """

    def __init__(self, config: Optional[PricingConfig] = None):
        self.config = config or PricingConfig()

    def black_scholes(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
        q: float = 0.0,
    ) -> OptionPrice:
        """Black-Scholes pricing with all Greeks.

        Args:
            S: Current underlying price.
            K: Strike price.
            T: Time to expiration in years.
            r: Risk-free rate.
            sigma: Volatility.
            option_type: 'call' or 'put'.
            q: Continuous dividend yield.

        Returns:
            OptionPrice with price and all Greeks.
        """
        if T <= 0 or sigma <= 0:
            intrinsic = max(S - K, 0) if option_type == "call" else max(K - S, 0)
            delta = 1.0 if (option_type == "call" and S > K) else (-1.0 if (option_type == "put" and S < K) else 0.0)
            return OptionPrice(price=intrinsic, delta=delta, option_type=option_type, model="black_scholes")

        sqrt_T = np.sqrt(T)
        d1 = (np.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        if option_type == "call":
            price = S * np.exp(-q * T) * _norm_cdf(d1) - K * np.exp(-r * T) * _norm_cdf(d2)
            delta = np.exp(-q * T) * _norm_cdf(d1)
            rho = K * T * np.exp(-r * T) * _norm_cdf(d2) / 100
        else:
            price = K * np.exp(-r * T) * _norm_cdf(-d2) - S * np.exp(-q * T) * _norm_cdf(-d1)
            delta = -np.exp(-q * T) * _norm_cdf(-d1)
            rho = -K * T * np.exp(-r * T) * _norm_cdf(-d2) / 100

        gamma = np.exp(-q * T) * _norm_pdf(d1) / (S * sigma * sqrt_T)
        vega = S * np.exp(-q * T) * _norm_pdf(d1) * sqrt_T / 100
        theta_call = (
            -S * np.exp(-q * T) * _norm_pdf(d1) * sigma / (2 * sqrt_T)
            - r * K * np.exp(-r * T) * _norm_cdf(d2)
            + q * S * np.exp(-q * T) * _norm_cdf(d1)
        ) / 365
        theta_put = (
            -S * np.exp(-q * T) * _norm_pdf(d1) * sigma / (2 * sqrt_T)
            + r * K * np.exp(-r * T) * _norm_cdf(-d2)
            - q * S * np.exp(-q * T) * _norm_cdf(-d1)
        ) / 365
        theta = theta_call if option_type == "call" else theta_put

        return OptionPrice(
            price=float(price),
            delta=float(delta),
            gamma=float(gamma),
            theta=float(theta),
            vega=float(vega),
            rho=float(rho),
            option_type=option_type,
            model="black_scholes",
        )

    def binomial_tree(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
        american: bool = True,
        n_steps: Optional[int] = None,
        q: float = 0.0,
    ) -> OptionPrice:
        """Binomial tree pricing (supports American options).

        Args:
            S: Current underlying price.
            K: Strike price.
            T: Time to expiration in years.
            r: Risk-free rate.
            sigma: Volatility.
            option_type: 'call' or 'put'.
            american: Whether to allow early exercise.
            n_steps: Number of tree steps.
            q: Dividend yield.

        Returns:
            OptionPrice with price and delta.
        """
        n = n_steps or self.config.binomial_steps

        if T <= 0 or sigma <= 0:
            intrinsic = max(S - K, 0) if option_type == "call" else max(K - S, 0)
            return OptionPrice(price=intrinsic, option_type=option_type, model="binomial")

        dt = T / n
        u = np.exp(sigma * np.sqrt(dt))
        d = 1.0 / u
        p = (np.exp((r - q) * dt) - d) / (u - d)
        disc = np.exp(-r * dt)

        # Build price tree at expiration
        prices = S * u ** np.arange(n, -1, -1) * d ** np.arange(0, n + 1)

        if option_type == "call":
            values = np.maximum(prices - K, 0)
        else:
            values = np.maximum(K - prices, 0)

        # Step back through tree
        for i in range(n - 1, -1, -1):
            values = disc * (p * values[:-1] + (1 - p) * values[1:])
            if american:
                prices_i = S * u ** np.arange(i, -1, -1) * d ** np.arange(0, i + 1)
                if option_type == "call":
                    exercise = np.maximum(prices_i - K, 0)
                else:
                    exercise = np.maximum(K - prices_i, 0)
                values = np.maximum(values, exercise)

        price = float(values[0])

        # Delta from first step
        delta = 0.0
        if n >= 1:
            v_up = disc * (p * values[0] + (1 - p) * values[0]) if len(values) == 1 else 0
            # Recalculate for delta
            bs = self.black_scholes(S, K, T, r, sigma, option_type, q)
            delta = bs.delta

        return OptionPrice(
            price=price,
            delta=delta,
            option_type=option_type,
            model="binomial",
        )

    def monte_carlo(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
        n_simulations: Optional[int] = None,
        q: float = 0.0,
    ) -> OptionPrice:
        """Monte Carlo pricing.

        Args:
            S: Current underlying price.
            K: Strike price.
            T: Time to expiration in years.
            r: Risk-free rate.
            sigma: Volatility.
            option_type: 'call' or 'put'.
            n_simulations: Number of simulations.
            q: Dividend yield.

        Returns:
            OptionPrice with price.
        """
        n_sims = n_simulations or self.config.monte_carlo_simulations

        if T <= 0 or sigma <= 0:
            intrinsic = max(S - K, 0) if option_type == "call" else max(K - S, 0)
            return OptionPrice(price=intrinsic, option_type=option_type, model="monte_carlo")

        rng = np.random.default_rng(self.config.monte_carlo_seed)
        z = rng.standard_normal(n_sims)

        # Geometric Brownian Motion
        ST = S * np.exp((r - q - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * z)

        if option_type == "call":
            payoffs = np.maximum(ST - K, 0)
        else:
            payoffs = np.maximum(K - ST, 0)

        price = float(np.exp(-r * T) * payoffs.mean())

        # Delta via bump-and-reprice
        dS = S * 0.01
        ST_up = (S + dS) * np.exp((r - q - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * z)
        if option_type == "call":
            payoffs_up = np.maximum(ST_up - K, 0)
        else:
            payoffs_up = np.maximum(K - ST_up, 0)
        price_up = float(np.exp(-r * T) * payoffs_up.mean())
        delta = (price_up - price) / dS

        return OptionPrice(
            price=price,
            delta=float(delta),
            option_type=option_type,
            model="monte_carlo",
        )

    def implied_volatility(
        self,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = "call",
        q: float = 0.0,
    ) -> float:
        """Newton-Raphson implied volatility solver.

        Args:
            market_price: Observed market price.
            S: Current underlying price.
            K: Strike price.
            T: Time to expiration in years.
            r: Risk-free rate.
            option_type: 'call' or 'put'.
            q: Dividend yield.

        Returns:
            Implied volatility.
        """
        if T <= 0 or market_price <= 0:
            return 0.0

        sigma = self.config.iv_initial_guess

        for _ in range(self.config.iv_solver_max_iterations):
            result = self.black_scholes(S, K, T, r, sigma, option_type, q)
            price = result.price
            vega = result.vega * 100  # vega is per 1% move, undo the /100

            diff = price - market_price
            if abs(diff) < self.config.iv_solver_tolerance:
                break

            if abs(vega) < 1e-12:
                break

            sigma -= diff / vega
            sigma = max(self.config.iv_min, min(sigma, self.config.iv_max))

        return float(sigma)

    def price_option(
        self,
        S: float,
        K: float,
        T: float,
        r: Optional[float] = None,
        sigma: float = 0.30,
        option_type: str = "call",
        model: str = "black_scholes",
        american: bool = False,
        q: Optional[float] = None,
    ) -> OptionPrice:
        """Unified pricing interface.

        Args:
            S: Underlying price.
            K: Strike price.
            T: Time to expiration in years.
            r: Risk-free rate (uses config default if None).
            sigma: Volatility.
            option_type: 'call' or 'put'.
            model: 'black_scholes', 'binomial', or 'monte_carlo'.
            american: For binomial, whether to allow early exercise.
            q: Dividend yield.

        Returns:
            OptionPrice result.
        """
        r = r if r is not None else self.config.risk_free_rate
        q = q if q is not None else self.config.dividend_yield

        if model == "binomial":
            return self.binomial_tree(S, K, T, r, sigma, option_type, american, q=q)
        elif model == "monte_carlo":
            return self.monte_carlo(S, K, T, r, sigma, option_type, q=q)
        else:
            return self.black_scholes(S, K, T, r, sigma, option_type, q)
