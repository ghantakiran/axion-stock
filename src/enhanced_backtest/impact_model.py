"""Convex Market Impact Model — realistic non-linear slippage.

Replaces the linear impact model with a square-root model that
more accurately reflects real market microstructure:
  impact = sigma * (Q / V)^0.5 * sign * temporary_factor
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImpactConfig:
    """Configuration for the convex impact model.

    Attributes:
        temporary_impact_coeff: Coefficient for temporary impact (eta).
        permanent_impact_coeff: Coefficient for permanent impact (gamma).
        volatility_scale: Whether to scale impact by volatility.
        min_spread_bps: Minimum bid-ask spread in basis points.
        urgency_penalty: Multiplier for high-urgency orders (1-3).
    """

    temporary_impact_coeff: float = 0.1
    permanent_impact_coeff: float = 0.05
    volatility_scale: bool = True
    min_spread_bps: float = 1.0
    urgency_penalty: float = 1.0


@dataclass
class ImpactResult:
    """Result of market impact estimation.

    Attributes:
        total_impact_bps: Total impact in basis points.
        temporary_impact_bps: Temporary component (mean-reverting).
        permanent_impact_bps: Permanent component (information leakage).
        spread_cost_bps: Bid-ask spread cost.
        effective_price: Price after impact.
        slippage_dollars: Dollar cost of impact for the order.
        participation_rate: Order size / daily volume.
    """

    total_impact_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    spread_cost_bps: float = 0.0
    effective_price: float = 0.0
    slippage_dollars: float = 0.0
    participation_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_impact_bps": round(self.total_impact_bps, 2),
            "temporary_impact_bps": round(self.temporary_impact_bps, 2),
            "permanent_impact_bps": round(self.permanent_impact_bps, 2),
            "spread_cost_bps": round(self.spread_cost_bps, 2),
            "effective_price": round(self.effective_price, 4),
            "slippage_dollars": round(self.slippage_dollars, 2),
            "participation_rate": round(self.participation_rate, 4),
        }


class ConvexImpactModel:
    """Square-root market impact model.

    Uses the Almgren-Chriss framework:
      temporary_impact = eta * sigma * sqrt(Q / V)
      permanent_impact = gamma * sigma * (Q / V)
      total = temporary + permanent + spread

    This produces convex (increasing marginal) impact as order size grows,
    which is more realistic than the linear model in BotBacktestRunner.

    Args:
        config: ImpactConfig with coefficients.

    Example:
        model = ConvexImpactModel()
        result = model.estimate(
            order_size=10_000,
            daily_volume=5_000_000,
            price=185.0,
            volatility=0.02,
            side="buy"
        )
        print(f"Impact: {result.total_impact_bps:.1f} bps")
    """

    def __init__(self, config: ImpactConfig | None = None) -> None:
        self.config = config or ImpactConfig()

    def estimate(
        self,
        order_size: float,
        daily_volume: float,
        price: float,
        volatility: float = 0.02,
        side: str = "buy",
    ) -> ImpactResult:
        """Estimate market impact for an order.

        Args:
            order_size: Number of shares to trade.
            daily_volume: Average daily volume in shares.
            price: Current mid-price.
            volatility: Daily volatility (as decimal, e.g. 0.02 for 2%).
            side: "buy" or "sell".

        Returns:
            ImpactResult with impact breakdown.
        """
        if daily_volume <= 0 or price <= 0 or order_size <= 0:
            return ImpactResult(effective_price=price)

        participation_rate = order_size / daily_volume
        sign = 1.0 if side == "buy" else -1.0
        sigma = volatility if self.config.volatility_scale else 0.02

        # Square-root temporary impact
        temp_impact = (
            self.config.temporary_impact_coeff
            * sigma
            * math.sqrt(participation_rate)
            * self.config.urgency_penalty
        )
        temp_bps = temp_impact * 10_000

        # Linear permanent impact
        perm_impact = self.config.permanent_impact_coeff * sigma * participation_rate
        perm_bps = perm_impact * 10_000

        # Spread cost
        spread_bps = self.config.min_spread_bps

        total_bps = temp_bps + perm_bps + spread_bps

        # Effective price (worse for the trader)
        price_impact = price * (total_bps / 10_000) * sign
        effective_price = price + price_impact

        slippage_dollars = abs(price_impact) * order_size

        return ImpactResult(
            total_impact_bps=total_bps,
            temporary_impact_bps=temp_bps,
            permanent_impact_bps=perm_bps,
            spread_cost_bps=spread_bps,
            effective_price=effective_price,
            slippage_dollars=slippage_dollars,
            participation_rate=participation_rate,
        )

    def estimate_for_dollar_amount(
        self,
        dollar_amount: float,
        price: float,
        daily_volume: float,
        volatility: float = 0.02,
        side: str = "buy",
    ) -> ImpactResult:
        """Convenience: estimate impact from a dollar amount."""
        order_size = dollar_amount / max(price, 0.01)
        return self.estimate(order_size, daily_volume, price, volatility, side)
