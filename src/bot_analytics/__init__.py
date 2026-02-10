"""PRD-175: Live Bot Analytics — real-time performance tracking.

Provides rolling equity curves, Sharpe/Sortino/Calmar ratios,
drawdown analysis, and per-signal/per-strategy breakdowns.
"""

from src.bot_analytics.metrics import (
    calmar_ratio,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from src.bot_analytics.snapshot import PerformanceSnapshot
from src.bot_analytics.tracker import BotPerformanceTracker

__all__ = [
    "BotPerformanceTracker",
    "PerformanceSnapshot",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "max_drawdown",
]
