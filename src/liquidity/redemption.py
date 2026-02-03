"""Redemption Risk Modeler.

Estimates redemption probabilities, computes liquidity buffers,
models stress scenarios, and builds portfolio liquidation schedules.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RedemptionScenario:
    """Redemption stress scenario result."""
    name: str = "normal"
    redemption_pct: float = 0.0
    redemption_amount: float = 0.0
    liquid_assets: float = 0.0
    coverage_ratio: float = 0.0
    shortfall: float = 0.0
    days_to_meet: int = 0

    @property
    def is_covered(self) -> bool:
        return self.coverage_ratio >= 1.0

    @property
    def has_shortfall(self) -> bool:
        return self.shortfall > 0


@dataclass
class LiquidityBuffer:
    """Required liquidity buffer analysis."""
    total_aum: float = 0.0
    cash_on_hand: float = 0.0
    liquid_assets: float = 0.0
    expected_redemption: float = 0.0
    required_buffer: float = 0.0
    coverage_ratio: float = 0.0
    buffer_deficit: float = 0.0

    @property
    def is_adequate(self) -> bool:
        return self.coverage_ratio >= 1.0

    @property
    def buffer_pct(self) -> float:
        return self.required_buffer / self.total_aum if self.total_aum > 0 else 0.0


@dataclass
class LiquidationItem:
    """Single position in liquidation schedule."""
    symbol: str
    position_value: float = 0.0
    avg_daily_volume_usd: float = 0.0
    max_daily_liquidation: float = 0.0
    days_to_liquidate: float = 0.0
    liquidation_cost_bps: float = 0.0
    priority: int = 0  # lower = liquidate first


@dataclass
class LiquidationSchedule:
    """Portfolio liquidation timeline."""
    items: list[LiquidationItem] = field(default_factory=list)
    total_value: float = 0.0
    total_days: float = 0.0
    total_cost_bps: float = 0.0
    pct_liquid_1d: float = 0.0
    pct_liquid_5d: float = 0.0
    pct_liquid_20d: float = 0.0


class RedemptionRiskModeler:
    """Models portfolio redemption risk and liquidity buffers."""

    def __init__(
        self,
        max_participation: float = 0.10,
        impact_coefficient: float = 0.10,
    ) -> None:
        self.max_participation = max_participation
        self.impact_coefficient = impact_coefficient

    def estimate_redemption_probability(
        self, flow_history: list[float], threshold_pct: float = 0.05
    ) -> float:
        """Estimate probability of redemption exceeding threshold.

        Uses historical outflow frequency.

        Args:
            flow_history: List of net flows (negative = outflow) as pct of AUM.
            threshold_pct: Redemption threshold (e.g., 0.05 = 5% of AUM).

        Returns:
            Probability [0, 1].
        """
        if not flow_history:
            return 0.0

        outflows = [f for f in flow_history if f < -threshold_pct]
        return len(outflows) / len(flow_history)

    def compute_buffer(
        self,
        total_aum: float,
        cash: float,
        liquid_asset_value: float,
        expected_redemption_pct: float = 0.05,
        buffer_multiplier: float = 1.5,
    ) -> LiquidityBuffer:
        """Compute required liquidity buffer.

        Args:
            total_aum: Total assets under management.
            cash: Cash on hand.
            liquid_asset_value: Value of liquid assets (< 1 day to sell).
            expected_redemption_pct: Expected redemption as pct of AUM.
            buffer_multiplier: Safety multiplier on expected redemption.

        Returns:
            LiquidityBuffer.
        """
        expected = total_aum * expected_redemption_pct
        required = expected * buffer_multiplier
        available = cash + liquid_asset_value
        coverage = available / required if required > 0 else float("inf")
        deficit = max(0, required - available)

        return LiquidityBuffer(
            total_aum=total_aum,
            cash_on_hand=cash,
            liquid_assets=liquid_asset_value,
            expected_redemption=expected,
            required_buffer=round(required, 2),
            coverage_ratio=round(coverage, 4),
            buffer_deficit=round(deficit, 2),
        )

    def stress_scenarios(
        self,
        total_aum: float,
        cash: float,
        liquid_asset_value: float,
        positions: Optional[list[dict]] = None,
    ) -> list[RedemptionScenario]:
        """Run multiple stress scenarios.

        Scenarios: normal (5%), stressed (15%), crisis (30%).

        Args:
            total_aum: Total AUM.
            cash: Cash on hand.
            liquid_asset_value: Liquid asset value.
            positions: Optional list of {symbol, value, adv_usd} for DTL calc.

        Returns:
            List of RedemptionScenario for each stress level.
        """
        scenarios = [
            ("normal", 0.05),
            ("stressed", 0.15),
            ("crisis", 0.30),
        ]

        available = cash + liquid_asset_value
        results = []

        for name, pct in scenarios:
            redemption = total_aum * pct
            coverage = available / redemption if redemption > 0 else float("inf")
            shortfall = max(0, redemption - available)

            # Days to meet redemption from positions
            days = 0
            if shortfall > 0 and positions:
                daily_capacity = sum(
                    p.get("adv_usd", 0) * self.max_participation
                    for p in positions
                )
                days = int(np.ceil(shortfall / daily_capacity)) if daily_capacity > 0 else 999

            results.append(RedemptionScenario(
                name=name,
                redemption_pct=pct,
                redemption_amount=round(redemption, 2),
                liquid_assets=available,
                coverage_ratio=round(coverage, 4),
                shortfall=round(shortfall, 2),
                days_to_meet=days,
            ))

        return results

    def liquidation_schedule(
        self, positions: list[dict]
    ) -> LiquidationSchedule:
        """Build portfolio liquidation schedule.

        Each position dict: {symbol, value, adv_usd, spread_bps}.

        Args:
            positions: List of position dicts.

        Returns:
            LiquidationSchedule with per-position timeline.
        """
        items: list[LiquidationItem] = []
        total_value = 0.0

        for pos in positions:
            value = pos.get("value", 0.0)
            adv = pos.get("adv_usd", 0.0)
            spread = pos.get("spread_bps", 5.0)

            max_daily = adv * self.max_participation if adv > 0 else 0.0
            dtl = value / max_daily if max_daily > 0 else 999.0

            # Impact cost: spread + sqrt model
            participation = value / adv if adv > 0 else 1.0
            impact = spread + self.impact_coefficient * np.sqrt(participation) * 10000
            impact = min(impact, 500)  # cap at 5%

            total_value += value
            items.append(LiquidationItem(
                symbol=pos.get("symbol", ""),
                position_value=value,
                avg_daily_volume_usd=adv,
                max_daily_liquidation=round(max_daily, 2),
                days_to_liquidate=round(dtl, 1),
                liquidation_cost_bps=round(impact, 2),
            ))

        # Sort by DTL for priority
        items.sort(key=lambda x: x.days_to_liquidate)
        for i, item in enumerate(items):
            item.priority = i + 1

        # Compute portfolio-level metrics
        total_days = max(item.days_to_liquidate for item in items) if items else 0
        avg_cost = (
            sum(it.liquidation_cost_bps * it.position_value for it in items) / total_value
            if total_value > 0 else 0.0
        )

        # Percentage liquidatable by timeframe
        cumulative = 0.0
        pct_1d = pct_5d = pct_20d = 0.0
        for item in items:
            if item.days_to_liquidate <= 1:
                cumulative += item.position_value
        pct_1d = cumulative / total_value if total_value > 0 else 0.0

        cumulative = sum(
            it.position_value for it in items if it.days_to_liquidate <= 5
        )
        pct_5d = cumulative / total_value if total_value > 0 else 0.0

        cumulative = sum(
            it.position_value for it in items if it.days_to_liquidate <= 20
        )
        pct_20d = cumulative / total_value if total_value > 0 else 0.0

        return LiquidationSchedule(
            items=items,
            total_value=round(total_value, 2),
            total_days=round(total_days, 1),
            total_cost_bps=round(avg_cost, 2),
            pct_liquid_1d=round(pct_1d, 4),
            pct_liquid_5d=round(pct_5d, 4),
            pct_liquid_20d=round(pct_20d, 4),
        )
