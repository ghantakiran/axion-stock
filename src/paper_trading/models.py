"""Paper Trading Data Models.

Session, trade, snapshot, and performance result dataclasses.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.paper_trading.config import (
    SessionStatus,
    StrategyType,
    PerformancePeriod,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class SessionTrade:
    """Single trade within a paper trading session."""
    trade_id: str = field(default_factory=_new_id)
    session_id: str = ""
    symbol: str = ""
    side: str = "buy"  # buy or sell
    qty: int = 0
    price: float = 0.0
    notional: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    pnl: Optional[float] = None  # Set on closing trades
    pnl_pct: Optional[float] = None
    reason: str = ""  # signal, rebalance, stop_loss, take_profit, manual
    timestamp: datetime = field(default_factory=_utc_now)

    @property
    def total_cost(self) -> float:
        return self.commission + self.slippage


@dataclass
class PortfolioPosition:
    """Position within a paper trading session."""
    symbol: str = ""
    qty: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    sector: str = ""

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.qty * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        return (self.current_price / self.avg_cost - 1) if self.avg_cost > 0 else 0.0

    @property
    def weight(self) -> float:
        """Weight placeholder - set externally based on portfolio equity."""
        return 0.0


@dataclass
class SessionSnapshot:
    """Point-in-time portfolio state within a session."""
    snapshot_id: str = field(default_factory=_new_id)
    session_id: str = ""
    timestamp: datetime = field(default_factory=_utc_now)
    equity: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    n_positions: int = 0
    drawdown: float = 0.0
    peak_equity: float = 0.0
    daily_return: float = 0.0


@dataclass
class SessionMetrics:
    """Comprehensive performance metrics for a session."""
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0

    # Risk
    volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trading
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0

    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0
    turnover: float = 0.0

    # Session info
    total_days: int = 0
    start_equity: float = 0.0
    end_equity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "benchmark_return": self.benchmark_return,
            "active_return": self.active_return,
            "volatility": self.volatility,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_costs": self.total_costs,
        }


@dataclass
class PaperSession:
    """Paper trading session with full lifecycle."""
    session_id: str = field(default_factory=_new_id)
    name: str = ""
    status: SessionStatus = SessionStatus.CREATED
    strategy_type: StrategyType = StrategyType.MANUAL
    initial_capital: float = 100_000.0
    symbols: list[str] = field(default_factory=list)
    benchmark: str = "SPY"

    # State
    cash: float = 0.0
    positions: dict[str, PortfolioPosition] = field(default_factory=dict)
    peak_equity: float = 0.0

    # History
    trades: list[SessionTrade] = field(default_factory=list)
    snapshots: list[SessionSnapshot] = field(default_factory=list)

    # Metrics
    metrics: SessionMetrics = field(default_factory=SessionMetrics)

    # Timestamps
    created_at: datetime = field(default_factory=_utc_now)
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def positions_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def equity(self) -> float:
        return self.cash + self.positions_value

    @property
    def drawdown(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.equity - self.peak_equity) / self.peak_equity

    @property
    def total_return(self) -> float:
        if self.initial_capital <= 0:
            return 0.0
        return (self.equity - self.initial_capital) / self.initial_capital

    @property
    def is_active(self) -> bool:
        return self.status in (SessionStatus.RUNNING, SessionStatus.PAUSED)

    def start(self) -> None:
        """Start the session."""
        if self.status != SessionStatus.CREATED:
            return
        self.status = SessionStatus.RUNNING
        self.cash = self.initial_capital
        self.peak_equity = self.initial_capital
        self.started_at = _utc_now()

    def pause(self) -> None:
        """Pause the session."""
        if self.status != SessionStatus.RUNNING:
            return
        self.status = SessionStatus.PAUSED
        self.paused_at = _utc_now()

    def resume(self) -> None:
        """Resume a paused session."""
        if self.status != SessionStatus.PAUSED:
            return
        self.status = SessionStatus.RUNNING
        self.paused_at = None

    def complete(self) -> None:
        """Complete (stop) the session."""
        if self.status not in (SessionStatus.RUNNING, SessionStatus.PAUSED):
            return
        self.status = SessionStatus.COMPLETED
        self.completed_at = _utc_now()

    def cancel(self) -> None:
        """Cancel the session."""
        if self.status == SessionStatus.COMPLETED:
            return
        self.status = SessionStatus.CANCELLED
        self.completed_at = _utc_now()


@dataclass
class SessionComparison:
    """Comparison of multiple paper trading sessions."""
    sessions: list[str] = field(default_factory=list)  # session_ids
    metrics_table: list[dict] = field(default_factory=list)
    winner_by_metric: dict[str, str] = field(default_factory=dict)
    ranking: list[dict] = field(default_factory=list)
