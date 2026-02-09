"""Bot Pipeline Orchestrator & Robustness Layer (PRD-170 + PRD-171).

Hardens the trading bot with:
- Thread-safe pipeline orchestrator (replaces direct executor calls)
- Persistent state management (kill switch survives restarts)
- Signal freshness + deduplication guard (PRD-171)
- Order fill validation (prevents ghost positions)
- Position reconciliation with broker
- Active position lifecycle management (PRD-171)
- Full audit trail integration (PRD-162)
- Unified risk assessment (PRD-163)
- Instrument routing & ETF sizing (PRD-171)
- Trade journal integration (PRD-171)
- Daily loss auto-kill (PRD-171)
- Signal performance feedback (PRD-166)

Pipeline: Signal → KillSwitch → SignalGuard → Recorder → UnifiedRisk
    → InstrumentRouter → Sizer → Router (retry) → Validator
    → Position → Journal → Feedback → DailyLossCheck
"""

from src.bot_pipeline.orchestrator import (
    BotOrchestrator,
    PipelineConfig,
    PipelineResult,
)
from src.bot_pipeline.state_manager import PersistentStateManager
from src.bot_pipeline.order_validator import FillValidation, OrderValidator
from src.bot_pipeline.signal_guard import SignalGuard
from src.bot_pipeline.lifecycle_manager import LifecycleManager, PortfolioSnapshot
from src.bot_pipeline.position_reconciler import (
    PositionMismatch,
    PositionReconciler,
    ReconciliationReport,
)

__all__ = [
    # Orchestrator
    "BotOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    # State management
    "PersistentStateManager",
    # Signal guard (PRD-171)
    "SignalGuard",
    # Lifecycle management (PRD-171)
    "LifecycleManager",
    "PortfolioSnapshot",
    # Order validation
    "OrderValidator",
    "FillValidation",
    # Position reconciliation
    "PositionReconciler",
    "PositionMismatch",
    "ReconciliationReport",
]
