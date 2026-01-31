"""Performance Attribution data models.

Dataclasses for attribution results, benchmark comparisons, and tear sheets.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
import uuid

from src.attribution.config import (
    AttributionMethod,
    AttributionLevel,
    TimePeriod,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class SectorAttribution:
    """Attribution for a single sector.

    Attributes:
        sector: Sector name.
        portfolio_weight: Portfolio weight in this sector.
        benchmark_weight: Benchmark weight in this sector.
        portfolio_return: Portfolio return within this sector.
        benchmark_return: Benchmark return within this sector.
        allocation_effect: Return from weight differences.
        selection_effect: Return from stock picking.
        interaction_effect: Combined allocation/selection.
        total_effect: Total active contribution.
    """
    sector: str = ""
    portfolio_weight: float = 0.0
    benchmark_weight: float = 0.0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    total_effect: float = 0.0


@dataclass
class BrinsonAttribution:
    """Brinson-Fachler attribution results.

    Attributes:
        portfolio_return: Total portfolio return.
        benchmark_return: Total benchmark return.
        active_return: Portfolio - benchmark return.
        total_allocation: Sum of allocation effects.
        total_selection: Sum of selection effects.
        total_interaction: Sum of interaction effects.
        sectors: Per-sector attribution breakdown.
        start_date: Analysis start date.
        end_date: Analysis end date.
    """
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    total_allocation: float = 0.0
    total_selection: float = 0.0
    total_interaction: float = 0.0
    sectors: list[SectorAttribution] = field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @property
    def attribution_sum(self) -> float:
        """Sum of all effects (should equal active_return)."""
        return self.total_allocation + self.total_selection + self.total_interaction


@dataclass
class FactorContribution:
    """Contribution of a single factor.

    Attributes:
        factor: Factor name.
        exposure: Portfolio exposure to this factor.
        factor_return: Factor's return in the period.
        contribution: exposure × factor_return.
    """
    factor: str = ""
    exposure: float = 0.0
    factor_return: float = 0.0
    contribution: float = 0.0


@dataclass
class FactorAttribution:
    """Factor-based attribution results.

    Attributes:
        portfolio_return: Total portfolio return.
        factor_return_total: Return explained by factors.
        specific_return: Residual/alpha return.
        factors: Per-factor contributions.
        r_squared: R² of factor model.
    """
    portfolio_return: float = 0.0
    factor_return_total: float = 0.0
    specific_return: float = 0.0
    factors: list[FactorContribution] = field(default_factory=list)
    r_squared: float = 0.0


@dataclass
class BenchmarkComparison:
    """Portfolio vs benchmark comparison metrics.

    Attributes:
        benchmark_id: Benchmark identifier.
        benchmark_name: Benchmark display name.
        portfolio_return: Portfolio total return.
        benchmark_return: Benchmark total return.
        active_return: Excess return.
        tracking_error: Annualized tracking error.
        information_ratio: Active return / tracking error.
        active_share: Fraction of portfolio differing from benchmark.
        up_capture: Up market capture ratio.
        down_capture: Down market capture ratio.
        beta: Portfolio beta to benchmark.
        alpha: Jensen's alpha.
        correlation: Return correlation.
    """
    benchmark_id: str = ""
    benchmark_name: str = ""
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    active_share: float = 0.0
    up_capture: float = 0.0
    down_capture: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    correlation: float = 0.0


@dataclass
class DrawdownPeriod:
    """A single drawdown period.

    Attributes:
        start_date: Drawdown start.
        trough_date: Maximum drawdown date.
        end_date: Recovery date (None if ongoing).
        depth: Maximum drawdown depth (negative).
        duration_days: Total days from start to recovery.
        recovery_days: Days from trough to recovery.
    """
    start_date: Optional[date] = None
    trough_date: Optional[date] = None
    end_date: Optional[date] = None
    depth: float = 0.0
    duration_days: int = 0
    recovery_days: int = 0


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics.

    Attributes:
        total_return: Cumulative return.
        annualized_return: Annualized (CAGR).
        volatility: Annualized volatility.
        sharpe_ratio: Sharpe ratio.
        sortino_ratio: Sortino ratio.
        calmar_ratio: Calmar ratio.
        max_drawdown: Maximum drawdown.
        win_rate: Fraction of positive-return days.
        best_day: Best daily return.
        worst_day: Worst daily return.
        avg_daily_return: Average daily return.
        skewness: Return distribution skewness.
        kurtosis: Return distribution excess kurtosis.
        var_95: 95% daily VaR.
        cvar_95: 95% conditional VaR.
        positive_days: Count of positive days.
        negative_days: Count of negative days.
        total_days: Total trading days.
    """
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    best_day: float = 0.0
    worst_day: float = 0.0
    avg_daily_return: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    positive_days: int = 0
    negative_days: int = 0
    total_days: int = 0


@dataclass
class MonthlyReturns:
    """Monthly return data for heatmap display.

    Attributes:
        year: Year.
        month: Month (1-12).
        portfolio_return: Monthly portfolio return.
        benchmark_return: Monthly benchmark return.
        active_return: Monthly active return.
    """
    year: int = 0
    month: int = 0
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0


@dataclass
class TearSheet:
    """Complete performance tear sheet.

    Attributes:
        report_id: Unique report identifier.
        name: Report name.
        period: Time period analyzed.
        metrics: Performance metrics.
        benchmark_comparison: Benchmark comparison.
        brinson: Brinson attribution (optional).
        factor_attribution: Factor attribution (optional).
        monthly_returns: Monthly return data.
        top_drawdowns: Top drawdown periods.
        rolling_sharpe: Rolling Sharpe ratio data points.
        rolling_volatility: Rolling volatility data points.
        generated_at: Generation timestamp.
    """
    report_id: str = field(default_factory=_new_id)
    name: str = ""
    period: TimePeriod = TimePeriod.ONE_YEAR
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    benchmark_comparison: Optional[BenchmarkComparison] = None
    brinson: Optional[BrinsonAttribution] = None
    factor_attribution: Optional[FactorAttribution] = None
    monthly_returns: list[MonthlyReturns] = field(default_factory=list)
    top_drawdowns: list[DrawdownPeriod] = field(default_factory=list)
    rolling_sharpe: list[tuple[date, float]] = field(default_factory=list)
    rolling_volatility: list[tuple[date, float]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_utc_now)
