"""Multi-Period Brinson Attribution.

Extends single-period Brinson-Fachler to multiple periods using
Carino linking to ensure effects compound correctly over time.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.attribution.config import AttributionConfig, DEFAULT_ATTRIBUTION_CONFIG
from src.attribution.models import SectorAttribution, BrinsonAttribution

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class PeriodAttribution:
    """Single-period attribution within a multi-period analysis."""
    period_index: int = 0
    period_label: str = ""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0

    @property
    def total_effect(self) -> float:
        return self.allocation_effect + self.selection_effect + self.interaction_effect


@dataclass
class LinkedAttribution:
    """Multi-period linked attribution result."""
    total_portfolio_return: float = 0.0
    total_benchmark_return: float = 0.0
    total_active_return: float = 0.0
    linked_allocation: float = 0.0
    linked_selection: float = 0.0
    linked_interaction: float = 0.0
    periods: list[PeriodAttribution] = field(default_factory=list)
    linking_method: str = "carino"
    n_periods: int = 0

    @property
    def linked_total(self) -> float:
        return self.linked_allocation + self.linked_selection + self.linked_interaction

    @property
    def residual(self) -> float:
        """Linking residual (should be near zero)."""
        return self.total_active_return - self.linked_total


@dataclass
class CumulativeEffect:
    """Cumulative attribution effect over time."""
    period_labels: list[str] = field(default_factory=list)
    cumulative_allocation: list[float] = field(default_factory=list)
    cumulative_selection: list[float] = field(default_factory=list)
    cumulative_interaction: list[float] = field(default_factory=list)
    cumulative_active: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-Period Analyzer
# ---------------------------------------------------------------------------
class MultiPeriodAttribution:
    """Multi-period Brinson attribution with linking."""

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def link_carino(
        self,
        period_portfolio_returns: list[float],
        period_benchmark_returns: list[float],
        period_allocations: list[float],
        period_selections: list[float],
        period_interactions: list[float],
        period_labels: Optional[list[str]] = None,
    ) -> LinkedAttribution:
        """Link multi-period attribution using Carino method.

        The Carino linking factor smoothly distributes the compounding
        adjustment across periods, preserving additivity of effects.

        Args:
            period_portfolio_returns: Portfolio return per period.
            period_benchmark_returns: Benchmark return per period.
            period_allocations: Allocation effect per period.
            period_selections: Selection effect per period.
            period_interactions: Interaction effect per period.
            period_labels: Optional labels for each period.

        Returns:
            LinkedAttribution with properly linked effects.
        """
        n = len(period_portfolio_returns)
        if n == 0:
            return LinkedAttribution(linking_method="carino")

        labels = period_labels or [f"Period {i+1}" for i in range(n)]

        # Compound total returns
        total_p = self._compound_return(period_portfolio_returns)
        total_b = self._compound_return(period_benchmark_returns)
        total_active = total_p - total_b

        # Carino linking factors
        # k_t = ln(1 + R_p_t) / R_p_t for each period
        # K = ln(1 + R_p) / R_p for total
        log_factors = []
        for r in period_portfolio_returns:
            if abs(r) < 1e-10:
                log_factors.append(1.0)
            else:
                log_factors.append(np.log(1 + r) / r)

        if abs(total_p) < 1e-10:
            total_log_factor = 1.0
        else:
            total_log_factor = np.log(1 + total_p) / total_p

        # Linking coefficient: c_t = k_t / K
        coefficients = []
        for k_t in log_factors:
            if abs(total_log_factor) < 1e-10:
                coefficients.append(1.0 / n)
            else:
                coefficients.append(k_t / total_log_factor)

        # Linked effects: linked_effect = sum(c_t * effect_t)
        linked_alloc = sum(c * a for c, a in zip(coefficients, period_allocations))
        linked_sel = sum(c * s for c, s in zip(coefficients, period_selections))
        linked_inter = sum(c * i for c, i in zip(coefficients, period_interactions))

        # Build period details
        periods = []
        for i in range(n):
            periods.append(PeriodAttribution(
                period_index=i,
                period_label=labels[i],
                portfolio_return=round(period_portfolio_returns[i], 6),
                benchmark_return=round(period_benchmark_returns[i], 6),
                active_return=round(
                    period_portfolio_returns[i] - period_benchmark_returns[i], 6
                ),
                allocation_effect=round(period_allocations[i], 6),
                selection_effect=round(period_selections[i], 6),
                interaction_effect=round(period_interactions[i], 6),
            ))

        return LinkedAttribution(
            total_portfolio_return=round(total_p, 6),
            total_benchmark_return=round(total_b, 6),
            total_active_return=round(total_active, 6),
            linked_allocation=round(linked_alloc, 6),
            linked_selection=round(linked_sel, 6),
            linked_interaction=round(linked_inter, 6),
            periods=periods,
            linking_method="carino",
            n_periods=n,
        )

    def link_geometric(
        self,
        period_portfolio_returns: list[float],
        period_benchmark_returns: list[float],
        period_allocations: list[float],
        period_selections: list[float],
        period_interactions: list[float],
        period_labels: Optional[list[str]] = None,
    ) -> LinkedAttribution:
        """Link multi-period attribution using geometric method.

        Scales each period's effects by cumulative benchmark growth.

        Args:
            period_portfolio_returns: Portfolio return per period.
            period_benchmark_returns: Benchmark return per period.
            period_allocations: Allocation effect per period.
            period_selections: Selection effect per period.
            period_interactions: Interaction effect per period.
            period_labels: Optional labels for each period.

        Returns:
            LinkedAttribution with geometrically linked effects.
        """
        n = len(period_portfolio_returns)
        if n == 0:
            return LinkedAttribution(linking_method="geometric")

        labels = period_labels or [f"Period {i+1}" for i in range(n)]

        total_p = self._compound_return(period_portfolio_returns)
        total_b = self._compound_return(period_benchmark_returns)
        total_active = total_p - total_b

        # Cumulative benchmark compounding factor up to (but not including) period t
        cum_bm = 1.0
        linked_alloc = 0.0
        linked_sel = 0.0
        linked_inter = 0.0

        periods = []
        for i in range(n):
            # Scale by prior cumulative benchmark
            linked_alloc += cum_bm * period_allocations[i]
            linked_sel += cum_bm * period_selections[i]
            linked_inter += cum_bm * period_interactions[i]

            periods.append(PeriodAttribution(
                period_index=i,
                period_label=labels[i],
                portfolio_return=round(period_portfolio_returns[i], 6),
                benchmark_return=round(period_benchmark_returns[i], 6),
                active_return=round(
                    period_portfolio_returns[i] - period_benchmark_returns[i], 6
                ),
                allocation_effect=round(period_allocations[i], 6),
                selection_effect=round(period_selections[i], 6),
                interaction_effect=round(period_interactions[i], 6),
            ))

            cum_bm *= (1 + period_benchmark_returns[i])

        return LinkedAttribution(
            total_portfolio_return=round(total_p, 6),
            total_benchmark_return=round(total_b, 6),
            total_active_return=round(total_active, 6),
            linked_allocation=round(linked_alloc, 6),
            linked_selection=round(linked_sel, 6),
            linked_interaction=round(linked_inter, 6),
            periods=periods,
            linking_method="geometric",
            n_periods=n,
        )

    def cumulative_effects(
        self,
        linked: LinkedAttribution,
    ) -> CumulativeEffect:
        """Compute cumulative attribution effects over time.

        Args:
            linked: Linked attribution result.

        Returns:
            CumulativeEffect with running sums.
        """
        labels = []
        cum_a, cum_s, cum_i, cum_active = [], [], [], []
        running_a = running_s = running_i = running_active = 0.0

        for p in linked.periods:
            labels.append(p.period_label)
            running_a += p.allocation_effect
            running_s += p.selection_effect
            running_i += p.interaction_effect
            running_active += p.active_return
            cum_a.append(round(running_a, 6))
            cum_s.append(round(running_s, 6))
            cum_i.append(round(running_i, 6))
            cum_active.append(round(running_active, 6))

        return CumulativeEffect(
            period_labels=labels,
            cumulative_allocation=cum_a,
            cumulative_selection=cum_s,
            cumulative_interaction=cum_i,
            cumulative_active=cum_active,
        )

    @staticmethod
    def _compound_return(returns: list[float]) -> float:
        """Compound a series of periodic returns."""
        cum = 1.0
        for r in returns:
            cum *= (1 + r)
        return cum - 1
