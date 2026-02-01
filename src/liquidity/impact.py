"""Market Impact Estimation.

Estimates the expected price impact and slippage for a given trade
size using linear and square-root market impact models.
"""

import logging
import math
from typing import Optional

from src.liquidity.config import (
    ImpactConfig,
    ImpactModel,
    DEFAULT_IMPACT_CONFIG,
)
from src.liquidity.models import MarketImpact

logger = logging.getLogger(__name__)


class MarketImpactEstimator:
    """Estimates market impact and optimal execution parameters."""

    def __init__(self, config: Optional[ImpactConfig] = None) -> None:
        self.config = config or DEFAULT_IMPACT_CONFIG

    def estimate_impact(
        self,
        trade_size: int,
        avg_volume: float,
        avg_spread: float = 0.0,
        volatility: float = 0.0,
        price: float = 0.0,
        symbol: str = "",
    ) -> MarketImpact:
        """Estimate market impact for a trade.

        Args:
            trade_size: Number of shares to trade.
            avg_volume: Average daily volume.
            avg_spread: Average bid-ask spread (absolute).
            volatility: Daily volatility (decimal).
            price: Current price (for dollar cost).
            symbol: Asset symbol.

        Returns:
            MarketImpact with cost breakdown.
        """
        if avg_volume <= 0 or trade_size <= 0:
            return MarketImpact(symbol=symbol, trade_size=trade_size)

        vol = volatility if volatility > 0 else self.config.default_volatility
        participation = trade_size / avg_volume

        # Spread cost (half spread per share as fraction of price)
        spread_cost = 0.0
        if avg_spread > 0 and price > 0:
            spread_cost = (avg_spread * self.config.spread_cost_multiplier) / price

        # Impact cost based on model
        k = self.config.impact_coefficient
        if self.config.model == ImpactModel.LINEAR:
            impact_cost = k * participation * vol
        else:  # SQUARE_ROOT
            impact_cost = k * math.sqrt(participation) * vol

        total_cost = spread_cost + impact_cost

        # Total cost in bps
        total_cost_bps = total_cost * 10000

        # Max safe size
        max_safe = self.max_safe_size(avg_volume)

        # Execution horizon
        exec_days = self.execution_horizon(trade_size, avg_volume)

        return MarketImpact(
            symbol=symbol,
            trade_size=trade_size,
            avg_volume=avg_volume,
            participation_rate=round(participation, 4),
            spread_cost=round(spread_cost, 6),
            impact_cost=round(impact_cost, 6),
            total_cost=round(total_cost, 6),
            total_cost_bps=round(total_cost_bps, 2),
            model=self.config.model,
            max_safe_size=max_safe,
            execution_days=exec_days,
        )

    def max_safe_size(
        self,
        avg_volume: float,
        max_participation: Optional[float] = None,
    ) -> int:
        """Compute max safe trade size within participation constraint.

        Args:
            avg_volume: Average daily volume.
            max_participation: Max fraction of daily volume (default: config).

        Returns:
            Max shares that can be safely traded in one day.
        """
        rate = max_participation or self.config.max_participation_rate
        return int(avg_volume * rate)

    def execution_horizon(
        self,
        trade_size: int,
        avg_volume: float,
        participation_rate: Optional[float] = None,
    ) -> int:
        """Compute optimal execution horizon in trading days.

        Args:
            trade_size: Total shares to execute.
            avg_volume: Average daily volume.
            participation_rate: Target participation rate per day.

        Returns:
            Number of trading days needed.
        """
        rate = participation_rate or self.config.max_participation_rate
        if avg_volume <= 0 or rate <= 0:
            return 1

        daily_capacity = avg_volume * rate
        if daily_capacity <= 0:
            return 1

        return max(1, math.ceil(trade_size / daily_capacity))
