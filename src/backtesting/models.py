"""Backtesting Data Models.

Core data structures for the backtesting engine including
bars, orders, fills, positions, and results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import numpy as np
import pandas as pd


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class BarData:
    """Single bar of market data."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    adj_close: Optional[float] = None

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3


@dataclass
class MarketEvent:
    """Market data event for event-driven processing."""

    timestamp: datetime
    bars: dict[str, BarData]  # symbol -> bar

    def get_bar(self, symbol: str) -> Optional[BarData]:
        return self.bars.get(symbol)


@dataclass
class Signal:
    """Trading signal from strategy."""

    symbol: str
    timestamp: datetime
    side: OrderSide
    target_weight: Optional[float] = None  # Target portfolio weight
    target_shares: Optional[int] = None  # Target number of shares
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    reason: str = ""
    priority: int = 0


@dataclass
class Order:
    """Order to be executed."""

    order_id: str
    symbol: str
    side: OrderSide
    qty: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    filled_qty: int = 0
    avg_fill_price: float = 0.0

    @property
    def remaining_qty(self) -> int:
        return self.qty - self.filled_qty


@dataclass
class Fill:
    """Order fill/execution."""

    order_id: str
    symbol: str
    side: OrderSide
    qty: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    slippage: float = 0.0
    fees: float = 0.0

    @property
    def notional(self) -> float:
        return self.qty * self.price

    @property
    def total_cost(self) -> float:
        return self.commission + self.slippage + self.fees


@dataclass
class Position:
    """Portfolio position."""

    symbol: str
    qty: int
    avg_cost: float
    current_price: float = 0.0
    sector: str = ""
    beta: float = 1.0

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
        return (self.current_price / self.avg_cost - 1) if self.avg_cost > 0 else 0


@dataclass
class Trade:
    """Completed round-trip trade."""

    symbol: str
    entry_date: datetime
    exit_date: datetime
    side: OrderSide
    entry_price: float
    exit_price: float
    qty: int
    pnl: float
    pnl_pct: float
    hold_days: int
    entry_reason: str = ""
    exit_reason: str = ""
    sector: str = ""
    factor_signal: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "qty": self.qty,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "hold_days": self.hold_days,
            "sector": self.sector,
        }


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio state."""

    timestamp: datetime
    equity: float
    cash: float
    positions_value: float
    n_positions: int
    drawdown: float = 0.0
    peak_equity: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "equity": self.equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "n_positions": self.n_positions,
            "drawdown": self.drawdown,
        }


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics."""

    # Returns
    total_return: float = 0.0
    cagr: float = 0.0
    benchmark_return: float = 0.0
    benchmark_cagr: float = 0.0
    alpha: float = 0.0

    # Risk
    volatility: float = 0.0
    downside_volatility: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    avg_drawdown_duration: int = 0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0

    # Trading
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_hold_days: float = 0.0

    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    total_fees: float = 0.0
    total_costs: float = 0.0
    turnover: float = 0.0

    # Monthly stats
    best_month: float = 0.0
    worst_month: float = 0.0
    positive_months: int = 0
    negative_months: int = 0

    def to_dict(self) -> dict:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "benchmark_return": self.benchmark_return,
            "alpha": self.alpha,
            "volatility": self.volatility,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_costs": self.total_costs,
        }


@dataclass
class BacktestResult:
    """Complete backtest result."""

    config: dict = field(default_factory=dict)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    benchmark_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    trades: list[Trade] = field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = field(default_factory=list)
    monthly_returns: pd.Series = field(default_factory=pd.Series)
    daily_returns: pd.Series = field(default_factory=pd.Series)

    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trades])

    def get_equity_df(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        return pd.DataFrame({
            "equity": self.equity_curve,
            "benchmark": self.benchmark_curve,
            "drawdown": self.drawdown_curve,
        })


@dataclass
class WalkForwardWindow:
    """Single walk-forward optimization window."""

    window_id: int
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    best_params: dict = field(default_factory=dict)
    in_sample_sharpe: float = 0.0
    out_of_sample_sharpe: float = 0.0
    out_of_sample_result: Optional[BacktestResult] = None


@dataclass
class WalkForwardResult:
    """Complete walk-forward optimization result."""

    windows: list[WalkForwardWindow] = field(default_factory=list)
    combined_equity_curve: pd.Series = field(default_factory=pd.Series)
    in_sample_sharpe_avg: float = 0.0
    out_of_sample_sharpe: float = 0.0
    efficiency_ratio: float = 0.0
    param_stability: dict = field(default_factory=dict)
    combined_metrics: BacktestMetrics = field(default_factory=BacktestMetrics)


@dataclass
class MonteCarloResult:
    """Monte Carlo analysis result."""

    n_simulations: int = 0

    # Sharpe distribution
    sharpe_mean: float = 0.0
    sharpe_std: float = 0.0
    sharpe_95ci: tuple = (0.0, 0.0)

    # CAGR distribution
    cagr_mean: float = 0.0
    cagr_std: float = 0.0
    cagr_95ci: tuple = (0.0, 0.0)

    # Drawdown distribution
    max_dd_mean: float = 0.0
    max_dd_std: float = 0.0
    max_dd_95ci: tuple = (0.0, 0.0)

    # Probabilities
    pct_profitable: float = 0.0
    pct_beats_benchmark: float = 0.0

    # Significance
    is_significant: bool = False
    p_value: float = 1.0

    # Distributions for plotting
    sharpe_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    cagr_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    dd_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
