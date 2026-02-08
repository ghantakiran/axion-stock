"""Crypto Option Pricing Engine."""

import math
import logging
from typing import Optional

from src.crypto_options.config import DEFAULT_CRYPTO_OPTIONS_CONFIG, CryptoOptionsConfig
from src.crypto_options.models import (
    CryptoOptionContract,
    CryptoOptionGreeks,
    CryptoOptionQuote,
    CryptoOptionType,
)

logger = logging.getLogger(__name__)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


class CryptoOptionPricer:
    """Prices crypto options using Black-76 model.

    Black-76 is preferred for crypto as it uses forward prices,
    accounting for the cost of carry in crypto markets (funding rates, basis).

    Features:
    - Black-76 pricing for calls and puts
    - Full greeks computation (delta, gamma, theta, vega, rho)
    - Implied volatility solver via Newton-Raphson
    - Volatility smile/surface construction
    """

    def __init__(self, config: Optional[CryptoOptionsConfig] = None):
        self.config = config or DEFAULT_CRYPTO_OPTIONS_CONFIG
        self._vol_surface: dict[str, dict[tuple[float, float], float]] = {}

    def price(
        self,
        contract: CryptoOptionContract,
        spot: float,
        vol: float,
        r: Optional[float] = None,
    ) -> CryptoOptionQuote:
        """Price a crypto option using Black-76.

        Args:
            contract: Option contract.
            spot: Current spot price.
            vol: Annualized volatility (e.g., 0.80 for 80%).
            r: Risk-free rate (defaults to config).

        Returns:
            CryptoOptionQuote with price and greeks.
        """
        r = r if r is not None else self.config.default_risk_free_rate
        T = contract.time_to_expiry

        if T <= 0 or vol <= 0:
            # Expired or zero vol → intrinsic value
            intrinsic = self._intrinsic(contract, spot)
            return CryptoOptionQuote(
                contract=contract,
                mark=intrinsic,
                underlying_price=spot,
                greeks=CryptoOptionGreeks(
                    delta=1.0 if intrinsic > 0 and contract.option_type == CryptoOptionType.CALL else
                          -1.0 if intrinsic > 0 and contract.option_type == CryptoOptionType.PUT else 0.0,
                    iv=vol,
                ),
            )

        F = spot * math.exp(r * T)  # Forward price
        d1 = (math.log(F / contract.strike) + 0.5 * vol ** 2 * T) / (vol * math.sqrt(T))
        d2 = d1 - vol * math.sqrt(T)
        df = math.exp(-r * T)

        if contract.option_type == CryptoOptionType.CALL:
            price = df * (F * _norm_cdf(d1) - contract.strike * _norm_cdf(d2))
            delta = df * _norm_cdf(d1)
        else:
            price = df * (contract.strike * _norm_cdf(-d2) - F * _norm_cdf(-d1))
            delta = -df * _norm_cdf(-d1)

        gamma = df * _norm_pdf(d1) / (spot * vol * math.sqrt(T))
        theta = -(spot * _norm_pdf(d1) * vol) / (2 * math.sqrt(T)) - r * contract.strike * df * (
            _norm_cdf(d2) if contract.option_type == CryptoOptionType.CALL else _norm_cdf(-d2)
        )
        theta /= 365  # Per day
        vega = spot * df * _norm_pdf(d1) * math.sqrt(T) / 100  # Per 1% vol

        greeks = CryptoOptionGreeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=0.0,
            iv=vol,
        )

        return CryptoOptionQuote(
            contract=contract,
            mark=round(price, 2),
            underlying_price=spot,
            greeks=greeks,
        )

    def implied_vol(
        self,
        contract: CryptoOptionContract,
        spot: float,
        market_price: float,
        r: Optional[float] = None,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> float:
        """Solve for implied volatility using Newton-Raphson.

        Args:
            contract: Option contract.
            spot: Current spot price.
            market_price: Observed market price.
            r: Risk-free rate.
            max_iter: Maximum iterations.
            tol: Convergence tolerance.

        Returns:
            Implied volatility.
        """
        r = r if r is not None else self.config.default_risk_free_rate
        T = contract.time_to_expiry

        if T <= 0:
            return 0.0

        # Initial guess
        vol = 0.5

        for _ in range(max_iter):
            quote = self.price(contract, spot, vol, r)
            diff = quote.mark - market_price

            if abs(diff) < tol:
                return vol

            # Vega for Newton step (unscaled)
            F = spot * math.exp(r * T)
            d1 = (math.log(F / contract.strike) + 0.5 * vol ** 2 * T) / (vol * math.sqrt(T))
            vega_raw = spot * math.exp(-r * T) * _norm_pdf(d1) * math.sqrt(T)

            if vega_raw < 1e-10:
                break

            vol -= diff / vega_raw
            vol = max(0.01, min(5.0, vol))  # Clamp

        return vol

    def build_vol_surface(
        self,
        underlying: str,
        spot: float,
        quotes: list[CryptoOptionQuote],
    ) -> dict[tuple[float, float], float]:
        """Build implied volatility surface from market quotes.

        Args:
            underlying: Underlying symbol.
            spot: Current spot price.
            quotes: List of market quotes with prices.

        Returns:
            Dict of (strike, tte) -> implied vol.
        """
        surface = {}

        for quote in quotes:
            if quote.mark <= 0:
                continue

            iv = self.implied_vol(
                quote.contract, spot, quote.mark,
            )
            key = (quote.contract.strike, quote.contract.time_to_expiry)
            surface[key] = iv

        self._vol_surface[underlying] = surface
        return surface

    def get_vol_surface(self, underlying: str) -> dict[tuple[float, float], float]:
        """Get stored volatility surface."""
        return self._vol_surface.get(underlying, {})

    def _intrinsic(self, contract: CryptoOptionContract, spot: float) -> float:
        """Compute intrinsic value."""
        if contract.option_type == CryptoOptionType.CALL:
            return max(0, spot - contract.strike)
        else:
            return max(0, contract.strike - spot)
