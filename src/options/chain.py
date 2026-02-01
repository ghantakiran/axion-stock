"""Options Chain Analyzer.

Computes chain-level analytics: put-call ratio (volume and OI),
max pain strike, IV skew, and aggregate chain summaries.
"""

import logging
from typing import Optional

import numpy as np

from src.options.config import ChainConfig
from src.options.pricing import OptionType, OptionsPricingEngine
from src.options.models import OptionContract, OptionGreeks, ChainSummary

logger = logging.getLogger(__name__)


class ChainAnalyzer:
    """Analyzes options chains for aggregate metrics."""

    def __init__(
        self,
        config: Optional[ChainConfig] = None,
        pricing_engine: Optional[OptionsPricingEngine] = None,
    ) -> None:
        self.config = config or ChainConfig()
        self.engine = pricing_engine or OptionsPricingEngine()

    def analyze_chain(
        self,
        contracts: list[OptionContract],
        underlying_price: float,
        symbol: str = "",
    ) -> ChainSummary:
        """Compute full chain summary.

        Args:
            contracts: List of option contracts in the chain.
            underlying_price: Current price of underlying.
            symbol: Asset symbol.

        Returns:
            ChainSummary with aggregate metrics.
        """
        filtered = self._filter_contracts(contracts)

        calls = [c for c in filtered if c.option_type == OptionType.CALL]
        puts = [c for c in filtered if c.option_type == OptionType.PUT]

        call_vol = sum(c.volume for c in calls)
        put_vol = sum(c.volume for c in puts)
        call_oi = sum(c.open_interest for c in calls)
        put_oi = sum(c.open_interest for c in puts)

        pcr_volume = put_vol / call_vol if call_vol > 0 else (999.0 if put_vol > 0 else 1.0)
        pcr_oi = put_oi / call_oi if call_oi > 0 else (999.0 if put_oi > 0 else 1.0)

        max_pain = self.compute_max_pain(filtered, underlying_price)
        iv_skew = self.compute_iv_skew(filtered, underlying_price)
        atm_iv = self._get_atm_iv(filtered, underlying_price)

        return ChainSummary(
            symbol=symbol,
            underlying_price=underlying_price,
            total_call_volume=call_vol,
            total_put_volume=put_vol,
            total_call_oi=call_oi,
            total_put_oi=put_oi,
            pcr_volume=round(min(pcr_volume, 999.0), 3),
            pcr_oi=round(min(pcr_oi, 999.0), 3),
            max_pain_strike=max_pain,
            iv_skew=round(iv_skew, 4),
            atm_iv=round(atm_iv, 4),
            n_contracts=len(filtered),
        )

    def compute_max_pain(
        self,
        contracts: list[OptionContract],
        underlying_price: float,
    ) -> float:
        """Compute max pain strike.

        Max pain is the strike where option writers (sellers) have
        minimum total payout — equivalently where option holders
        experience maximum combined loss.

        Args:
            contracts: Option contracts with OI data.
            underlying_price: Current underlying price.

        Returns:
            Strike price at max pain.
        """
        if not contracts:
            return underlying_price

        strikes = sorted(set(c.strike for c in contracts))
        if not strikes:
            return underlying_price

        min_pain = float("inf")
        max_pain_strike = strikes[0]

        for test_price in strikes:
            total_pain = 0.0
            for c in contracts:
                if c.open_interest <= 0:
                    continue
                if c.option_type == OptionType.CALL:
                    intrinsic = max(test_price - c.strike, 0)
                else:
                    intrinsic = max(c.strike - test_price, 0)
                total_pain += intrinsic * c.open_interest

            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = test_price

        return max_pain_strike

    def compute_iv_skew(
        self,
        contracts: list[OptionContract],
        underlying_price: float,
    ) -> float:
        """Compute IV skew (OTM put IV - OTM call IV).

        Positive skew = puts are more expensive (typical fear/hedge demand).
        Negative skew = calls are more expensive (speculative demand).

        Args:
            contracts: Contracts with greeks/IV data.
            underlying_price: Current underlying price.

        Returns:
            IV skew value.
        """
        otm_range = self.config.skew_otm_range
        lower = underlying_price * (1 - otm_range)
        upper = underlying_price * (1 + otm_range)

        otm_puts = [
            c for c in contracts
            if c.option_type == OptionType.PUT
            and c.strike < underlying_price
            and c.strike >= lower
            and c.greeks is not None
            and c.greeks.implied_vol > 0
        ]
        otm_calls = [
            c for c in contracts
            if c.option_type == OptionType.CALL
            and c.strike > underlying_price
            and c.strike <= upper
            and c.greeks is not None
            and c.greeks.implied_vol > 0
        ]

        if not otm_puts or not otm_calls:
            return 0.0

        # OI-weighted average IV
        put_iv = self._weighted_iv(otm_puts)
        call_iv = self._weighted_iv(otm_calls)

        return put_iv - call_iv

    def put_call_ratio(
        self,
        contracts: list[OptionContract],
        use_oi: bool = False,
    ) -> float:
        """Compute put-call ratio.

        Args:
            contracts: Option contracts.
            use_oi: Use open interest instead of volume.

        Returns:
            Put-call ratio.
        """
        calls = [c for c in contracts if c.option_type == OptionType.CALL]
        puts = [c for c in contracts if c.option_type == OptionType.PUT]

        if use_oi:
            call_total = sum(c.open_interest for c in calls)
            put_total = sum(c.open_interest for c in puts)
        else:
            call_total = sum(c.volume for c in calls)
            put_total = sum(c.volume for c in puts)

        if call_total == 0:
            return 999.0 if put_total > 0 else 1.0
        return put_total / call_total

    def compute_greeks_for_chain(
        self,
        contracts: list[OptionContract],
        underlying_price: float,
        risk_free_rate: float = 0.05,
        volatility: float = 0.30,
    ) -> list[OptionContract]:
        """Compute Greeks for all contracts in the chain.

        Args:
            contracts: Contracts without greeks.
            underlying_price: Current underlying price.
            risk_free_rate: Risk-free rate.
            volatility: Default volatility if not available.

        Returns:
            Contracts with greeks populated.
        """
        for c in contracts:
            T = c.expiry_days / 365.0
            sigma = c.greeks.implied_vol if c.greeks and c.greeks.implied_vol > 0 else volatility
            opt_type = "call" if c.option_type == OptionType.CALL else "put"

            result = self.engine.black_scholes(
                underlying_price, c.strike, T, risk_free_rate, sigma, opt_type,
            )

            iv = sigma
            if c.mid > 0:
                iv = self.engine.implied_volatility(
                    c.mid, underlying_price, c.strike, T, risk_free_rate, opt_type,
                )

            c.greeks = OptionGreeks(
                delta=round(result.delta, 4),
                gamma=round(result.gamma, 6),
                theta=round(result.theta, 4),
                vega=round(result.vega, 4),
                rho=round(result.rho, 4),
                implied_vol=round(iv, 4),
                price=round(result.price, 4),
            )

        return contracts

    def _filter_contracts(self, contracts: list[OptionContract]) -> list[OptionContract]:
        """Filter contracts by minimum volume and OI."""
        return [
            c for c in contracts
            if c.volume >= self.config.min_volume
            or c.open_interest >= self.config.min_open_interest
        ]

    def _get_atm_iv(
        self,
        contracts: list[OptionContract],
        underlying_price: float,
    ) -> float:
        """Get ATM implied volatility."""
        with_iv = [
            c for c in contracts
            if c.greeks is not None and c.greeks.implied_vol > 0
        ]
        if not with_iv:
            return 0.0

        # Find contract closest to ATM
        nearest = min(with_iv, key=lambda c: abs(c.strike - underlying_price))
        return nearest.greeks.implied_vol

    def _weighted_iv(self, contracts: list[OptionContract]) -> float:
        """OI-weighted average IV."""
        total_oi = sum(c.open_interest for c in contracts)
        if total_oi == 0:
            return float(np.mean([c.greeks.implied_vol for c in contracts]))
        return sum(
            c.greeks.implied_vol * c.open_interest / total_oi
            for c in contracts
        )
