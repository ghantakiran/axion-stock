"""Tax Optimization Data Models.

Dataclasses for tax lots, gains/losses, wash sales, and reports.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
import uuid

from src.tax.config import (
    HoldingPeriod,
    AcquisitionType,
    AccountType,
    LotSelectionMethod,
    BasisReportingCategory,
    AdjustmentCode,
    FilingStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# =============================================================================
# Core Tax Models
# =============================================================================

@dataclass
class TaxLot:
    """Individual tax lot for cost basis tracking.
    
    Represents a specific acquisition of shares with its own cost basis
    and acquisition date for tax purposes.
    """
    lot_id: str = field(default_factory=_new_id)
    account_id: str = ""
    symbol: str = ""
    shares: float = 0.0
    cost_basis: float = 0.0  # Total cost basis for all shares
    adjusted_basis: float = 0.0  # After wash sale adjustments
    acquisition_date: date = field(default_factory=date.today)
    acquisition_type: AcquisitionType = AcquisitionType.BUY
    wash_sale_adjustment: float = 0.0
    remaining_shares: float = 0.0  # Shares not yet sold
    created_at: datetime = field(default_factory=_utc_now)
    
    def __post_init__(self):
        if self.remaining_shares == 0.0:
            self.remaining_shares = self.shares
        if self.adjusted_basis == 0.0:
            self.adjusted_basis = self.cost_basis
    
    @property
    def cost_per_share(self) -> float:
        """Cost basis per share."""
        if self.shares == 0:
            return 0.0
        return self.cost_basis / self.shares
    
    @property
    def adjusted_cost_per_share(self) -> float:
        """Adjusted cost basis per share (after wash sale adjustments)."""
        if self.shares == 0:
            return 0.0
        return self.adjusted_basis / self.shares
    
    @property
    def holding_period(self) -> HoldingPeriod:
        """Determine if short-term or long-term based on acquisition date."""
        days_held = (date.today() - self.acquisition_date).days
        if days_held > 365:
            return HoldingPeriod.LONG_TERM
        return HoldingPeriod.SHORT_TERM
    
    @property
    def days_held(self) -> int:
        """Number of days this lot has been held."""
        return (date.today() - self.acquisition_date).days
    
    @property
    def days_to_long_term(self) -> int:
        """Days until this lot becomes long-term. Negative if already long-term."""
        return 366 - self.days_held
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "shares": self.shares,
            "cost_basis": self.cost_basis,
            "adjusted_basis": self.adjusted_basis,
            "acquisition_date": self.acquisition_date.isoformat(),
            "acquisition_type": self.acquisition_type.value,
            "holding_period": self.holding_period.value,
            "remaining_shares": self.remaining_shares,
            "wash_sale_adjustment": self.wash_sale_adjustment,
        }


@dataclass
class RealizedGain:
    """Record of a realized gain or loss from a sale."""
    gain_id: str = field(default_factory=_new_id)
    account_id: str = ""
    lot_id: str = ""
    symbol: str = ""
    shares: float = 0.0
    proceeds: float = 0.0
    cost_basis: float = 0.0
    gain_loss: float = 0.0
    holding_period: HoldingPeriod = HoldingPeriod.SHORT_TERM
    sale_date: date = field(default_factory=date.today)
    acquisition_date: date = field(default_factory=date.today)
    is_wash_sale: bool = False
    disallowed_loss: float = 0.0
    adjustment_code: Optional[AdjustmentCode] = None
    basis_category: BasisReportingCategory = BasisReportingCategory.A
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def net_gain_loss(self) -> float:
        """Net gain/loss after wash sale disallowance."""
        if self.is_wash_sale and self.gain_loss < 0:
            return self.gain_loss + self.disallowed_loss
        return self.gain_loss
    
    @property
    def is_gain(self) -> bool:
        return self.gain_loss > 0
    
    @property
    def is_loss(self) -> bool:
        return self.gain_loss < 0


@dataclass
class WashSale:
    """Wash sale record tracking disallowed losses."""
    wash_sale_id: str = field(default_factory=_new_id)
    account_id: str = ""
    loss_sale_id: str = ""  # Reference to RealizedGain
    replacement_lot_id: str = ""  # Reference to TaxLot
    symbol: str = ""
    disallowed_loss: float = 0.0
    basis_adjustment: float = 0.0
    holding_period_adjustment_days: int = 0
    loss_sale_date: date = field(default_factory=date.today)
    replacement_date: date = field(default_factory=date.today)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class HarvestOpportunity:
    """Tax-loss harvesting opportunity."""
    symbol: str = ""
    lot_id: str = ""
    shares: float = 0.0
    current_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_loss: float = 0.0
    holding_period: HoldingPeriod = HoldingPeriod.SHORT_TERM
    days_held: int = 0
    estimated_tax_savings: float = 0.0
    wash_sale_risk: bool = False
    last_purchase_date: Optional[date] = None
    substitute_symbols: list[str] = field(default_factory=list)
    
    @property
    def loss_percentage(self) -> float:
        """Loss as percentage of cost basis."""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_loss / self.cost_basis


@dataclass
class HarvestResult:
    """Result of executing a tax-loss harvest."""
    harvest_id: str = field(default_factory=_new_id)
    account_id: str = ""
    symbol: str = ""
    shares: float = 0.0
    proceeds: float = 0.0
    loss_realized: float = 0.0
    tax_savings: float = 0.0
    replacement_symbol: Optional[str] = None
    replacement_shares: float = 0.0
    harvest_date: date = field(default_factory=date.today)
    repurchase_eligible_date: date = field(default_factory=date.today)
    status: str = "pending"  # pending, completed, cancelled


# =============================================================================
# Gain/Loss Tracking
# =============================================================================

@dataclass
class GainLossReport:
    """Comprehensive gain/loss report for a period."""
    # Realized (closed positions)
    short_term_realized_gains: float = 0.0
    short_term_realized_losses: float = 0.0
    long_term_realized_gains: float = 0.0
    long_term_realized_losses: float = 0.0
    
    # Unrealized (open positions)
    short_term_unrealized_gains: float = 0.0
    short_term_unrealized_losses: float = 0.0
    long_term_unrealized_gains: float = 0.0
    long_term_unrealized_losses: float = 0.0
    
    # Wash sale impact
    disallowed_losses: float = 0.0
    pending_adjustments: float = 0.0
    
    # Period info
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)
    
    @property
    def net_short_term_realized(self) -> float:
        return self.short_term_realized_gains + self.short_term_realized_losses
    
    @property
    def net_long_term_realized(self) -> float:
        return self.long_term_realized_gains + self.long_term_realized_losses
    
    @property
    def total_realized(self) -> float:
        return self.net_short_term_realized + self.net_long_term_realized
    
    @property
    def net_short_term_unrealized(self) -> float:
        return self.short_term_unrealized_gains + self.short_term_unrealized_losses
    
    @property
    def net_long_term_unrealized(self) -> float:
        return self.long_term_unrealized_gains + self.long_term_unrealized_losses
    
    @property
    def total_unrealized(self) -> float:
        return self.net_short_term_unrealized + self.net_long_term_unrealized
    
    @property
    def adjusted_realized_loss(self) -> float:
        """Net realized loss after wash sale disallowances."""
        total_loss = (self.short_term_realized_losses + 
                      self.long_term_realized_losses)
        return total_loss + self.disallowed_losses  # disallowed is positive


# =============================================================================
# Tax Estimation
# =============================================================================

@dataclass
class TaxEstimate:
    """Estimated tax liability breakdown."""
    # Income components
    ordinary_income: float = 0.0
    short_term_gains: float = 0.0
    long_term_gains: float = 0.0
    total_taxable_income: float = 0.0
    
    # Federal taxes
    federal_ordinary_tax: float = 0.0
    federal_stcg_tax: float = 0.0
    federal_ltcg_tax: float = 0.0
    federal_niit: float = 0.0
    total_federal_tax: float = 0.0
    
    # State taxes
    state: str = ""
    state_tax: float = 0.0
    
    # Totals
    total_tax: float = 0.0
    effective_rate: float = 0.0
    marginal_rate: float = 0.0
    
    # Tax on investment income specifically
    investment_income_tax: float = 0.0
    investment_effective_rate: float = 0.0
    
    filing_status: FilingStatus = FilingStatus.SINGLE
    tax_year: int = 2024


@dataclass
class TaxSavingsProjection:
    """Projected tax savings from an action."""
    action: str = ""  # e.g., "harvest_loss", "hold_for_long_term"
    current_tax: float = 0.0
    projected_tax: float = 0.0
    tax_savings: float = 0.0
    assumptions: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Tax Reports
# =============================================================================

@dataclass
class Form8949Entry:
    """Single line item for Form 8949."""
    description: str = ""  # e.g., "100 sh AAPL"
    date_acquired: date = field(default_factory=date.today)
    date_sold: date = field(default_factory=date.today)
    proceeds: float = 0.0
    cost_basis: float = 0.0
    adjustment_code: Optional[str] = None
    adjustment_amount: float = 0.0
    gain_loss: float = 0.0
    category: BasisReportingCategory = BasisReportingCategory.A


@dataclass
class Form8949:
    """IRS Form 8949 - Sales and Other Dispositions of Capital Assets."""
    tax_year: int = 2024
    name: str = ""
    ssn: str = ""
    
    # Part I - Short-term
    short_term_entries: list[Form8949Entry] = field(default_factory=list)
    
    # Part II - Long-term
    long_term_entries: list[Form8949Entry] = field(default_factory=list)
    
    @property
    def short_term_proceeds(self) -> float:
        return sum(e.proceeds for e in self.short_term_entries)
    
    @property
    def short_term_basis(self) -> float:
        return sum(e.cost_basis for e in self.short_term_entries)
    
    @property
    def short_term_adjustments(self) -> float:
        return sum(e.adjustment_amount for e in self.short_term_entries)
    
    @property
    def short_term_gain_loss(self) -> float:
        return sum(e.gain_loss for e in self.short_term_entries)
    
    @property
    def long_term_proceeds(self) -> float:
        return sum(e.proceeds for e in self.long_term_entries)
    
    @property
    def long_term_basis(self) -> float:
        return sum(e.cost_basis for e in self.long_term_entries)
    
    @property
    def long_term_adjustments(self) -> float:
        return sum(e.adjustment_amount for e in self.long_term_entries)
    
    @property
    def long_term_gain_loss(self) -> float:
        return sum(e.gain_loss for e in self.long_term_entries)


@dataclass
class ScheduleD:
    """IRS Schedule D - Capital Gains and Losses summary."""
    tax_year: int = 2024
    
    # Short-term (Part I)
    short_term_from_8949: float = 0.0
    short_term_from_k1: float = 0.0
    short_term_carryover: float = 0.0
    net_short_term: float = 0.0
    
    # Long-term (Part II)
    long_term_from_8949: float = 0.0
    long_term_from_k1: float = 0.0
    long_term_carryover: float = 0.0
    net_long_term: float = 0.0
    
    # Summary (Part III)
    net_capital_gain_loss: float = 0.0
    capital_loss_carryover: float = 0.0  # To next year
    
    def calculate_totals(self) -> None:
        """Calculate summary totals."""
        self.net_short_term = (self.short_term_from_8949 + 
                               self.short_term_from_k1 + 
                               self.short_term_carryover)
        self.net_long_term = (self.long_term_from_8949 + 
                              self.long_term_from_k1 + 
                              self.long_term_carryover)
        self.net_capital_gain_loss = self.net_short_term + self.net_long_term
        
        # Capital loss limitation ($3,000 per year for individuals)
        if self.net_capital_gain_loss < -3000:
            self.capital_loss_carryover = self.net_capital_gain_loss + 3000


@dataclass
class TaxSummaryReport:
    """Annual tax summary report."""
    tax_year: int = 2024
    account_id: str = ""
    
    # Realized gains/losses
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    short_term_gain_loss: float = 0.0
    long_term_gain_loss: float = 0.0
    net_gain_loss: float = 0.0
    
    # Wash sales
    wash_sale_disallowed: float = 0.0
    wash_sale_count: int = 0
    
    # Harvesting activity
    total_harvested_losses: float = 0.0
    harvest_count: int = 0
    estimated_tax_savings: float = 0.0
    
    # Dividends
    qualified_dividends: float = 0.0
    ordinary_dividends: float = 0.0
    
    # Tax estimate
    estimated_tax_liability: float = 0.0
    effective_rate: float = 0.0
    
    generated_at: datetime = field(default_factory=_utc_now)
