"""Live Signal-to-Trade Pipeline (PRD-149).

Bridges signal generation (signal_fusion, social_intelligence, ema_signals)
to trade execution (multi_broker, trade_executor) with validation, risk
checks, position tracking, and execution reconciliation.

Pipeline: signal -> bridge -> validate -> risk_check -> route -> execute -> reconcile
"""

from src.trade_pipeline.bridge import (
    OrderSide,
    OrderType,
    PipelineOrder,
    SignalBridge,
    SignalType,
)
from src.trade_pipeline.executor import (
    PipelineConfig,
    PipelineExecutor,
    PipelineResult,
    PipelineStatus,
)
from src.trade_pipeline.reconciler import (
    ExecutionReconciler,
    ReconciliationRecord,
    SlippageStats,
)
from src.trade_pipeline.position_store import (
    PositionStore,
    TrackedPosition,
)

__all__ = [
    # Bridge
    "SignalType",
    "OrderSide",
    "OrderType",
    "PipelineOrder",
    "SignalBridge",
    # Executor
    "PipelineStatus",
    "PipelineResult",
    "PipelineConfig",
    "PipelineExecutor",
    # Reconciler
    "ReconciliationRecord",
    "SlippageStats",
    "ExecutionReconciler",
    # Position Store
    "TrackedPosition",
    "PositionStore",
]
