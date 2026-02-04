"""Liquidity Cost Curves.

Builds cost-versus-size curves showing how transaction costs scale
with trade size, and identifies optimal execution sizes.
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
class CostPoint:
    """Single point on the cost curve."""
    trade_size_shares: int = 0
    trade_size_usd: float = 0.0
    participation_rate: float = 0.0
    spread_cost_bps: float = 0.0
    impact_cost_bps: float = 0.0
    total_cost_bps: float = 0.0
    execution_days: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.trade_size_usd * self.total_cost_bps / 10_000

    @property
    def is_feasible(self) -> bool:
        return self.participation_rate <= 0.10


@dataclass
class CostCurve:
    """Full cost curve for a symbol."""
    symbol: str = ""
    points: list[CostPoint] = field(default_factory=list)
    optimal_size_shares: int = 0  # Best cost-efficiency point
    optimal_cost_bps: float = 0.0
    max_feasible_shares: int = 0
    avg_daily_volume: float = 0.0
    price: float = 0.0

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def cost_at_1pct_adv(self) -> float:
        """Cost at 1% of ADV."""
        target = self.avg_daily_volume * 0.01
        for pt in self.points:
            if pt.trade_size_shares >= target:
                return pt.total_cost_bps
        return 0.0


@dataclass
class CostComparison:
    """Comparison of cost curves across symbols."""
    curves: list[CostCurve] = field(default_factory=list)
    cheapest_at_10k: str = ""
    cheapest_at_100k: str = ""
    cheapest_at_1m: str = ""

    @property
    def n_symbols(self) -> int:
        return len(self.curves)


@dataclass
class OptimalExecution:
    """Optimal execution parameters for a target trade."""
    symbol: str = ""
    target_shares: int = 0
    target_usd: float = 0.0
    recommended_slices: int = 1
    slice_size: int = 0
    expected_cost_bps: float = 0.0
    expected_cost_usd: float = 0.0
    execution_days: float = 0.0
    strategy: str = ""  # single, split, multi_day

    @property
    def is_multi_day(self) -> bool:
        return self.execution_days > 1.0


# ---------------------------------------------------------------------------
# Cost Curve Builder
# ---------------------------------------------------------------------------
class CostCurveBuilder:
    """Builds transaction cost curves and optimal execution analysis."""

    def __init__(
        self,
        impact_coefficient: float = 0.10,
        max_participation: float = 0.10,
        spread_bps: float = 2.0,
    ) -> None:
        self.impact_coefficient = impact_coefficient
        self.max_participation = max_participation
        self.default_spread_bps = spread_bps

    def build_curve(
        self,
        avg_daily_volume: float,
        price: float,
        volatility: float = 0.02,
        spread_bps: Optional[float] = None,
        symbol: str = "",
        n_points: int = 10,
    ) -> CostCurve:
        """Build cost curve for a symbol.

        Args:
            avg_daily_volume: Average daily volume in shares.
            price: Current price.
            volatility: Daily return volatility.
            spread_bps: Bid-ask spread in bps (uses default if None).
            symbol: Ticker symbol.
            n_points: Number of points on the curve.

        Returns:
            CostCurve with cost at various sizes.
        """
        if avg_daily_volume <= 0 or price <= 0:
            return CostCurve(symbol=symbol)

        spread = spread_bps if spread_bps is not None else self.default_spread_bps

        # Generate size points logarithmically
        max_size = avg_daily_volume * self.max_participation
        if max_size <= 0:
            return CostCurve(symbol=symbol)

        sizes = np.logspace(
            np.log10(max(1, max_size / 1000)),
            np.log10(max_size * 2),
            n_points,
        ).astype(int)
        sizes = sorted(set(sizes))

        points = []
        for size in sizes:
            participation = size / avg_daily_volume
            # Square-root impact model
            impact_bps = (
                self.impact_coefficient
                * volatility
                * np.sqrt(participation)
                * 10_000
            )
            total = spread * 0.5 + float(impact_bps)  # Half-spread + impact
            exec_days = participation / self.max_participation

            points.append(CostPoint(
                trade_size_shares=int(size),
                trade_size_usd=round(size * price, 2),
                participation_rate=round(participation, 6),
                spread_cost_bps=round(spread * 0.5, 2),
                impact_cost_bps=round(float(impact_bps), 2),
                total_cost_bps=round(total, 2),
                execution_days=round(max(0.1, exec_days), 2),
            ))

        # Optimal: best cost-efficiency for feasible trades
        feasible = [p for p in points if p.is_feasible]
        if feasible:
            # Cost efficiency = size / total_cost
            optimal = max(
                feasible,
                key=lambda p: p.trade_size_shares / max(0.01, p.total_cost_bps),
            )
            optimal_size = optimal.trade_size_shares
            optimal_cost = optimal.total_cost_bps
            max_feasible = max(p.trade_size_shares for p in feasible)
        else:
            optimal_size = 0
            optimal_cost = 0.0
            max_feasible = 0

        return CostCurve(
            symbol=symbol,
            points=points,
            optimal_size_shares=optimal_size,
            optimal_cost_bps=round(optimal_cost, 2),
            max_feasible_shares=max_feasible,
            avg_daily_volume=round(avg_daily_volume, 0),
            price=round(price, 2),
        )

    def compare_curves(
        self,
        curves: list[CostCurve],
    ) -> CostComparison:
        """Compare cost curves across symbols.

        Args:
            curves: List of CostCurve objects.

        Returns:
            CostComparison with cheapest at various sizes.
        """
        if not curves:
            return CostComparison()

        def cheapest_at_size(target_shares: int) -> str:
            best_sym = ""
            best_cost = float("inf")
            for c in curves:
                for pt in c.points:
                    if pt.trade_size_shares >= target_shares:
                        if pt.total_cost_bps < best_cost:
                            best_cost = pt.total_cost_bps
                            best_sym = c.symbol
                        break
            return best_sym

        return CostComparison(
            curves=curves,
            cheapest_at_10k=cheapest_at_size(10_000),
            cheapest_at_100k=cheapest_at_size(100_000),
            cheapest_at_1m=cheapest_at_size(1_000_000),
        )

    def optimal_execution(
        self,
        target_shares: int,
        avg_daily_volume: float,
        price: float,
        volatility: float = 0.02,
        spread_bps: Optional[float] = None,
        symbol: str = "",
    ) -> OptimalExecution:
        """Determine optimal execution strategy for a target trade.

        Args:
            target_shares: Number of shares to trade.
            avg_daily_volume: Average daily volume.
            price: Current price.
            volatility: Daily return volatility.
            spread_bps: Bid-ask spread in bps.
            symbol: Ticker symbol.

        Returns:
            OptimalExecution with strategy recommendation.
        """
        if avg_daily_volume <= 0 or price <= 0 or target_shares <= 0:
            return OptimalExecution(symbol=symbol)

        spread = spread_bps if spread_bps is not None else self.default_spread_bps
        participation = target_shares / avg_daily_volume
        target_usd = target_shares * price

        # Determine strategy
        if participation <= self.max_participation:
            # Single execution
            impact = (
                self.impact_coefficient * volatility
                * np.sqrt(participation) * 10_000
            )
            total_cost = spread * 0.5 + float(impact)
            strategy = "single"
            slices = 1
            slice_size = target_shares
            exec_days = max(0.1, participation / self.max_participation)
        else:
            # Split across multiple days
            daily_max = int(avg_daily_volume * self.max_participation)
            slices = max(1, int(np.ceil(target_shares / daily_max)))
            slice_size = int(np.ceil(target_shares / slices))
            slice_participation = slice_size / avg_daily_volume

            # Impact per slice (but repeated slices add persistence cost)
            per_slice_impact = (
                self.impact_coefficient * volatility
                * np.sqrt(slice_participation) * 10_000
            )
            # Multi-day cost includes timing risk
            timing_cost = slices * 0.5  # ~0.5 bps per extra day
            total_cost = spread * 0.5 + float(per_slice_impact) + timing_cost
            strategy = "multi_day" if slices > 1 else "split"
            exec_days = float(slices)

        cost_usd = target_usd * total_cost / 10_000

        return OptimalExecution(
            symbol=symbol,
            target_shares=target_shares,
            target_usd=round(target_usd, 2),
            recommended_slices=slices,
            slice_size=slice_size,
            expected_cost_bps=round(total_cost, 2),
            expected_cost_usd=round(cost_usd, 2),
            execution_days=round(exec_days, 2),
            strategy=strategy,
        )
