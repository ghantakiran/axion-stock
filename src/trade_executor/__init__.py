"""Autonomous Trade Executor (PRD-135).

Consumes signals from the EMA Cloud Signal Engine (PRD-134) and manages
the full trade lifecycle: validate -> size -> route -> monitor -> exit.

Supports 3 instrument modes: Options, Leveraged ETFs, or Both.
"""

from src.trade_executor.executor import (
    AccountState,
    ExecutionResult,
    ExecutorConfig,
    InstrumentMode,
    KillSwitch,
    Position,
    PositionSize,
    PositionSizer,
    TradeExecutor,
)
from src.trade_executor.exit_monitor import ExitMonitor, ExitSignal
from src.trade_executor.instrument_router import (
    ETFSelection,
    InstrumentDecision,
    InstrumentRouter,
    LEVERAGED_ETF_CATALOG,
)
from src.trade_executor.etf_sizer import LeveragedETFSizer
from src.trade_executor.journal import DailySummary, TradeJournalWriter, TradeRecord
from src.trade_executor.risk_gate import RiskDecision, RiskGate
from src.trade_executor.router import Order, OrderResult, OrderRouter

__all__ = [
    # Core
    "TradeExecutor",
    "ExecutorConfig",
    "InstrumentMode",
    "AccountState",
    "Position",
    "PositionSize",
    "ExecutionResult",
    "PositionSizer",
    "KillSwitch",
    # Risk
    "RiskGate",
    "RiskDecision",
    # Routing
    "OrderRouter",
    "Order",
    "OrderResult",
    "InstrumentRouter",
    "InstrumentDecision",
    "ETFSelection",
    "LEVERAGED_ETF_CATALOG",
    # ETF Sizing
    "LeveragedETFSizer",
    # Exit
    "ExitMonitor",
    "ExitSignal",
    # Journal
    "TradeJournalWriter",
    "TradeRecord",
    "DailySummary",
]
