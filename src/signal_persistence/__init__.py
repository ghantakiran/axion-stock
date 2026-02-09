"""Signal Persistence & Audit Trail (PRD-162).

Persists every signal, risk decision, and execution result to enable:
- Full signal→execution→attribution audit trail
- Historical signal replay for backtesting
- Regulatory compliance (MiFID II / SEC Rule 17a-4)
- Closed-loop feedback for adaptive signal weighting

Pipeline: Signal generated → persisted → fused → risk checked → executed → attributed
"""

from src.signal_persistence.models import (
    ExecutionRecord,
    FusionRecord,
    PersistenceConfig,
    RiskDecisionRecord,
    SignalRecord,
    SignalStatus,
)
from src.signal_persistence.store import SignalStore
from src.signal_persistence.recorder import SignalRecorder
from src.signal_persistence.query import SignalQuery, SignalQueryBuilder

__all__ = [
    # Models
    "SignalRecord",
    "FusionRecord",
    "RiskDecisionRecord",
    "ExecutionRecord",
    "SignalStatus",
    "PersistenceConfig",
    # Store
    "SignalStore",
    # Recorder
    "SignalRecorder",
    # Query
    "SignalQuery",
    "SignalQueryBuilder",
]
