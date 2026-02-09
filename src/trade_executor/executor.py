"""Autonomous trade execution engine.

Consumes signals from the EMA Cloud Signal Engine (PRD-134), manages
the full trade lifecycle: validate → size → route → monitor → exit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from enum import Enum
from typing import Literal, Optional

from src.ema_signals.detector import TradeSignal

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class InstrumentMode(str, Enum):
    """User-selectable instrument mode for the bot."""

    OPTIONS = "options"
    LEVERAGED_ETF = "leveraged_etf"
    BOTH = "both"


@dataclass
class ExecutorConfig:
    """Configuration for the trade executor."""

    # Instrument mode
    instrument_mode: InstrumentMode = InstrumentMode.BOTH

    # Risk parameters (Aggressive)
    max_risk_per_trade: float = 0.05
    max_concurrent_positions: int = 10
    daily_loss_limit: float = 0.10
    max_single_stock_exposure: float = 0.15
    max_sector_exposure: float = 0.30
    min_account_equity: float = 25_000.0

    # Execution
    primary_broker: str = "alpaca"
    fallback_broker: str = "ibkr"
    slippage_buffer: float = 0.001
    default_time_in_force: str = "day"

    # Entry
    high_conviction_order_type: str = "market"
    medium_conviction_order_type: str = "limit"
    scale_in_enabled: bool = True
    scale_in_initial_pct: float = 0.5

    # Exit
    reward_to_risk_target: float = 2.0
    time_stop_minutes: int = 120
    eod_close_time: str = "15:55"
    trailing_stop_cloud: str = "pullback"

    # Leveraged ETF settings
    max_etf_hold_days_3x: int = 5
    max_etf_hold_days_2x: int = 10
    prefer_3x_for_day_trades: bool = True
    min_etf_daily_volume: float = 10_000_000
    etf_sector_mapping: bool = True

    # Kill switch
    consecutive_loss_threshold: int = 3
    consecutive_loss_pct: float = 0.03
    api_timeout_seconds: int = 60


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AccountState:
    """Current state of the trading account."""

    equity: float
    cash: float
    buying_power: float
    open_positions: list[Position] = field(default_factory=list)
    daily_pnl: float = 0.0
    daily_trades: int = 0
    is_pdt_compliant: bool = True
    starting_equity: float = 0.0

    @property
    def daily_pnl_pct(self) -> float:
        if self.starting_equity <= 0:
            return 0.0
        return self.daily_pnl / self.starting_equity

    @property
    def exposure_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        total = sum(abs(p.shares * p.current_price) for p in self.open_positions)
        return total / self.equity


@dataclass
class Position:
    """An open trading position."""

    ticker: str
    direction: Literal["long", "short"]
    entry_price: float
    current_price: float
    shares: int
    stop_loss: float
    target_price: Optional[float]
    entry_time: datetime
    signal_id: str = ""
    trade_type: Literal["day", "swing", "scalp"] = "day"
    instrument_type: Literal["stock", "option", "leveraged_etf"] = "stock"
    leverage: float = 1.0

    @property
    def unrealized_pnl(self) -> float:
        mult = 1 if self.direction == "long" else -1
        return mult * (self.current_price - self.entry_price) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        mult = 1 if self.direction == "long" else -1
        return mult * (self.current_price - self.entry_price) / self.entry_price

    @property
    def hold_time(self) -> timedelta:
        return datetime.now(timezone.utc) - self.entry_time

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": round(self.entry_price, 4),
            "current_price": round(self.current_price, 4),
            "shares": self.shares,
            "stop_loss": round(self.stop_loss, 4),
            "target_price": round(self.target_price, 4) if self.target_price else None,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 4),
            "trade_type": self.trade_type,
            "instrument_type": self.instrument_type,
            "leverage": self.leverage,
        }


@dataclass
class PositionSize:
    """Calculated position size for a trade."""

    shares: int
    notional_value: float
    risk_amount: float
    conviction_multiplier: float
    order_type: str


@dataclass
class ExecutionResult:
    """Result of attempting to execute a trade signal."""

    success: bool
    signal: TradeSignal
    position: Optional[Position] = None
    order_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    risk_decision: Optional[object] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "ticker": self.signal.ticker,
            "direction": self.signal.direction,
            "conviction": self.signal.conviction,
            "order_id": self.order_id,
            "rejection_reason": self.rejection_reason,
        }


# ═══════════════════════════════════════════════════════════════════════
# Position Sizer
# ═══════════════════════════════════════════════════════════════════════


class PositionSizer:
    """Calculate position size based on conviction and risk parameters."""

    def __init__(self, config: ExecutorConfig):
        self.config = config

    def calculate(
        self, signal: TradeSignal, account: AccountState
    ) -> PositionSize:
        """Size a position based on risk-per-trade and conviction.

        Formula:
        1. risk_amount = equity * max_risk_per_trade (5%)
        2. stop_distance = abs(entry - stop) / entry
        3. raw_shares = risk_amount / (entry * stop_distance)
        4. conviction_multiplier: high=1.0, medium=0.5
        5. final = min(raw * multiplier, max_position_shares)
        """
        risk_amount = account.equity * self.config.max_risk_per_trade

        stop_distance = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        if stop_distance < 0.001:
            stop_distance = 0.02  # Default 2% if stop too tight

        raw_shares = risk_amount / (signal.entry_price * stop_distance)

        if signal.conviction >= 75:
            conv_mult = 1.0
            order_type = self.config.high_conviction_order_type
        else:
            conv_mult = 0.5
            order_type = self.config.medium_conviction_order_type

        if self.config.scale_in_enabled and order_type == "limit":
            conv_mult *= self.config.scale_in_initial_pct

        final_shares = int(raw_shares * conv_mult)

        # Cap at max single-stock exposure
        max_notional = account.equity * self.config.max_single_stock_exposure
        max_shares = int(max_notional / signal.entry_price) if signal.entry_price > 0 else 0
        final_shares = min(final_shares, max_shares)
        final_shares = max(final_shares, 1)  # At least 1 share

        notional = final_shares * signal.entry_price

        return PositionSize(
            shares=final_shares,
            notional_value=round(notional, 2),
            risk_amount=round(risk_amount, 2),
            conviction_multiplier=conv_mult,
            order_type=order_type,
        )


# ═══════════════════════════════════════════════════════════════════════
# Kill Switch
# ═══════════════════════════════════════════════════════════════════════


class KillSwitch:
    """Emergency stop for the trading bot."""

    def __init__(self, config: ExecutorConfig):
        self.config = config
        self.active = False
        self.reason: Optional[str] = None
        self._consecutive_losses: list[float] = []

    def check(self, account: AccountState) -> bool:
        """Returns True if bot should halt all trading."""
        if self.active:
            return True

        # 1. Daily loss exceeds limit
        if account.starting_equity > 0:
            daily_loss_pct = abs(account.daily_pnl) / account.starting_equity
            if account.daily_pnl < 0 and daily_loss_pct >= self.config.daily_loss_limit:
                self.activate(f"Daily loss limit hit: {daily_loss_pct:.1%}")
                return True

        # 2. Account equity below PDT minimum
        if account.equity < self.config.min_account_equity:
            self.activate(f"Equity ${account.equity:,.0f} below ${self.config.min_account_equity:,.0f}")
            return True

        # 3. Consecutive losses
        if len(self._consecutive_losses) >= self.config.consecutive_loss_threshold:
            recent = self._consecutive_losses[-self.config.consecutive_loss_threshold:]
            if all(loss >= self.config.consecutive_loss_pct for loss in recent):
                self.activate(
                    f"{self.config.consecutive_loss_threshold} consecutive losses >"
                    f" {self.config.consecutive_loss_pct:.0%}"
                )
                return True

        return False

    def record_trade_result(self, pnl_pct: float) -> None:
        """Track consecutive losses for kill switch trigger."""
        if pnl_pct < 0:
            self._consecutive_losses.append(abs(pnl_pct))
        else:
            self._consecutive_losses.clear()

    def activate(self, reason: str) -> None:
        """Halt all trading."""
        self.active = True
        self.reason = reason
        logger.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate(self) -> None:
        """Re-enable trading (manual only)."""
        self.active = False
        self.reason = None
        self._consecutive_losses.clear()
        logger.info("Kill switch deactivated")


# ═══════════════════════════════════════════════════════════════════════
# Trade Executor
# ═══════════════════════════════════════════════════════════════════════


class TradeExecutor:
    """Main execution engine — consumes signals, manages lifecycle."""

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self.sizer = PositionSizer(self.config)
        self.kill_switch = KillSwitch(self.config)
        self.positions: list[Position] = []
        self.signal_queue: list[TradeSignal] = []
        self.execution_history: list[ExecutionResult] = []

    def process_signal(self, signal: TradeSignal, account: AccountState) -> ExecutionResult:
        """Full pipeline: validate → size → route → confirm.

        This is a synchronous version for simplicity. In production,
        broker calls would be async via the OrderRouter.
        """
        from src.trade_executor.risk_gate import RiskGate

        # Kill switch check
        if self.kill_switch.check(account):
            return ExecutionResult(
                success=False,
                signal=signal,
                rejection_reason=f"Kill switch active: {self.kill_switch.reason}",
            )

        # Risk gate validation
        risk_gate = RiskGate(self.config)
        decision = risk_gate.validate(signal, account)
        if not decision.approved:
            return ExecutionResult(
                success=False,
                signal=signal,
                rejection_reason=decision.reason,
                risk_decision=decision,
            )

        # Position sizing
        size = self.sizer.calculate(signal, account)

        # Create position
        position = Position(
            ticker=signal.ticker,
            direction=signal.direction,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            shares=size.shares,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            entry_time=datetime.now(timezone.utc),
            signal_id=str(id(signal)),
            trade_type=self._classify_trade_type(signal.timeframe),
        )

        self.positions.append(position)
        result = ExecutionResult(
            success=True,
            signal=signal,
            position=position,
            order_id=f"ORD-{id(signal)}",
        )
        self.execution_history.append(result)
        return result

    def close_position(self, ticker: str, exit_reason: str) -> Optional[Position]:
        """Close a position by ticker."""
        for i, pos in enumerate(self.positions):
            if pos.ticker == ticker:
                closed = self.positions.pop(i)
                pnl_pct = closed.unrealized_pnl_pct
                self.kill_switch.record_trade_result(pnl_pct)
                logger.info(
                    "Closed %s %s: P&L %.2f%% (%s)",
                    closed.direction, closed.ticker, pnl_pct * 100, exit_reason,
                )
                return closed
        return None

    def get_account_snapshot(self, equity: float, cash: float) -> AccountState:
        """Build an AccountState from current executor state."""
        return AccountState(
            equity=equity,
            cash=cash,
            buying_power=cash,
            open_positions=list(self.positions),
            daily_pnl=sum(p.unrealized_pnl for p in self.positions),
            daily_trades=len(self.execution_history),
            starting_equity=equity,
        )

    @staticmethod
    def _classify_trade_type(timeframe: str) -> Literal["day", "swing", "scalp"]:
        if timeframe in ("1m", "5m"):
            return "scalp"
        elif timeframe in ("10m",):
            return "day"
        return "swing"
