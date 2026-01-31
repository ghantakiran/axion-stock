"""Dividend Tracker Data Models.

Dataclasses for dividend events, income, yields, safety, and projections.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

from src.dividends.config import (
    DividendFrequency,
    DividendType,
    SafetyRating,
    DividendStatus,
    TaxClassification,
    FREQUENCY_MULTIPLIERS,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Core Dividend Models
# =============================================================================

@dataclass
class DividendEvent:
    """A dividend distribution event."""
    event_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Key dates
    declaration_date: Optional[date] = None
    ex_dividend_date: Optional[date] = None
    record_date: Optional[date] = None
    payment_date: Optional[date] = None
    
    # Amount
    amount: float = 0.0  # Per share
    frequency: DividendFrequency = DividendFrequency.QUARTERLY
    dividend_type: DividendType = DividendType.REGULAR
    
    # Tax classification
    is_qualified: bool = True
    tax_classification: TaxClassification = TaxClassification.QUALIFIED
    
    # Changes
    previous_amount: Optional[float] = None
    
    @property
    def change_pct(self) -> Optional[float]:
        """Calculate change from previous dividend."""
        if self.previous_amount and self.previous_amount > 0:
            return (self.amount - self.previous_amount) / self.previous_amount
        return None
    
    @property
    def annual_amount(self) -> float:
        """Annualized dividend amount."""
        multiplier = FREQUENCY_MULTIPLIERS.get(self.frequency, 4)
        return self.amount * multiplier


@dataclass
class DividendRecord:
    """Historical dividend record."""
    record_id: str = field(default_factory=_new_id)
    symbol: str = ""
    payment_date: Optional[date] = None
    amount: float = 0.0
    dividend_type: DividendType = DividendType.REGULAR
    
    # For year-over-year comparison
    year: int = 0
    quarter: int = 0


@dataclass 
class DividendHolding:
    """A dividend-paying holding in portfolio."""
    symbol: str = ""
    company_name: str = ""
    shares: float = 0.0
    cost_basis: float = 0.0
    current_price: float = 0.0
    sector: str = ""
    
    # Dividend info
    annual_dividend: float = 0.0  # Per share
    frequency: DividendFrequency = DividendFrequency.QUARTERLY
    next_ex_date: Optional[date] = None
    
    @property
    def market_value(self) -> float:
        return self.shares * self.current_price
    
    @property
    def annual_income(self) -> float:
        return self.shares * self.annual_dividend
    
    @property
    def current_yield(self) -> float:
        if self.current_price > 0:
            return self.annual_dividend / self.current_price
        return 0.0
    
    @property
    def yield_on_cost(self) -> float:
        if self.cost_basis > 0:
            avg_cost = self.cost_basis / self.shares if self.shares > 0 else 0
            if avg_cost > 0:
                return self.annual_dividend / avg_cost
        return 0.0


# =============================================================================
# Income Models
# =============================================================================

@dataclass
class DividendIncome:
    """Projected dividend income for a holding."""
    symbol: str = ""
    shares: float = 0.0
    
    # Annual projections
    annual_dividend_per_share: float = 0.0
    annual_income: float = 0.0
    
    # Monthly breakdown
    monthly_income: list[float] = field(default_factory=lambda: [0.0] * 12)
    
    # Yield metrics
    current_yield: float = 0.0
    yield_on_cost: float = 0.0
    forward_yield: float = 0.0


@dataclass
class PortfolioIncome:
    """Total portfolio dividend income."""
    # Total projections
    annual_income: float = 0.0
    monthly_average: float = 0.0
    
    # Monthly breakdown (Jan-Dec)
    monthly_projections: dict[str, float] = field(default_factory=dict)
    
    # By holding
    income_by_symbol: dict[str, float] = field(default_factory=dict)
    
    # Yield metrics
    portfolio_yield: float = 0.0
    weighted_yield_on_cost: float = 0.0
    
    # Portfolio value
    total_value: float = 0.0
    total_cost_basis: float = 0.0


# =============================================================================
# Yield Models
# =============================================================================

@dataclass
class YieldAnalysis:
    """Yield analysis for a stock."""
    symbol: str = ""
    
    # Current yields
    current_yield: float = 0.0
    forward_yield: float = 0.0
    trailing_yield: float = 0.0
    yield_on_cost: float = 0.0
    
    # Comparison
    sector_avg_yield: float = 0.0
    yield_vs_sector: float = 0.0
    
    # Historical context
    yield_5y_avg: float = 0.0
    yield_5y_high: float = 0.0
    yield_5y_low: float = 0.0
    yield_percentile: float = 0.0  # Current vs 5yr range


# =============================================================================
# Safety Models
# =============================================================================

@dataclass
class DividendSafety:
    """Dividend safety assessment."""
    safety_id: str = field(default_factory=_new_id)
    symbol: str = ""
    
    # Payout ratios
    payout_ratio: float = 0.0  # Dividends / EPS
    cash_payout_ratio: float = 0.0  # Dividends / FCF
    coverage_ratio: float = 0.0  # EPS / DPS
    
    # Balance sheet health
    debt_to_ebitda: float = 0.0
    interest_coverage: float = 0.0
    current_ratio: float = 0.0
    
    # Scoring
    safety_score: float = 0.0  # 0-100
    safety_rating: SafetyRating = SafetyRating.MODERATE
    
    # Red flags
    red_flags: list[str] = field(default_factory=list)
    
    # Analysis date
    as_of_date: date = field(default_factory=date.today)


# =============================================================================
# Growth Models
# =============================================================================

@dataclass
class DividendGrowth:
    """Dividend growth analysis."""
    symbol: str = ""
    
    # Historical growth rates
    cagr_1y: float = 0.0
    cagr_3y: float = 0.0
    cagr_5y: float = 0.0
    cagr_10y: float = 0.0
    
    # Streak
    consecutive_increases: int = 0
    years_of_dividends: int = 0
    status: DividendStatus = DividendStatus.NONE
    
    # Current dividend info
    current_annual_dividend: float = 0.0
    most_recent_increase_pct: float = 0.0
    
    # History
    dividend_history: list[DividendRecord] = field(default_factory=list)


# =============================================================================
# DRIP Models
# =============================================================================

@dataclass
class DRIPYear:
    """Single year in DRIP simulation."""
    year: int = 0
    starting_shares: float = 0.0
    starting_value: float = 0.0
    
    # Dividend info
    dividend_per_share: float = 0.0
    dividends_received: float = 0.0
    
    # Reinvestment
    share_price: float = 0.0
    shares_purchased: float = 0.0
    
    # Ending state
    ending_shares: float = 0.0
    ending_value: float = 0.0
    
    # Yield metrics
    yield_on_original_cost: float = 0.0
    income_growth_pct: float = 0.0


@dataclass
class DRIPSimulation:
    """DRIP simulation results."""
    simulation_id: str = field(default_factory=_new_id)
    symbol: str = ""
    
    # Initial state
    initial_shares: float = 0.0
    initial_investment: float = 0.0
    initial_price: float = 0.0
    initial_dividend: float = 0.0
    
    # Simulation parameters
    years: int = 20
    dividend_growth_rate: float = 0.05
    price_growth_rate: float = 0.07
    
    # Final results
    final_shares: float = 0.0
    final_value: float = 0.0
    final_annual_income: float = 0.0
    
    # Totals
    total_dividends_received: float = 0.0
    total_shares_from_drip: float = 0.0
    
    # Year-by-year
    yearly_projections: list[DRIPYear] = field(default_factory=list)
    
    # Returns
    total_return_pct: float = 0.0
    annualized_return: float = 0.0


# =============================================================================
# Tax Models
# =============================================================================

@dataclass
class DividendTaxAnalysis:
    """Tax analysis for dividend income."""
    tax_id: str = field(default_factory=_new_id)
    tax_year: int = 0
    
    # Income breakdown
    qualified_dividends: float = 0.0
    non_qualified_dividends: float = 0.0
    return_of_capital: float = 0.0
    foreign_dividends: float = 0.0
    foreign_tax_withheld: float = 0.0
    
    # Total income
    total_dividend_income: float = 0.0
    
    # Tax estimates
    estimated_tax_qualified: float = 0.0
    estimated_tax_ordinary: float = 0.0
    total_estimated_tax: float = 0.0
    
    # After-tax
    after_tax_income: float = 0.0
    effective_tax_rate: float = 0.0
