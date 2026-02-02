"""Price Impact Estimation.

Temporary/permanent impact decomposition, square-root impact
model, and Almgren-Chriss optimal execution framework.
"""

import logging
import math
from typing import Optional

import numpy as np

from src.microstructure.config import ImpactConfig, ImpactModel, DEFAULT_IMPACT_CONFIG
from src.microstructure.models import ImpactEstimate

logger = logging.getLogger(__name__)


class ImpactEstimator:
    """Estimates market impact of order execution."""

    def __init__(self, config: Optional[ImpactConfig] = None) -> None:
        self.config = config or DEFAULT_IMPACT_CONFIG

    def estimate(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
        price: float,
        symbol: str = "",
    ) -> ImpactEstimate:
        """Estimate price impact of an order.

        Args:
            order_size: Number of shares to execute.
            daily_volume: Average daily volume (shares).
            volatility: Daily volatility (decimal, e.g. 0.02 = 2%).
            price: Current price per share.
            symbol: Ticker symbol.

        Returns:
            ImpactEstimate with temporary and permanent components.
        """
        if daily_volume <= 0 or volatility <= 0 or price <= 0:
            return self._empty_estimate(symbol, order_size)

        participation = order_size / daily_volume
        model = self.config.model

        if model == ImpactModel.SQUARE_ROOT:
            temp_bps, perm_bps = self._square_root_model(
                participation, volatility
            )
        elif model == ImpactModel.ALMGREN_CHRISS:
            temp_bps, perm_bps = self._almgren_chriss_model(
                order_size, daily_volume, volatility
            )
        else:
            temp_bps, perm_bps = self._linear_model(participation, volatility)

        total_bps = temp_bps + perm_bps
        cost_dollars = price * order_size * total_bps / 10000

        return ImpactEstimate(
            symbol=symbol,
            order_size=order_size,
            temporary_impact_bps=round(temp_bps, 2),
            permanent_impact_bps=round(perm_bps, 2),
            total_impact_bps=round(total_bps, 2),
            cost_dollars=round(cost_dollars, 2),
            participation_rate=round(participation, 6),
            daily_volume=daily_volume,
            volatility=volatility,
            model_used=model.value,
        )

    def _square_root_model(
        self, participation: float, volatility: float
    ) -> tuple[float, float]:
        """Square-root impact model.

        Total impact = sigma * sqrt(Q/V)
        Split into temporary (decays) and permanent components.
        """
        vol_bps = volatility * 10000
        sqrt_part = math.sqrt(abs(participation))

        # Empirical coefficients (calibrated to market data)
        temp_coeff = 0.5
        perm_coeff = 0.3

        temporary = temp_coeff * vol_bps * sqrt_part * self.config.temporary_decay
        permanent = perm_coeff * vol_bps * sqrt_part

        return temporary, permanent

    def _almgren_chriss_model(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> tuple[float, float]:
        """Almgren-Chriss optimal execution model.

        Uses risk-aversion framework with temporary and permanent
        impact functions.
        """
        vol_bps = volatility * 10000
        participation = order_size / daily_volume

        # Permanent impact: linear in participation
        gamma = 0.314  # empirical permanent impact coefficient
        permanent = gamma * vol_bps * participation

        # Temporary impact: depends on execution rate
        eta = 0.142  # empirical temporary impact coefficient
        # Assume execution over 1 day at constant rate
        exec_rate = participation  # fraction of ADV per day
        temporary = eta * vol_bps * exec_rate * self.config.temporary_decay

        return temporary, permanent

    def _linear_model(
        self, participation: float, volatility: float
    ) -> tuple[float, float]:
        """Simple linear impact model.

        Impact = coefficient * volatility * participation_rate
        """
        vol_bps = volatility * 10000

        temp_coeff = 0.4
        perm_coeff = 0.2

        temporary = temp_coeff * vol_bps * participation * self.config.temporary_decay
        permanent = perm_coeff * vol_bps * participation

        return temporary, permanent

    def optimal_schedule(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
        n_periods: int = 10,
        risk_aversion: float = 1e-6,
    ) -> list[float]:
        """Compute optimal execution schedule (Almgren-Chriss).

        Args:
            order_size: Total shares to execute.
            daily_volume: Average daily volume.
            volatility: Daily volatility.
            n_periods: Number of execution intervals.
            risk_aversion: Risk aversion parameter.

        Returns:
            List of shares to execute per period.
        """
        if n_periods <= 0 or daily_volume <= 0:
            return [order_size]

        # Kappa: urgency parameter
        sigma = volatility * math.sqrt(daily_volume)
        eta = 0.142  # temporary impact coefficient
        gamma = 0.314  # permanent impact coefficient

        if eta == 0 or sigma == 0:
            # Uniform schedule
            return [order_size / n_periods] * n_periods

        kappa_sq = risk_aversion * sigma * sigma / eta
        kappa = math.sqrt(abs(kappa_sq))

        # Trajectory: remaining shares at each step
        schedule = []
        remaining = order_size
        for j in range(n_periods):
            if kappa * (n_periods - j) > 20:
                # Avoid overflow: approximately uniform for large kappa
                trade_j = remaining / (n_periods - j)
            else:
                denom = math.sinh(kappa * (n_periods - j))
                if denom == 0:
                    trade_j = remaining / (n_periods - j)
                else:
                    trade_j = remaining * math.sinh(kappa) / denom

            trade_j = min(trade_j, remaining)
            schedule.append(round(trade_j, 2))
            remaining -= trade_j

        # Assign any residual to last period
        if remaining > 0.01:
            schedule[-1] += round(remaining, 2)

        return schedule

    def _empty_estimate(
        self, symbol: str, order_size: float
    ) -> ImpactEstimate:
        return ImpactEstimate(
            symbol=symbol,
            order_size=order_size,
            temporary_impact_bps=0.0,
            permanent_impact_bps=0.0,
            total_impact_bps=0.0,
            cost_dollars=0.0,
            participation_rate=0.0,
            daily_volume=0.0,
            volatility=0.0,
        )
