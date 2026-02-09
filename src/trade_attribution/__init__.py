"""Live Trade Attribution System (PRD-160).

Links executed trades to originating signals, decomposes P&L into
entry quality, market movement, exit timing, and transaction costs.
Tracks signal-type performance over rolling windows for live optimization.
"""
from src.trade_attribution.config import (
    AttributionConfig,
    DecompositionMethod,
    TimeWindow,
)
from src.trade_attribution.linker import (
    TradeSignalLinker,
    LinkedTrade,
    LinkageReport,
)
from src.trade_attribution.decomposer import (
    TradeDecomposer,
    PnLBreakdown,
    DecompositionReport,
)
from src.trade_attribution.tracker import (
    SignalPerformanceTracker,
    RollingSignalStats,
    TrackerSnapshot,
)
from src.trade_attribution.engine import (
    AttributionEngine,
    AttributionResult,
    LiveAttributionReport,
)

__all__ = [
    "AttributionConfig",
    "DecompositionMethod",
    "TimeWindow",
    "TradeSignalLinker",
    "LinkedTrade",
    "LinkageReport",
    "TradeDecomposer",
    "PnLBreakdown",
    "DecompositionReport",
    "SignalPerformanceTracker",
    "RollingSignalStats",
    "TrackerSnapshot",
    "AttributionEngine",
    "AttributionResult",
    "LiveAttributionReport",
]
