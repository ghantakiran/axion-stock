"""Data models for GIPS performance reporting."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class PortfolioAssignment:
    """Portfolio membership in a composite."""

    portfolio_id: str
    composite_id: str
    join_date: date
    leave_date: Optional[date] = None
    market_value: float = 0.0
    is_active: bool = True


@dataclass
class PerformanceRecord:
    """Single-period return for a portfolio."""

    portfolio_id: str
    period_start: date
    period_end: date
    gross_return: float = 0.0
    net_return: float = 0.0
    beginning_value: float = 0.0
    ending_value: float = 0.0
    cash_flows: float = 0.0
    weight: float = 0.0


@dataclass
class CompositeDefinition:
    """GIPS composite definition."""

    composite_id: str
    name: str
    strategy: str
    benchmark_name: str
    inception_date: date
    creation_date: date
    description: str = ""
    currency: str = "USD"
    membership_rules: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    portfolios: List[PortfolioAssignment] = field(default_factory=list)

    @property
    def active_portfolios(self) -> List[PortfolioAssignment]:
        return [p for p in self.portfolios if p.is_active]

    @property
    def n_portfolios(self) -> int:
        return len(self.active_portfolios)


@dataclass
class CompositeReturn:
    """Composite-level return for a period."""

    composite_id: str
    period_start: date
    period_end: date
    gross_return: float = 0.0
    net_return: float = 0.0
    benchmark_return: float = 0.0
    n_portfolios: int = 0
    composite_assets: float = 0.0
    firm_assets: float = 0.0
    pct_firm_assets: float = 0.0

    @property
    def excess_return_gross(self) -> float:
        return self.gross_return - self.benchmark_return

    @property
    def excess_return_net(self) -> float:
        return self.net_return - self.benchmark_return


@dataclass
class CompositePeriod:
    """Annual composite statistics for GIPS presentation."""

    year: int
    gross_return: float = 0.0
    net_return: float = 0.0
    benchmark_return: float = 0.0
    n_portfolios: int = 0
    composite_assets: float = 0.0
    firm_assets: float = 0.0
    pct_firm_assets: float = 0.0
    dispersion: Optional[float] = None
    composite_3yr_std: Optional[float] = None
    benchmark_3yr_std: Optional[float] = None


@dataclass
class DispersionResult:
    """Internal dispersion calculation result."""

    method: str
    value: float
    n_portfolios: int
    high: float = 0.0
    low: float = 0.0
    median: float = 0.0
    is_meaningful: bool = True  # False if < 6 portfolios


@dataclass
class GIPSDisclosure:
    """Required GIPS disclosure item."""

    category: str
    text: str
    is_required: bool = True
    effective_date: Optional[date] = None


@dataclass
class ComplianceCheck:
    """Individual compliance check result."""

    rule_id: str
    description: str
    passed: bool
    severity: str = "error"  # error, warning, info
    details: str = ""


@dataclass
class ComplianceReport:
    """Overall GIPS compliance assessment."""

    composite_id: str
    checked_at: datetime = field(default_factory=datetime.now)
    checks: List[ComplianceCheck] = field(default_factory=list)
    overall_compliant: bool = False

    @property
    def errors(self) -> List[ComplianceCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> List[ComplianceCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    @property
    def pass_rate(self) -> float:
        if not self.checks:
            return 0.0
        return len([c for c in self.checks if c.passed]) / len(self.checks)


@dataclass
class GIPSPresentation:
    """Complete GIPS-compliant presentation."""

    composite_name: str
    firm_name: str
    benchmark_name: str
    periods: List[CompositePeriod] = field(default_factory=list)
    disclosures: List[GIPSDisclosure] = field(default_factory=list)
    compliance_status: str = "Compliant"
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def years_of_history(self) -> int:
        return len(self.periods)

    @property
    def cumulative_gross(self) -> float:
        if not self.periods:
            return 0.0
        cumulative = 1.0
        for p in self.periods:
            cumulative *= (1 + p.gross_return)
        return cumulative - 1.0

    @property
    def cumulative_benchmark(self) -> float:
        if not self.periods:
            return 0.0
        cumulative = 1.0
        for p in self.periods:
            cumulative *= (1 + p.benchmark_return)
        return cumulative - 1.0
