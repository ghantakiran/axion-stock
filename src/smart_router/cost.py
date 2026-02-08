"""Cost optimization for order routing."""

import math
from typing import Dict, List, Optional

from .models import CostEstimate, Venue


class CostOptimizer:
    """Estimates and optimizes execution costs across venues."""

    def __init__(self, spread_bps: float = 2.0, impact_coefficient: float = 0.1):
        self.spread_bps = spread_bps
        self.impact_coefficient = impact_coefficient

    def estimate_cost(
        self,
        venue: Venue,
        quantity: int,
        price: float,
        adv: float = 1_000_000,
        is_maker: bool = False,
    ) -> CostEstimate:
        """Estimate total execution cost for a venue."""
        notional = quantity * price

        # Exchange fee/rebate
        fee_per_share = venue.maker_fee if is_maker else venue.taker_fee
        exchange_fee = fee_per_share * quantity
        rebate = -exchange_fee if exchange_fee < 0 else 0.0
        exchange_fee = max(0.0, exchange_fee)

        # Spread cost (half spread for each side)
        spread_cost = notional * (self.spread_bps / 10000) / 2

        # Market impact (square-root model)
        participation = quantity / max(adv, 1)
        impact_cost = notional * self.impact_coefficient * math.sqrt(participation)

        # Opportunity cost (based on venue fill rate)
        miss_rate = 1.0 - venue.fill_rate
        opportunity_cost = notional * miss_rate * (self.spread_bps / 10000)

        # Price improvement offset for dark pools
        pi_offset = venue.avg_price_improvement * notional

        total = exchange_fee + spread_cost + impact_cost + opportunity_cost - pi_offset
        net = total - rebate

        return CostEstimate(
            venue_id=venue.venue_id,
            exchange_fee=exchange_fee,
            spread_cost=spread_cost,
            impact_cost=impact_cost,
            opportunity_cost=opportunity_cost,
            total_cost=total,
            rebate=rebate,
            net_cost=net,
        )

    def find_cheapest(
        self,
        venues: List[Venue],
        quantity: int,
        price: float,
        adv: float = 1_000_000,
        is_maker: bool = False,
    ) -> Optional[CostEstimate]:
        """Find the venue with lowest net cost."""
        if not venues:
            return None

        estimates = [
            self.estimate_cost(venue, quantity, price, adv, is_maker)
            for venue in venues
        ]
        return min(estimates, key=lambda e: e.net_cost)

    def compare_venues(
        self,
        venues: List[Venue],
        quantity: int,
        price: float,
        adv: float = 1_000_000,
    ) -> List[CostEstimate]:
        """Compare costs across all venues, sorted by net cost."""
        estimates = []
        for venue in venues:
            # Estimate both maker and taker, use taker as default
            est = self.estimate_cost(venue, quantity, price, adv, is_maker=False)
            estimates.append(est)
        return sorted(estimates, key=lambda e: e.net_cost)

    def optimal_split_cost(
        self,
        venues: List[Venue],
        total_quantity: int,
        price: float,
        adv: float = 1_000_000,
    ) -> float:
        """Estimate the cost of optimally splitting across venues."""
        if not venues or total_quantity <= 0:
            return 0.0

        # Simple proportional split by fill rate
        total_rate = sum(v.fill_rate for v in venues)
        if total_rate <= 0:
            return 0.0

        total_cost = 0.0
        for venue in venues:
            qty = int(total_quantity * venue.fill_rate / total_rate)
            if qty > 0:
                est = self.estimate_cost(venue, qty, price, adv)
                total_cost += est.net_cost

        return total_cost

    def maker_taker_savings(
        self,
        venue: Venue,
        quantity: int,
        price: float,
        adv: float = 1_000_000,
    ) -> float:
        """Calculate savings from using maker vs taker orders."""
        taker = self.estimate_cost(venue, quantity, price, adv, is_maker=False)
        maker = self.estimate_cost(venue, quantity, price, adv, is_maker=True)
        return taker.net_cost - maker.net_cost
