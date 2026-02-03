"""Execution Scheduling.

Generates optimal execution schedules using TWAP, VWAP,
and Implementation Shortfall (IS) strategies.
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
class TimeSlice:
    """A single time slice in an execution schedule."""
    slice_index: int = 0
    start_minute: int = 0
    end_minute: int = 0
    quantity: float = 0.0
    pct_of_total: float = 0.0
    cumulative_pct: float = 0.0
    expected_price_impact_bps: float = 0.0

    @property
    def duration_minutes(self) -> int:
        return self.end_minute - self.start_minute


@dataclass
class ExecutionSchedule:
    """Complete execution schedule."""
    symbol: str = ""
    total_quantity: float = 0.0
    strategy: str = "twap"
    n_slices: int = 0
    slices: list[TimeSlice] = field(default_factory=list)
    total_duration_minutes: int = 390  # Full trading day
    estimated_impact_bps: float = 0.0
    urgency: float = 0.5

    @property
    def avg_slice_quantity(self) -> float:
        if self.n_slices <= 0:
            return 0.0
        return self.total_quantity / self.n_slices

    @property
    def participation_rate(self) -> float:
        """Average participation rate if ADV known."""
        return 0.0  # Computed externally


@dataclass
class ScheduleComparison:
    """Compare different scheduling strategies."""
    symbol: str = ""
    quantity: float = 0.0
    twap_impact_bps: float = 0.0
    vwap_impact_bps: float = 0.0
    is_impact_bps: float = 0.0
    recommended: str = "vwap"
    reason: str = ""


# ---------------------------------------------------------------------------
# Execution Scheduler
# ---------------------------------------------------------------------------
class ExecutionScheduler:
    """Generates optimal execution schedules."""

    # Typical intraday volume profile (30-min buckets, 13 buckets for 390 min)
    DEFAULT_VOLUME_PROFILE = [
        0.12, 0.09, 0.07, 0.06, 0.06, 0.06, 0.06,
        0.06, 0.06, 0.07, 0.07, 0.09, 0.13,
    ]

    def __init__(
        self,
        trading_minutes: int = 390,
        impact_coefficient: float = 0.1,
        risk_aversion: float = 1.0,
    ) -> None:
        self.trading_minutes = trading_minutes
        self.impact_coefficient = impact_coefficient
        self.risk_aversion = risk_aversion

    def twap(
        self,
        symbol: str,
        quantity: float,
        n_slices: int = 13,
        duration_minutes: int = 390,
    ) -> ExecutionSchedule:
        """Generate TWAP (Time-Weighted Average Price) schedule.

        Splits order equally across time slices.

        Args:
            symbol: Ticker symbol.
            quantity: Total quantity to execute.
            n_slices: Number of time slices.
            duration_minutes: Total duration in minutes.

        Returns:
            ExecutionSchedule with equal-weighted slices.
        """
        if n_slices <= 0 or quantity <= 0:
            return ExecutionSchedule(symbol=symbol, strategy="twap")

        slice_qty = quantity / n_slices
        slice_duration = duration_minutes / n_slices
        slices = []

        for i in range(n_slices):
            slices.append(TimeSlice(
                slice_index=i,
                start_minute=int(i * slice_duration),
                end_minute=int((i + 1) * slice_duration),
                quantity=round(slice_qty, 2),
                pct_of_total=round(1.0 / n_slices, 4),
                cumulative_pct=round((i + 1) / n_slices, 4),
                expected_price_impact_bps=0.0,
            ))

        # Estimate total impact (uniform participation)
        impact = self._estimate_schedule_impact(
            quantity, n_slices, [1.0 / n_slices] * n_slices
        )

        return ExecutionSchedule(
            symbol=symbol,
            total_quantity=quantity,
            strategy="twap",
            n_slices=n_slices,
            slices=slices,
            total_duration_minutes=duration_minutes,
            estimated_impact_bps=round(impact, 2),
        )

    def vwap(
        self,
        symbol: str,
        quantity: float,
        volume_profile: Optional[list[float]] = None,
        duration_minutes: int = 390,
    ) -> ExecutionSchedule:
        """Generate VWAP (Volume-Weighted Average Price) schedule.

        Distributes order proportionally to expected volume.

        Args:
            symbol: Ticker symbol.
            quantity: Total quantity to execute.
            volume_profile: Intraday volume distribution (sums to 1.0).
            duration_minutes: Total duration in minutes.

        Returns:
            ExecutionSchedule weighted by volume profile.
        """
        if quantity <= 0:
            return ExecutionSchedule(symbol=symbol, strategy="vwap")

        profile = volume_profile or self.DEFAULT_VOLUME_PROFILE
        n_slices = len(profile)

        # Normalize profile
        total_vol = sum(profile)
        if total_vol <= 0:
            profile = [1.0 / n_slices] * n_slices
            total_vol = 1.0
        normalized = [v / total_vol for v in profile]

        slice_duration = duration_minutes / n_slices
        slices = []
        cumulative = 0.0

        for i in range(n_slices):
            pct = normalized[i]
            cumulative += pct
            slice_qty = quantity * pct

            slices.append(TimeSlice(
                slice_index=i,
                start_minute=int(i * slice_duration),
                end_minute=int((i + 1) * slice_duration),
                quantity=round(slice_qty, 2),
                pct_of_total=round(pct, 4),
                cumulative_pct=round(cumulative, 4),
                expected_price_impact_bps=0.0,
            ))

        impact = self._estimate_schedule_impact(quantity, n_slices, normalized)

        return ExecutionSchedule(
            symbol=symbol,
            total_quantity=quantity,
            strategy="vwap",
            n_slices=n_slices,
            slices=slices,
            total_duration_minutes=duration_minutes,
            estimated_impact_bps=round(impact, 2),
        )

    def implementation_shortfall(
        self,
        symbol: str,
        quantity: float,
        urgency: float = 0.5,
        volatility: float = 0.02,
        n_slices: int = 13,
        duration_minutes: int = 390,
    ) -> ExecutionSchedule:
        """Generate Implementation Shortfall (IS) schedule.

        Balances market impact vs timing risk. Higher urgency
        front-loads execution to minimize timing risk.

        Args:
            symbol: Ticker symbol.
            quantity: Total quantity.
            urgency: 0-1 scale (0=patient, 1=aggressive).
            volatility: Daily volatility.
            n_slices: Number of time slices.
            duration_minutes: Total duration.

        Returns:
            ExecutionSchedule optimized for IS.
        """
        if n_slices <= 0 or quantity <= 0:
            return ExecutionSchedule(symbol=symbol, strategy="is")

        urgency = max(0.0, min(1.0, urgency))

        # Generate front-loaded weights using exponential decay
        # Higher urgency = faster decay = more front-loaded
        decay = 0.5 + urgency * 2.0  # decay factor 0.5 to 2.5
        raw_weights = [np.exp(-decay * i / n_slices) for i in range(n_slices)]
        total_w = sum(raw_weights)
        weights = [w / total_w for w in raw_weights]

        slice_duration = duration_minutes / n_slices
        slices = []
        cumulative = 0.0

        for i in range(n_slices):
            pct = weights[i]
            cumulative += pct
            slice_qty = quantity * pct

            # Per-slice impact estimate
            participation = pct
            slice_impact = self.impact_coefficient * volatility * np.sqrt(participation) * 10_000

            slices.append(TimeSlice(
                slice_index=i,
                start_minute=int(i * slice_duration),
                end_minute=int((i + 1) * slice_duration),
                quantity=round(slice_qty, 2),
                pct_of_total=round(pct, 4),
                cumulative_pct=round(min(cumulative, 1.0), 4),
                expected_price_impact_bps=round(float(slice_impact), 2),
            ))

        impact = self._estimate_schedule_impact(quantity, n_slices, weights, volatility)

        return ExecutionSchedule(
            symbol=symbol,
            total_quantity=quantity,
            strategy="is",
            n_slices=n_slices,
            slices=slices,
            total_duration_minutes=duration_minutes,
            estimated_impact_bps=round(impact, 2),
            urgency=urgency,
        )

    def compare_strategies(
        self,
        symbol: str,
        quantity: float,
        volatility: float = 0.02,
        urgency: float = 0.5,
    ) -> ScheduleComparison:
        """Compare TWAP, VWAP, and IS strategies.

        Args:
            symbol: Ticker symbol.
            quantity: Total quantity.
            volatility: Daily volatility.
            urgency: Urgency level for IS.

        Returns:
            ScheduleComparison with recommendations.
        """
        twap = self.twap(symbol, quantity)
        vwap = self.vwap(symbol, quantity)
        is_sched = self.implementation_shortfall(
            symbol, quantity, urgency=urgency, volatility=volatility
        )

        impacts = {
            "twap": twap.estimated_impact_bps,
            "vwap": vwap.estimated_impact_bps,
            "is": is_sched.estimated_impact_bps,
        }

        # Recommend based on conditions
        if urgency > 0.7:
            recommended = "is"
            reason = "High urgency favors IS to minimize timing risk"
        elif volatility > 0.03:
            recommended = "is"
            reason = "High volatility favors IS to reduce timing cost"
        else:
            recommended = "vwap"
            reason = "Normal conditions favor VWAP for best average price"

        return ScheduleComparison(
            symbol=symbol,
            quantity=quantity,
            twap_impact_bps=impacts["twap"],
            vwap_impact_bps=impacts["vwap"],
            is_impact_bps=impacts["is"],
            recommended=recommended,
            reason=reason,
        )

    def _estimate_schedule_impact(
        self,
        quantity: float,
        n_slices: int,
        weights: list[float],
        volatility: float = 0.02,
    ) -> float:
        """Estimate total market impact for a schedule."""
        total_impact = 0.0
        for w in weights:
            participation = w
            slice_impact = self.impact_coefficient * volatility * np.sqrt(participation)
            total_impact += slice_impact * w
        return float(total_impact * 10_000)
