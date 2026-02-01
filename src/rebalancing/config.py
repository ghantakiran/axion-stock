"""Portfolio Rebalancing Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class RebalanceTrigger(str, Enum):
    """What triggers a rebalance."""
    CALENDAR = "calendar"
    THRESHOLD = "threshold"
    COMBINED = "combined"
    MANUAL = "manual"


class RebalanceFrequency(str, Enum):
    """Calendar rebalance frequency."""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class DriftMethod(str, Enum):
    """Drift measurement method."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


class RebalanceStatus(str, Enum):
    """Rebalance execution status."""
    PENDING = "pending"
    EXECUTED = "executed"
    SKIPPED = "skipped"
    PARTIAL = "partial"


@dataclass(frozen=True)
class DriftConfig:
    """Drift monitoring configuration."""
    method: DriftMethod = DriftMethod.ABSOLUTE
    threshold: float = 0.05
    critical_threshold: float = 0.10
    check_frequency_days: int = 1


@dataclass(frozen=True)
class CalendarConfig:
    """Calendar-based rebalance configuration."""
    frequency: RebalanceFrequency = RebalanceFrequency.QUARTERLY
    day_of_week: int = 0  # Monday
    day_of_month: int = 1
    month_of_quarter: int = 1  # First month


@dataclass(frozen=True)
class TaxConfig:
    """Tax-aware rebalancing configuration."""
    enabled: bool = True
    short_term_days: int = 365
    harvest_threshold: float = 0.03
    wash_sale_days: int = 30
    avoid_short_term_gains: bool = True


@dataclass(frozen=True)
class CostConfig:
    """Rebalance cost configuration."""
    commission_per_trade: float = 0.0
    spread_cost_bps: float = 1.0
    min_trade_dollars: float = 100.0
    min_trade_shares: int = 1


@dataclass(frozen=True)
class RebalancingConfig:
    """Complete rebalancing configuration."""
    trigger: RebalanceTrigger = RebalanceTrigger.COMBINED
    drift: DriftConfig = field(default_factory=DriftConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
    cost: CostConfig = field(default_factory=CostConfig)


DEFAULT_DRIFT_CONFIG = DriftConfig()
DEFAULT_CALENDAR_CONFIG = CalendarConfig()
DEFAULT_TAX_CONFIG = TaxConfig()
DEFAULT_COST_CONFIG = CostConfig()
DEFAULT_CONFIG = RebalancingConfig()
