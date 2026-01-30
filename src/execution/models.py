"""Data models for the execution system.

Contains all the core data structures used across the execution module:
- Order-related models (OrderRequest, Order, OrderStatus, etc.)
- Position and Account models
- Trade records for journaling
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class OrderSide(Enum):
    """Order side - buy or sell."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type for execution."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    MARKET_ON_CLOSE = "market_on_close"


class OrderStatus(Enum):
    """Order lifecycle status."""
    PENDING = "pending"           # Created, not yet submitted
    SUBMITTED = "submitted"       # Sent to broker
    ACCEPTED = "accepted"         # Accepted by broker
    PARTIAL_FILL = "partial_fill" # Partially executed
    FILLED = "filled"             # Fully executed
    CANCELLED = "cancelled"       # Cancelled by user or system
    REJECTED = "rejected"         # Rejected by broker
    EXPIRED = "expired"           # Time-in-force expired
    FAILED = "failed"             # Execution failed


class OrderTimeInForce(Enum):
    """Time in force for orders."""
    DAY = "day"           # Valid for trading day only
    GTC = "gtc"           # Good till cancelled
    IOC = "ioc"           # Immediate or cancel
    FOK = "fok"           # Fill or kill
    OPG = "opg"           # Market on open
    CLS = "cls"           # Market on close


@dataclass
class OrderRequest:
    """Request to place an order."""
    symbol: str
    qty: float
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: OrderTimeInForce = OrderTimeInForce.DAY
    extended_hours: bool = False
    client_order_id: Optional[str] = None
    
    # Bracket order components
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    
    # Trailing stop
    trail_percent: Optional[float] = None
    trail_price: Optional[float] = None
    
    # Metadata
    trigger: str = "manual"  # 'manual', 'rebalance', 'signal', 'stop_loss'
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Convert string enums if needed
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)
        if isinstance(self.order_type, str):
            self.order_type = OrderType(self.order_type)
        if isinstance(self.time_in_force, str):
            self.time_in_force = OrderTimeInForce(self.time_in_force)
    
    @property
    def notional_value(self) -> Optional[float]:
        """Estimated notional value of the order."""
        if self.limit_price:
            return self.qty * self.limit_price
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "extended_hours": self.extended_hours,
            "client_order_id": self.client_order_id,
            "take_profit_price": self.take_profit_price,
            "stop_loss_price": self.stop_loss_price,
            "trail_percent": self.trail_percent,
            "trail_price": self.trail_price,
            "trigger": self.trigger,
            "notes": self.notes,
        }


@dataclass
class Order:
    """Executed or pending order with full details."""
    id: str
    client_order_id: Optional[str]
    symbol: str
    qty: float
    filled_qty: float
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_avg_price: Optional[float] = None
    time_in_force: OrderTimeInForce = OrderTimeInForce.DAY
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Execution details
    commission: float = 0.0
    slippage: float = 0.0
    
    # Metadata
    trigger: str = "manual"
    notes: Optional[str] = None
    broker: str = "unknown"
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIAL_FILL,
        ]
    
    @property
    def remaining_qty(self) -> float:
        return self.qty - self.filled_qty
    
    @property
    def fill_price(self) -> Optional[float]:
        """Alias for filled_avg_price."""
        return self.filled_avg_price
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "qty": self.qty,
            "filled_qty": self.filled_qty,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "filled_avg_price": self.filled_avg_price,
            "time_in_force": self.time_in_force.value,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "commission": self.commission,
            "slippage": self.slippage,
            "trigger": self.trigger,
            "broker": self.broker,
        }


@dataclass
class Position:
    """Current position in a security."""
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    side: str = "long"  # 'long' or 'short'
    
    # Computed at access time
    @property
    def market_value(self) -> float:
        return abs(self.qty) * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return abs(self.qty) * self.avg_entry_price
    
    @property
    def unrealized_pnl(self) -> float:
        if self.side == "long":
            return (self.current_price - self.avg_entry_price) * self.qty
        else:
            return (self.avg_entry_price - self.current_price) * abs(self.qty)
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "side": self.side,
        }


@dataclass
class AccountInfo:
    """Brokerage account information."""
    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    
    # Margin info
    margin_used: float = 0.0
    margin_available: float = 0.0
    
    # Day trading
    day_trades_remaining: int = 3  # PDT tracking
    is_pattern_day_trader: bool = False
    
    # Account status
    trading_blocked: bool = False
    transfers_blocked: bool = False
    account_blocked: bool = False
    
    # Timestamps
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def leverage(self) -> float:
        if self.equity == 0:
            return 0.0
        return self.portfolio_value / self.equity
    
    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "buying_power": self.buying_power,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "day_trades_remaining": self.day_trades_remaining,
            "is_pattern_day_trader": self.is_pattern_day_trader,
            "leverage": self.leverage,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Trade:
    """Completed trade record for journaling."""
    id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float = 0.0
    slippage: float = 0.0
    
    # Context at time of trade
    order_type: OrderType = OrderType.MARKET
    trigger: str = "manual"
    factor_scores_at_entry: Optional[dict] = None
    regime_at_entry: Optional[str] = None
    portfolio_value_at_time: Optional[float] = None
    
    # Notes
    notes: Optional[str] = None
    
    @property
    def notional_value(self) -> float:
        return self.quantity * self.price
    
    @property
    def total_cost(self) -> float:
        """Total cost including commission and slippage."""
        return self.notional_value + self.commission + self.slippage
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "commission": self.commission,
            "slippage": self.slippage,
            "order_type": self.order_type.value,
            "trigger": self.trigger,
            "factor_scores_at_entry": self.factor_scores_at_entry,
            "regime_at_entry": self.regime_at_entry,
            "portfolio_value_at_time": self.portfolio_value_at_time,
            "notes": self.notes,
        }


@dataclass
class ExecutionResult:
    """Result of an order execution attempt."""
    success: bool
    order: Optional[Order] = None
    trades: list[Trade] = field(default_factory=list)
    error_message: Optional[str] = None
    
    # Execution metrics
    expected_price: Optional[float] = None
    actual_avg_price: Optional[float] = None
    total_slippage: float = 0.0
    total_commission: float = 0.0
    execution_time_ms: float = 0.0
    
    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points."""
        if self.expected_price and self.actual_avg_price:
            return (self.actual_avg_price - self.expected_price) / self.expected_price * 10000
        return 0.0
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "order": self.order.to_dict() if self.order else None,
            "trades": [t.to_dict() for t in self.trades],
            "error_message": self.error_message,
            "expected_price": self.expected_price,
            "actual_avg_price": self.actual_avg_price,
            "slippage_bps": self.slippage_bps,
            "total_commission": self.total_commission,
            "execution_time_ms": self.execution_time_ms,
        }
