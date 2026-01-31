"""Trading Bots Data Models.

Dataclasses for bots, executions, orders, and performance tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Optional
import uuid

from src.bots.config import (
    BotType,
    BotStatus,
    ExecutionStatus,
    TradeSide,
    OrderType,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# =============================================================================
# Core Models
# =============================================================================

@dataclass
class BotOrder:
    """Order placed by a bot."""
    order_id: str = field(default_factory=_new_id)
    execution_id: str = ""
    bot_id: str = ""
    
    # Order details
    symbol: str = ""
    side: TradeSide = TradeSide.BUY
    quantity: float = 0.0
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    
    # Fill details
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    commission: float = 0.0
    
    # Status
    status: str = "pending"  # pending, filled, partial, cancelled, rejected
    error_message: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=_utc_now)
    filled_at: Optional[datetime] = None
    
    @property
    def is_filled(self) -> bool:
        return self.status == "filled"
    
    @property
    def fill_value(self) -> float:
        if self.filled_price:
            return self.filled_quantity * self.filled_price
        return 0.0


@dataclass
class BotExecution:
    """Single execution of a bot."""
    execution_id: str = field(default_factory=_new_id)
    bot_id: str = ""
    bot_name: str = ""
    bot_type: BotType = BotType.DCA
    
    # Timing
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Status
    status: ExecutionStatus = ExecutionStatus.PENDING
    trigger_reason: str = ""  # 'scheduled', 'signal', 'manual'
    
    # Results
    orders: list[BotOrder] = field(default_factory=list)
    total_value: float = 0.0
    realized_pnl: float = 0.0
    
    # Errors
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def orders_placed(self) -> int:
        return len(self.orders)
    
    @property
    def orders_filled(self) -> int:
        return len([o for o in self.orders if o.is_filled])
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def add_order(self, order: BotOrder) -> None:
        order.execution_id = self.execution_id
        order.bot_id = self.bot_id
        self.orders.append(order)
        self.total_value += order.fill_value


@dataclass
class BotPerformance:
    """Bot performance metrics."""
    bot_id: str = ""
    period_start: date = field(default_factory=date.today)
    period_end: date = field(default_factory=date.today)
    
    # Investment
    total_invested: float = 0.0
    current_value: float = 0.0
    cash_balance: float = 0.0
    
    # P&L
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    dividends_received: float = 0.0
    
    # Activity
    num_executions: int = 0
    num_trades: int = 0
    num_successful: int = 0
    num_failed: int = 0
    
    # Risk metrics
    max_drawdown_pct: float = 0.0
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def total_return_pct(self) -> float:
        if self.total_invested > 0:
            return (self.total_pnl / self.total_invested) * 100
        return 0.0
    
    @property
    def success_rate(self) -> float:
        total = self.num_successful + self.num_failed
        if total > 0:
            return (self.num_successful / total) * 100
        return 0.0


@dataclass
class BotPosition:
    """Position held by a bot."""
    bot_id: str = ""
    symbol: str = ""
    quantity: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    
    # Tracking
    first_purchase: datetime = field(default_factory=_utc_now)
    last_updated: datetime = field(default_factory=_utc_now)
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis > 0:
            return (self.unrealized_pnl / self.cost_basis) * 100
        return 0.0


@dataclass
class Signal:
    """Trading signal generated by a bot."""
    signal_id: str = field(default_factory=_new_id)
    bot_id: str = ""
    symbol: str = ""
    
    # Signal details
    signal_type: str = ""
    side: TradeSide = TradeSide.BUY
    strength: float = 0.0  # 0 to 1
    
    # Context
    indicator_value: float = 0.0
    threshold: float = 0.0
    price_at_signal: float = 0.0
    
    # Status
    is_confirmed: bool = False
    is_executed: bool = False
    execution_id: Optional[str] = None
    
    created_at: datetime = field(default_factory=_utc_now)
    expires_at: Optional[datetime] = None


@dataclass
class GridLevel:
    """Grid level for grid trading bot."""
    level_id: str = field(default_factory=_new_id)
    bot_id: str = ""
    
    # Level definition
    price: float = 0.0
    level_index: int = 0
    
    # Orders
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    
    # Status
    has_position: bool = False
    quantity: float = 0.0
    entry_price: Optional[float] = None
    
    # Tracking
    times_bought: int = 0
    times_sold: int = 0
    total_profit: float = 0.0


@dataclass
class ScheduledRun:
    """Scheduled bot run."""
    schedule_id: str = field(default_factory=_new_id)
    bot_id: str = ""
    bot_name: str = ""
    
    scheduled_time: datetime = field(default_factory=_utc_now)
    status: str = "pending"  # pending, running, completed, missed
    
    execution_id: Optional[str] = None
    
    created_at: datetime = field(default_factory=_utc_now)


@dataclass 
class BotSummary:
    """Summary of a bot for display."""
    bot_id: str = ""
    name: str = ""
    bot_type: BotType = BotType.DCA
    status: BotStatus = BotStatus.ACTIVE
    
    # Activity
    symbols: list[str] = field(default_factory=list)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    total_executions: int = 0
    
    # Performance
    total_invested: float = 0.0
    current_value: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    
    created_at: datetime = field(default_factory=_utc_now)
