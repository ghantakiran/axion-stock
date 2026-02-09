"""Bot Pipeline Orchestrator & Robustness Layer (PRD-170).

Hardens the trading bot with:
- Thread-safe pipeline orchestrator (replaces direct executor calls)
- Persistent state management (kill switch survives restarts)
- Order fill validation (prevents ghost positions)
- Position reconciliation with broker
- Full audit trail integration (PRD-162)
- Unified risk assessment (PRD-163)
- Signal performance feedback (PRD-166)

Pipeline: Signal → KillSwitch → Recorder → UnifiedRisk → Sizer
    → Router (retry) → Validator → Position → Feedback
"""

from src.bot_pipeline.orchestrator import (
    BotOrchestrator,
    PipelineConfig,
    PipelineResult,
)
from src.bot_pipeline.state_manager import PersistentStateManager
from src.bot_pipeline.order_validator import FillValidation, OrderValidator
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
    # Order validation
    "OrderValidator",
    "FillValidation",
    # Position reconciliation
    "PositionReconciler",
    "PositionMismatch",
    "ReconciliationReport",
]
