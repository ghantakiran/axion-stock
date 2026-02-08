"""GIPS-compliant performance calculations."""

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from .config import (
    FeeSchedule,
    GIPSConfig,
    LARGE_CASH_FLOW_PCT,
    ReturnMethod,
)
from .models import CompositePeriod, CompositeReturn, PerformanceRecord


class GIPSCalculator:
    """GIPS-compliant return calculations: TWR, MWR, gross/net separation."""

    def __init__(self, config: Optional[GIPSConfig] = None):
        self.config = config or GIPSConfig()

    def time_weighted_return(
        self, values: List[float], cash_flows: Optional[List[float]] = None
    ) -> float:
        """Calculate time-weighted return from sequential valuations."""
        if len(values) < 2:
            return 0.0

        flows = cash_flows or [0.0] * (len(values) - 1)
        twr = 1.0

        for i in range(1, len(values)):
            bv = values[i - 1]
            ev = values[i]
            cf = flows[i - 1] if i - 1 < len(flows) else 0.0

            if bv + cf == 0:
                continue

            sub_return = (ev - bv - cf) / (bv + cf)
            twr *= (1 + sub_return)

        return twr - 1.0

    def modified_dietz_return(
        self,
        beginning_value: float,
        ending_value: float,
        cash_flows: List[Tuple[float, float]],
    ) -> float:
        """Modified Dietz return with day-weighted cash flows.

        Args:
            beginning_value: Start-of-period value
            ending_value: End-of-period value
            cash_flows: List of (amount, weight) where weight is fraction of period remaining
        """
        if beginning_value <= 0:
            return 0.0

        weighted_cf = sum(cf * w for cf, w in cash_flows)
        total_cf = sum(cf for cf, _ in cash_flows)

        denominator = beginning_value + weighted_cf
        if denominator <= 0:
            return 0.0

        return (ending_value - beginning_value - total_cf) / denominator

    def money_weighted_return(
        self,
        beginning_value: float,
        ending_value: float,
        cash_flows: List[Tuple[float, int]],
        total_days: int = 365,
        max_iter: int = 100,
    ) -> float:
        """IRR-based money-weighted return via Newton's method.

        Args:
            beginning_value: Start value
            ending_value: End value
            cash_flows: List of (amount, day_number)
            total_days: Total days in period
        """
        if beginning_value <= 0:
            return 0.0

        # Build cash flow vector: negative for outflows (initial investment)
        cf_list = [(-beginning_value, 0)] + list(cash_flows) + [(ending_value, total_days)]

        r = 0.05  # initial guess
        for _ in range(max_iter):
            npv = sum(cf / (1 + r) ** (d / 365) for cf, d in cf_list)
            dnpv = sum(-cf * (d / 365) / (1 + r) ** (d / 365 + 1) for cf, d in cf_list)

            if abs(dnpv) < 1e-12:
                break

            r_new = r - npv / dnpv
            if abs(r_new - r) < 1e-8:
                r = r_new
                break
            r = r_new

        return r

    def gross_to_net(
        self, gross_return: float, fee_rate: float, periods: int = 1
    ) -> float:
        """Convert gross return to net return by deducting fees."""
        periodic_fee = fee_rate / max(periods, 1)
        return gross_return - periodic_fee

    def net_to_gross(
        self, net_return: float, fee_rate: float, periods: int = 1
    ) -> float:
        """Convert net return to gross return by adding fees."""
        periodic_fee = fee_rate / max(periods, 1)
        return net_return + periodic_fee

    def annualize_return(self, total_return: float, years: float) -> float:
        """Annualize a cumulative return."""
        if years <= 0:
            return 0.0
        if total_return <= -1.0:
            return -1.0
        return (1 + total_return) ** (1.0 / years) - 1.0

    def annualized_std_dev(self, returns: List[float], periods_per_year: int = 12) -> float:
        """Calculate annualized standard deviation (3-year GIPS requirement)."""
        if len(returns) < 2:
            return 0.0

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(variance * periods_per_year)

    def handle_large_cash_flow(
        self,
        beginning_value: float,
        cash_flow: float,
        threshold: Optional[float] = None,
    ) -> bool:
        """Check if a cash flow exceeds the large cash flow threshold."""
        thresh = threshold or self.config.large_cash_flow_threshold
        if beginning_value <= 0:
            return abs(cash_flow) > 0
        return abs(cash_flow) / beginning_value > thresh

    def link_returns(self, period_returns: List[float]) -> float:
        """Geometrically link sub-period returns."""
        cumulative = 1.0
        for r in period_returns:
            cumulative *= (1 + r)
        return cumulative - 1.0

    def build_annual_periods(
        self,
        composite_returns: List[CompositeReturn],
        monthly_returns_gross: Optional[Dict[int, List[float]]] = None,
        monthly_returns_benchmark: Optional[Dict[int, List[float]]] = None,
    ) -> List[CompositePeriod]:
        """Build annual CompositePeriod records from composite returns."""
        by_year: Dict[int, List[CompositeReturn]] = {}
        for cr in composite_returns:
            year = cr.period_end.year
            by_year.setdefault(year, []).append(cr)

        periods = []
        for year in sorted(by_year.keys()):
            year_returns = by_year[year]
            gross = self.link_returns([cr.gross_return for cr in year_returns])
            net = self.link_returns([cr.net_return for cr in year_returns])
            bench = self.link_returns([cr.benchmark_return for cr in year_returns])

            last = year_returns[-1]

            # 3-year std dev if we have monthly data
            comp_3yr_std = None
            bench_3yr_std = None
            if monthly_returns_gross:
                three_yr = []
                for y in range(year - 2, year + 1):
                    three_yr.extend(monthly_returns_gross.get(y, []))
                if len(three_yr) >= 36:
                    comp_3yr_std = self.annualized_std_dev(three_yr)

            if monthly_returns_benchmark:
                three_yr_b = []
                for y in range(year - 2, year + 1):
                    three_yr_b.extend(monthly_returns_benchmark.get(y, []))
                if len(three_yr_b) >= 36:
                    bench_3yr_std = self.annualized_std_dev(three_yr_b)

            periods.append(CompositePeriod(
                year=year,
                gross_return=gross,
                net_return=net,
                benchmark_return=bench,
                n_portfolios=last.n_portfolios,
                composite_assets=last.composite_assets,
                firm_assets=last.firm_assets,
                pct_firm_assets=last.pct_firm_assets,
                composite_3yr_std=comp_3yr_std,
                benchmark_3yr_std=bench_3yr_std,
            ))

        return periods

    @staticmethod
    def generate_sample_returns(n_years: int = 7) -> List[CompositeReturn]:
        """Generate sample composite returns for demo."""
        import random
        random.seed(42)

        returns = []
        base_year = 2018

        for yr in range(n_years):
            for month in range(1, 13):
                period_start = date(base_year + yr, month, 1)
                if month == 12:
                    period_end = date(base_year + yr, 12, 31)
                else:
                    period_end = date(base_year + yr, month + 1, 1) - timedelta(days=1)

                gross = random.gauss(0.008, 0.035)
                net = gross - 0.0008
                bench = random.gauss(0.007, 0.033)
                assets = 50_000_000 + yr * 10_000_000 + random.randint(-2_000_000, 5_000_000)

                returns.append(CompositeReturn(
                    composite_id="sample",
                    period_start=period_start,
                    period_end=period_end,
                    gross_return=gross,
                    net_return=net,
                    benchmark_return=bench,
                    n_portfolios=5 + yr,
                    composite_assets=assets,
                    firm_assets=assets * 3,
                    pct_firm_assets=33.3,
                ))

        return returns
