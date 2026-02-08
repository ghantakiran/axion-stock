"""Configuration for GIPS-compliant performance reporting."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ReturnMethod(str, Enum):
    TIME_WEIGHTED = "time_weighted"
    MONEY_WEIGHTED = "money_weighted"
    MODIFIED_DIETZ = "modified_dietz"
    DAILY_VALUATION = "daily_valuation"


class FeeType(str, Enum):
    GROSS = "gross"
    NET = "net"
    BOTH = "both"


class CompositeMembership(str, Enum):
    FULL_PERIOD = "full_period"
    BEGINNING_OF_PERIOD = "beginning_of_period"
    SINCE_INCEPTION = "since_inception"


class DispersionMethod(str, Enum):
    ASSET_WEIGHTED_STD = "asset_weighted_std"
    EQUAL_WEIGHTED_STD = "equal_weighted_std"
    HIGH_LOW_RANGE = "high_low_range"
    INTERQUARTILE = "interquartile"


class ReportPeriod(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    SINCE_INCEPTION = "since_inception"


# GIPS requires large external cash flow threshold
LARGE_CASH_FLOW_PCT = 0.10  # 10% of portfolio value

# Minimum years of performance history for GIPS
MIN_HISTORY_YEARS = 5  # Build up to 10 years

# 3-year annualized std dev required by GIPS
ANNUALIZED_STD_YEARS = 3

# Minimum portfolios for dispersion to be meaningful
MIN_PORTFOLIOS_DISPERSION = 6


@dataclass
class FeeSchedule:
    """Fee tiers for gross/net return calculation."""

    tiers: List[Dict[str, float]] = field(default_factory=lambda: [
        {"breakpoint": 1_000_000, "rate": 0.0100},
        {"breakpoint": 5_000_000, "rate": 0.0075},
        {"breakpoint": 25_000_000, "rate": 0.0050},
        {"breakpoint": float("inf"), "rate": 0.0035},
    ])

    def get_fee_rate(self, assets: float) -> float:
        for tier in self.tiers:
            if assets <= tier["breakpoint"]:
                return tier["rate"]
        return self.tiers[-1]["rate"]


@dataclass
class CompositeConfig:
    """Configuration for a composite."""

    name: str = "Default Composite"
    strategy: str = "All Cap Equity"
    benchmark_name: str = "S&P 500"
    membership_rule: CompositeMembership = CompositeMembership.FULL_PERIOD
    min_portfolio_size: float = 100_000
    currency: str = "USD"
    fee_schedule: FeeSchedule = field(default_factory=FeeSchedule)
    inception_date: Optional[str] = None
    creation_date: Optional[str] = None


@dataclass
class GIPSConfig:
    """Master GIPS configuration."""

    firm_name: str = "Investment Firm"
    firm_definition: str = "Registered investment advisor managing equity portfolios"
    compliance_since: str = "2020-01-01"
    return_method: ReturnMethod = ReturnMethod.DAILY_VALUATION
    fee_type: FeeType = FeeType.BOTH
    dispersion_method: DispersionMethod = DispersionMethod.ASSET_WEIGHTED_STD
    report_period: ReportPeriod = ReportPeriod.ANNUAL
    large_cash_flow_threshold: float = LARGE_CASH_FLOW_PCT
    include_3yr_std_dev: bool = True
    min_history_years: int = MIN_HISTORY_YEARS
    verification_status: str = "Not Verified"
    total_firm_assets: float = 0.0
