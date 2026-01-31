"""Insider Trading Data Models.

Dataclasses for transactions, clusters, institutions, and profiles.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

from src.insider.config import (
    InsiderType,
    TransactionType,
    SignalStrength,
    InstitutionType,
    FilingType,
    BULLISH_TRANSACTIONS,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Insider Transactions
# =============================================================================

@dataclass
class InsiderTransaction:
    """An insider trading transaction."""
    transaction_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Insider info
    insider_name: str = ""
    insider_title: str = ""
    insider_type: InsiderType = InsiderType.OTHER
    
    # Transaction details
    transaction_type: TransactionType = TransactionType.BUY
    transaction_date: Optional[date] = None
    shares: int = 0
    price: float = 0.0
    value: float = 0.0
    
    # Post-transaction ownership
    shares_owned: int = 0
    ownership_change_pct: float = 0.0
    
    # Filing info
    filing_date: Optional[date] = None
    form_type: FilingType = FilingType.FORM_4
    sec_url: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def is_buy(self) -> bool:
        """Check if transaction is a buy."""
        return self.transaction_type == TransactionType.BUY
    
    @property
    def is_sell(self) -> bool:
        """Check if transaction is a sell."""
        return self.transaction_type == TransactionType.SELL
    
    @property
    def is_bullish(self) -> bool:
        """Check if transaction is bullish signal."""
        return self.transaction_type in BULLISH_TRANSACTIONS
    
    @property
    def is_significant(self) -> bool:
        """Check if transaction is significant (>$100K)."""
        return self.value >= 100_000


@dataclass
class InsiderSummary:
    """Summary of insider activity for a symbol."""
    symbol: str = ""
    company_name: str = ""
    
    # Counts
    total_transactions: int = 0
    buy_count: int = 0
    sell_count: int = 0
    
    # Values
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    net_value: float = 0.0  # buys - sells
    
    # Insiders
    unique_insiders: int = 0
    unique_buyers: int = 0
    
    # Time range
    first_transaction: Optional[date] = None
    last_transaction: Optional[date] = None
    
    @property
    def buy_sell_ratio(self) -> float:
        """Calculate buy/sell ratio."""
        if self.sell_count == 0:
            return float('inf') if self.buy_count > 0 else 0
        return self.buy_count / self.sell_count


# =============================================================================
# Cluster Buying
# =============================================================================

@dataclass
class InsiderCluster:
    """A cluster of insider buying activity."""
    cluster_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Time window
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Participants
    insider_count: int = 0
    insiders: list[str] = field(default_factory=list)
    transactions: list[InsiderTransaction] = field(default_factory=list)
    
    # Totals
    total_shares: int = 0
    total_value: float = 0.0
    avg_price: float = 0.0
    
    # Scoring
    cluster_score: float = 0.0  # 0-100
    signal_strength: SignalStrength = SignalStrength.MODERATE
    
    # Detection
    detected_at: datetime = field(default_factory=_utc_now)
    
    @property
    def days_span(self) -> int:
        """Calculate days between first and last transaction."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0


# =============================================================================
# Institutional Holdings
# =============================================================================

@dataclass
class InstitutionalHolding:
    """Institutional holding from 13F filing."""
    holding_id: str = field(default_factory=_new_id)
    
    # Institution info
    institution_name: str = ""
    institution_cik: str = ""
    institution_type: InstitutionType = InstitutionType.OTHER
    
    # Position
    symbol: str = ""
    company_name: str = ""
    shares: int = 0
    value: float = 0.0
    portfolio_pct: float = 0.0
    
    # Changes from previous quarter
    shares_change: int = 0
    shares_change_pct: float = 0.0
    value_change: float = 0.0
    is_new_position: bool = False
    is_sold_out: bool = False
    
    # Filing info
    report_date: Optional[date] = None
    filing_date: Optional[date] = None
    
    @property
    def is_increase(self) -> bool:
        """Check if position increased."""
        return self.shares_change > 0
    
    @property
    def is_decrease(self) -> bool:
        """Check if position decreased."""
        return self.shares_change < 0


@dataclass
class InstitutionalSummary:
    """Summary of institutional ownership for a symbol."""
    symbol: str = ""
    
    # Ownership
    total_institutions: int = 0
    total_shares: int = 0
    total_value: float = 0.0
    institutional_pct: float = 0.0  # % of float
    
    # Changes
    new_positions: int = 0
    increased_positions: int = 0
    decreased_positions: int = 0
    sold_out: int = 0
    
    # Top holders
    top_holders: list[str] = field(default_factory=list)


# =============================================================================
# Insider Profiles
# =============================================================================

@dataclass
class InsiderProfile:
    """Profile of an individual insider."""
    insider_id: str = field(default_factory=_new_id)
    name: str = ""
    
    # Current affiliations
    companies: list[str] = field(default_factory=list)
    titles: dict[str, str] = field(default_factory=dict)  # symbol -> title
    
    # Trading history
    total_transactions: int = 0
    total_buys: int = 0
    total_sells: int = 0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    
    # Recent activity
    last_transaction_date: Optional[date] = None
    recent_transactions: list[InsiderTransaction] = field(default_factory=list)
    
    # Performance (optional tracking)
    avg_return_after_buy: Optional[float] = None
    avg_return_after_sell: Optional[float] = None
    success_rate: Optional[float] = None
    
    @property
    def net_value(self) -> float:
        """Net buy - sell value."""
        return self.total_buy_value - self.total_sell_value


# =============================================================================
# Signals & Alerts
# =============================================================================

@dataclass
class InsiderSignal:
    """Generated insider trading signal."""
    signal_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Signal info
    signal_type: str = ""  # large_buy, cluster, ceo_buy, etc.
    signal_strength: SignalStrength = SignalStrength.MODERATE
    
    # Details
    description: str = ""
    insiders_involved: list[str] = field(default_factory=list)
    total_value: float = 0.0
    
    # Related data
    transactions: list[InsiderTransaction] = field(default_factory=list)
    cluster: Optional[InsiderCluster] = None
    
    # Timing
    signal_date: Optional[date] = None
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class InsiderAlert:
    """Alert configuration for insider activity."""
    alert_id: str = field(default_factory=_new_id)
    name: str = ""
    
    # Criteria
    min_value: float = 100_000
    transaction_types: list[TransactionType] = field(default_factory=lambda: [TransactionType.BUY])
    insider_types: list[InsiderType] = field(default_factory=list)
    
    # Filters
    symbols: list[str] = field(default_factory=list)  # Empty = all
    sectors: list[str] = field(default_factory=list)
    
    # Settings
    require_cluster: bool = False
    min_insiders: int = 1
    
    # Status
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)
