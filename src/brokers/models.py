"""Broker Integration Data Models.

Dataclasses for accounts, positions, orders, and transactions.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Optional
import uuid

from src.brokers.config import (
    BrokerType,
    AccountType,
    AccountStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    AssetType,
    ConnectionStatus,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# =============================================================================
# Account Models
# =============================================================================

@dataclass
class BrokerAccount:
    """Brokerage account information."""
    account_id: str
    broker: BrokerType
    account_type: AccountType = AccountType.INDIVIDUAL
    account_name: str = ""
    status: AccountStatus = AccountStatus.ACTIVE
    
    # Capabilities
    can_trade_stocks: bool = True
    can_trade_options: bool = False
    can_trade_margin: bool = False
    can_short: bool = False
    can_trade_crypto: bool = False
    
    # Pattern day trader
    is_pdt: bool = False
    pdt_day_trades_remaining: int = 3
    
    # Metadata
    currency: str = "USD"
    opened_date: Optional[date] = None
    last_sync: datetime = field(default_factory=_utc_now)


@dataclass
class AccountBalances:
    """Account balance information."""
    account_id: str
    currency: str = "USD"
    
    # Cash
    cash: float = 0.0
    cash_available: float = 0.0
    cash_withdrawable: float = 0.0
    unsettled_cash: float = 0.0
    
    # Buying power
    buying_power: float = 0.0
    day_trading_buying_power: float = 0.0
    non_marginable_buying_power: float = 0.0
    
    # Margin (if applicable)
    margin_balance: float = 0.0
    margin_buying_power: float = 0.0
    margin_maintenance: float = 0.0
    margin_equity: float = 0.0
    
    # Portfolio value
    total_value: float = 0.0
    market_value: float = 0.0
    long_market_value: float = 0.0
    short_market_value: float = 0.0
    
    # P&L
    day_pnl: float = 0.0
    day_pnl_pct: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    
    # Timestamps
    as_of: datetime = field(default_factory=_utc_now)


# =============================================================================
# Position Models
# =============================================================================

@dataclass
class Position:
    """Account position."""
    position_id: str = field(default_factory=_new_id)
    account_id: str = ""
    symbol: str = ""
    asset_type: AssetType = AssetType.STOCK
    
    # Quantity
    quantity: float = 0.0
    quantity_available: float = 0.0  # Available for selling
    
    # Prices
    average_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    
    # P&L
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    day_pnl: float = 0.0
    day_pnl_pct: float = 0.0
    
    # For options
    option_type: Optional[str] = None  # call, put
    strike: Optional[float] = None
    expiration: Optional[date] = None
    underlying_symbol: Optional[str] = None
    
    # Side
    side: str = "long"  # long, short
    
    # Timestamps
    opened_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=_utc_now)


# =============================================================================
# Order Models
# =============================================================================

@dataclass
class OrderRequest:
    """Request to place an order."""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    
    # Prices
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Time in force
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Extended hours
    extended_hours: bool = False
    
    # Trailing stop
    trail_amount: Optional[float] = None
    trail_percent: Optional[float] = None
    
    # Options specific
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration: Optional[date] = None
    
    # Client reference
    client_order_id: Optional[str] = None
    
    # Account
    account_id: Optional[str] = None


@dataclass
class OrderModify:
    """Request to modify an order."""
    quantity: Optional[float] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: Optional[TimeInForce] = None
    trail_amount: Optional[float] = None
    trail_percent: Optional[float] = None


@dataclass
class Order:
    """Order information."""
    order_id: str = field(default_factory=_new_id)
    account_id: str = ""
    client_order_id: Optional[str] = None
    
    # Order details
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Prices
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    
    # Fill info
    filled_quantity: float = 0.0
    filled_avg_price: float = 0.0
    remaining_quantity: float = 0.0
    
    # Extended hours
    extended_hours: bool = False
    
    # Timestamps
    created_at: datetime = field(default_factory=_utc_now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    
    # Fees
    commission: float = 0.0
    fees: float = 0.0


@dataclass
class OrderResult:
    """Result of an order operation."""
    success: bool
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    message: str = ""
    
    # Fill info (if filled)
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    
    # Timestamps
    submitted_at: datetime = field(default_factory=_utc_now)
    filled_at: Optional[datetime] = None
    
    # Error details
    error_code: Optional[str] = None
    error_details: Optional[dict] = None


# =============================================================================
# Transaction Models
# =============================================================================

@dataclass
class Transaction:
    """Account transaction."""
    transaction_id: str = field(default_factory=_new_id)
    account_id: str = ""
    
    # Type
    transaction_type: str = ""  # trade, dividend, interest, fee, transfer, etc.
    
    # Details
    symbol: Optional[str] = None
    description: str = ""
    
    # Amounts
    amount: float = 0.0
    quantity: Optional[float] = None
    price: Optional[float] = None
    commission: float = 0.0
    fees: float = 0.0
    
    # Settlement
    trade_date: date = field(default_factory=date.today)
    settlement_date: Optional[date] = None
    
    # Reference
    order_id: Optional[str] = None


# =============================================================================
# Connection Models
# =============================================================================

@dataclass
class BrokerConnection:
    """Broker connection state."""
    connection_id: str = field(default_factory=_new_id)
    broker: BrokerType = BrokerType.ALPACA
    
    # Status
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    
    # Accounts
    accounts: list[str] = field(default_factory=list)
    primary_account: Optional[str] = None
    
    # Auth state
    is_authenticated: bool = False
    token_expiry: Optional[datetime] = None
    
    # Timestamps
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Error info
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None


# =============================================================================
# Quote Models
# =============================================================================

@dataclass
class Quote:
    """Stock quote."""
    symbol: str
    
    # Prices
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    
    # Sizes
    bid_size: int = 0
    ask_size: int = 0
    last_size: int = 0
    
    # Volume
    volume: int = 0
    
    # Day range
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    prev_close: float = 0.0
    
    # Change
    change: float = 0.0
    change_pct: float = 0.0
    
    # Timestamp
    timestamp: datetime = field(default_factory=_utc_now)
    
    @property
    def mid(self) -> float:
        """Mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last
    
    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def spread_pct(self) -> float:
        """Spread as percentage of mid."""
        if self.mid > 0:
            return self.spread / self.mid * 100
        return 0.0
