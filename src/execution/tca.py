"""Transaction Cost Analysis (TCA).

Decomposes execution costs into timing, market impact, spread,
and opportunity cost components using the Implementation Shortfall
framework (Perold, 1988).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class CostComponent:
    """Single cost component of a trade."""
    name: str
    cost_bps: float = 0.0
    cost_dollar: float = 0.0
    pct_of_total: float = 0.0

    @property
    def cost_pct(self) -> float:
        return self.cost_bps / 10_000


@dataclass
class TCAResult:
    """Transaction cost analysis for a single trade."""
    symbol: str = ""
    side: str = "buy"
    quantity: float = 0.0
    decision_price: float = 0.0
    arrival_price: float = 0.0
    execution_price: float = 0.0
    benchmark_vwap: float = 0.0
    notional: float = 0.0

    # Cost breakdown (bps)
    total_cost_bps: float = 0.0
    spread_cost_bps: float = 0.0
    timing_cost_bps: float = 0.0
    impact_cost_bps: float = 0.0
    opportunity_cost_bps: float = 0.0
    commission_bps: float = 0.0

    # Dollar costs
    total_cost_dollar: float = 0.0
    spread_cost_dollar: float = 0.0
    timing_cost_dollar: float = 0.0
    impact_cost_dollar: float = 0.0
    opportunity_cost_dollar: float = 0.0
    commission_dollar: float = 0.0

    # Fill info
    fill_rate: float = 1.0
    filled_quantity: float = 0.0

    @property
    def components(self) -> list[CostComponent]:
        total = abs(self.total_cost_bps) or 1.0
        return [
            CostComponent("Spread", self.spread_cost_bps, self.spread_cost_dollar,
                          abs(self.spread_cost_bps) / total if total else 0),
            CostComponent("Timing", self.timing_cost_bps, self.timing_cost_dollar,
                          abs(self.timing_cost_bps) / total if total else 0),
            CostComponent("Impact", self.impact_cost_bps, self.impact_cost_dollar,
                          abs(self.impact_cost_bps) / total if total else 0),
            CostComponent("Opportunity", self.opportunity_cost_bps,
                          self.opportunity_cost_dollar,
                          abs(self.opportunity_cost_bps) / total if total else 0),
            CostComponent("Commission", self.commission_bps, self.commission_dollar,
                          abs(self.commission_bps) / total if total else 0),
        ]

    @property
    def vs_vwap_bps(self) -> float:
        if self.benchmark_vwap <= 0:
            return 0.0
        sign = 1 if self.side == "buy" else -1
        return sign * (self.execution_price - self.benchmark_vwap) / self.benchmark_vwap * 10_000

    @property
    def implementation_shortfall_pct(self) -> float:
        return self.total_cost_bps / 10_000


@dataclass
class AggregateTCA:
    """Aggregated TCA across multiple trades."""
    n_trades: int = 0
    total_notional: float = 0.0
    avg_cost_bps: float = 0.0
    median_cost_bps: float = 0.0
    std_cost_bps: float = 0.0
    total_cost_dollar: float = 0.0
    avg_spread_bps: float = 0.0
    avg_impact_bps: float = 0.0
    avg_timing_bps: float = 0.0
    avg_fill_rate: float = 0.0
    pct_positive_alpha: float = 0.0  # % of trades with negative IS

    @property
    def cost_per_million(self) -> float:
        if self.total_notional <= 0:
            return 0.0
        return self.total_cost_dollar / (self.total_notional / 1_000_000)


# ---------------------------------------------------------------------------
# TCA Engine
# ---------------------------------------------------------------------------
class TCAEngine:
    """Implementation Shortfall-based transaction cost analysis."""

    def __init__(
        self,
        default_spread_bps: float = 5.0,
        impact_coefficient: float = 0.1,
    ) -> None:
        self.default_spread_bps = default_spread_bps
        self.impact_coefficient = impact_coefficient

    def analyze_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        decision_price: float,
        arrival_price: float,
        execution_price: float,
        filled_quantity: float = 0.0,
        benchmark_vwap: float = 0.0,
        spread: float = 0.0,
        commission: float = 0.0,
        adv: float = 0.0,
    ) -> TCAResult:
        """Analyze a single trade using Implementation Shortfall.

        Args:
            symbol: Ticker symbol.
            side: 'buy' or 'sell'.
            quantity: Intended order quantity.
            decision_price: Price when trade decision was made.
            arrival_price: Price when order hit the market.
            execution_price: Average fill price.
            filled_quantity: Quantity actually filled.
            benchmark_vwap: VWAP benchmark price.
            spread: Bid-ask spread in dollars.
            commission: Total commission in dollars.
            adv: Average daily volume (for impact estimate).

        Returns:
            TCAResult with full cost decomposition.
        """
        if decision_price <= 0:
            return TCAResult(symbol=symbol, side=side, quantity=quantity)

        filled_quantity = filled_quantity or quantity
        sign = 1 if side == "buy" else -1
        notional = filled_quantity * execution_price

        # 1. Spread cost
        if spread > 0:
            spread_bps = (spread / 2) / decision_price * 10_000
        else:
            spread_bps = self.default_spread_bps / 2
        spread_dollar = spread_bps / 10_000 * notional

        # 2. Timing cost: price movement between decision and arrival
        timing_bps = sign * (arrival_price - decision_price) / decision_price * 10_000
        timing_dollar = timing_bps / 10_000 * notional

        # 3. Market impact: price movement between arrival and execution
        impact_bps = sign * (execution_price - arrival_price) / arrival_price * 10_000
        impact_dollar = impact_bps / 10_000 * notional

        # 4. Opportunity cost: cost of unfilled portion
        unfilled = quantity - filled_quantity
        if unfilled > 0 and quantity > 0:
            # Use close/decision price diff as opportunity cost proxy
            opp_price_diff = sign * (execution_price - decision_price)
            opportunity_bps = (unfilled / quantity) * abs(opp_price_diff) / decision_price * 10_000
            opportunity_dollar = unfilled * abs(opp_price_diff)
        else:
            opportunity_bps = 0.0
            opportunity_dollar = 0.0

        # 5. Commission
        commission_bps = commission / notional * 10_000 if notional > 0 else 0.0

        # Total
        total_bps = spread_bps + timing_bps + impact_bps + opportunity_bps + commission_bps
        total_dollar = spread_dollar + timing_dollar + impact_dollar + opportunity_dollar + commission

        fill_rate = filled_quantity / quantity if quantity > 0 else 0.0

        return TCAResult(
            symbol=symbol,
            side=side,
            quantity=quantity,
            decision_price=round(decision_price, 4),
            arrival_price=round(arrival_price, 4),
            execution_price=round(execution_price, 4),
            benchmark_vwap=round(benchmark_vwap, 4) if benchmark_vwap else 0.0,
            notional=round(notional, 2),
            total_cost_bps=round(total_bps, 2),
            spread_cost_bps=round(spread_bps, 2),
            timing_cost_bps=round(timing_bps, 2),
            impact_cost_bps=round(impact_bps, 2),
            opportunity_cost_bps=round(opportunity_bps, 2),
            commission_bps=round(commission_bps, 2),
            total_cost_dollar=round(total_dollar, 2),
            spread_cost_dollar=round(spread_dollar, 2),
            timing_cost_dollar=round(timing_dollar, 2),
            impact_cost_dollar=round(impact_dollar, 2),
            opportunity_cost_dollar=round(opportunity_dollar, 2),
            commission_dollar=round(commission, 2),
            fill_rate=round(fill_rate, 4),
            filled_quantity=filled_quantity,
        )

    def aggregate(self, results: list[TCAResult]) -> AggregateTCA:
        """Aggregate TCA results across multiple trades.

        Args:
            results: List of individual TCA results.

        Returns:
            AggregateTCA summary.
        """
        if not results:
            return AggregateTCA()

        costs = [r.total_cost_bps for r in results]
        spreads = [r.spread_cost_bps for r in results]
        impacts = [r.impact_cost_bps for r in results]
        timings = [r.timing_cost_bps for r in results]
        fills = [r.fill_rate for r in results]
        notionals = [r.notional for r in results]

        positive_alpha = sum(1 for c in costs if c < 0)  # Negative IS = alpha

        return AggregateTCA(
            n_trades=len(results),
            total_notional=round(sum(notionals), 2),
            avg_cost_bps=round(float(np.mean(costs)), 2),
            median_cost_bps=round(float(np.median(costs)), 2),
            std_cost_bps=round(float(np.std(costs)), 2),
            total_cost_dollar=round(sum(r.total_cost_dollar for r in results), 2),
            avg_spread_bps=round(float(np.mean(spreads)), 2),
            avg_impact_bps=round(float(np.mean(impacts)), 2),
            avg_timing_bps=round(float(np.mean(timings)), 2),
            avg_fill_rate=round(float(np.mean(fills)), 4),
            pct_positive_alpha=round(positive_alpha / len(results), 4),
        )

    def estimate_impact(
        self,
        quantity: float,
        price: float,
        adv: float,
        volatility: float = 0.02,
    ) -> float:
        """Estimate expected market impact in bps.

        Uses square-root model: impact = coeff * sigma * sqrt(Q/ADV).

        Args:
            quantity: Order quantity.
            price: Current price.
            adv: Average daily volume.
            volatility: Daily volatility.

        Returns:
            Estimated impact in basis points.
        """
        if adv <= 0 or price <= 0:
            return 0.0
        participation = quantity / adv
        impact = self.impact_coefficient * volatility * np.sqrt(participation) * 10_000
        return round(float(impact), 2)
