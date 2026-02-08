"""Crypto Derivatives Analytics."""

import logging
from typing import Optional
from datetime import datetime

from src.crypto_options.config import CryptoExchange
from src.crypto_options.models import (
    CryptoPerpetual,
    CryptoFundingRate,
    CryptoBasisSpread,
    CryptoOptionQuote,
)

logger = logging.getLogger(__name__)


class CryptoDerivativesAnalyzer:
    """Analyzes crypto derivatives markets.

    Features:
    - Funding rate tracking and analysis
    - Spot-futures basis analysis
    - Put/call ratio computation
    - Open interest analysis
    - Max pain calculation
    """

    def __init__(self):
        self._funding_history: dict[str, list[CryptoFundingRate]] = {}
        self._perpetuals: dict[str, CryptoPerpetual] = {}

    def record_funding_rate(
        self,
        underlying: str,
        exchange: CryptoExchange,
        rate: float,
    ) -> CryptoFundingRate:
        """Record a funding rate snapshot.

        Args:
            underlying: Underlying symbol.
            exchange: Exchange.
            rate: Funding rate (e.g., 0.0001 = 0.01%).

        Returns:
            CryptoFundingRate record.
        """
        fr = CryptoFundingRate(
            underlying=underlying,
            exchange=exchange,
            rate=rate,
        )

        key = f"{underlying}:{exchange.value}"
        if key not in self._funding_history:
            self._funding_history[key] = []
        self._funding_history[key].append(fr)

        return fr

    def get_funding_history(
        self,
        underlying: str,
        exchange: CryptoExchange,
        limit: int = 100,
    ) -> list[CryptoFundingRate]:
        """Get funding rate history.

        Args:
            underlying: Underlying symbol.
            exchange: Exchange.
            limit: Max records to return.

        Returns:
            List of CryptoFundingRate, newest first.
        """
        key = f"{underlying}:{exchange.value}"
        history = self._funding_history.get(key, [])
        return list(reversed(history[-limit:]))

    def average_funding_rate(
        self,
        underlying: str,
        exchange: CryptoExchange,
        periods: int = 30,
    ) -> float:
        """Compute average funding rate over N periods.

        Args:
            underlying: Underlying symbol.
            exchange: Exchange.
            periods: Number of periods to average.

        Returns:
            Average funding rate.
        """
        history = self.get_funding_history(underlying, exchange, limit=periods)
        if not history:
            return 0.0
        return sum(fr.rate for fr in history) / len(history)

    def compute_basis(
        self,
        underlying: str,
        spot_price: float,
        futures_price: float,
        perp_price: float,
        days_to_expiry: int = 0,
    ) -> CryptoBasisSpread:
        """Compute spot-futures basis spread.

        Args:
            underlying: Underlying symbol.
            spot_price: Current spot price.
            futures_price: Futures price.
            perp_price: Perpetual price.
            days_to_expiry: Days to futures expiry.

        Returns:
            CryptoBasisSpread analysis.
        """
        return CryptoBasisSpread(
            underlying=underlying,
            spot_price=spot_price,
            futures_price=futures_price,
            perp_price=perp_price,
            days_to_expiry=days_to_expiry,
        )

    def put_call_ratio(self, quotes: list[CryptoOptionQuote]) -> float:
        """Compute put/call ratio from option quotes.

        Args:
            quotes: List of option quotes.

        Returns:
            Put/call ratio by open interest.
        """
        from src.crypto_options.config import CryptoOptionType

        put_oi = sum(
            q.open_interest for q in quotes
            if q.contract.option_type == CryptoOptionType.PUT
        )
        call_oi = sum(
            q.open_interest for q in quotes
            if q.contract.option_type == CryptoOptionType.CALL
        )

        if call_oi == 0:
            return 0.0
        return put_oi / call_oi

    def max_pain(
        self,
        quotes: list[CryptoOptionQuote],
        spot: float,
    ) -> float:
        """Calculate max pain strike price.

        Max pain is the strike where option sellers have minimum payout.

        Args:
            quotes: Option quotes with open interest.
            spot: Current spot price.

        Returns:
            Max pain strike price.
        """
        from src.crypto_options.config import CryptoOptionType

        strikes = set(q.contract.strike for q in quotes if q.contract.strike > 0)
        if not strikes:
            return spot

        min_pain = float("inf")
        max_pain_strike = spot

        for test_strike in strikes:
            total_pain = 0.0
            for q in quotes:
                if q.contract.option_type == CryptoOptionType.CALL:
                    pain = max(0, test_strike - q.contract.strike) * q.open_interest
                else:
                    pain = max(0, q.contract.strike - test_strike) * q.open_interest
                total_pain += pain

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_strike

        return max_pain_strike

    def update_perpetual(self, perp: CryptoPerpetual) -> None:
        """Update perpetual contract data."""
        self._perpetuals[perp.underlying] = perp

    def get_perpetual(self, underlying: str) -> Optional[CryptoPerpetual]:
        """Get perpetual contract data."""
        return self._perpetuals.get(underlying)
