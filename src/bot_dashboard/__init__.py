"""Trading Bot Dashboard & Control Center (PRD-137).

Unified dashboard for monitoring and controlling the autonomous trading bot.
Combines real-time P&L tracking, position monitoring, signal visualization,
EMA cloud charts, and a kill switch into a single command center.
"""

from src.bot_dashboard.state import (
    BotController,
    BotEvent,
    BotState,
    DashboardConfig,
)
from src.bot_dashboard.metrics import DailyMetrics, PerformanceMetrics
from src.bot_dashboard.charts import CloudChartRenderer

__all__ = [
    "BotController",
    "BotEvent",
    "BotState",
    "DashboardConfig",
    "PerformanceMetrics",
    "DailyMetrics",
    "CloudChartRenderer",
]
