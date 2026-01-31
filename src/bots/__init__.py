"""Automated Trading Bots.

Comprehensive trading bot system including:
- DCA (Dollar-Cost Averaging) bots
- Portfolio rebalancing bots
- Signal-based trading bots
- Grid trading bots
- Scheduling and execution engine

Example:
    from src.bots import BotEngine, BotConfig, BotType, DCAConfig
    
    # Create engine
    engine = BotEngine()
    
    # Create a DCA bot
    config = BotConfig(
        name="Weekly S&P 500",
        bot_type=BotType.DCA,
        symbols=["SPY"],
        dca_config=DCAConfig(
            amount_per_period=100,
            allocations={"SPY": 1.0},
        ),
    )
    bot = engine.create_bot(config)
    
    # Run manually
    execution = engine.run_bot(bot.bot_id, {"SPY": {"price": 450}})
    
    # Or let scheduler handle it
    engine.run_due_bots(market_data)
"""

from src.bots.config import (
    # Enums
    BotType,
    BotStatus,
    ExecutionStatus,
    ScheduleFrequency,
    ExecutionTime,
    OrderType,
    SignalType,
    SignalCondition,
    PositionSizeMethod,
    RebalanceMethod,
    GridType,
    TradeSide,
    # Config dataclasses
    ScheduleConfig,
    RiskConfig,
    ExecutionConfig,
    DCAConfig,
    RebalanceConfig,
    SignalBotConfig,
    GridConfig,
    BotConfig,
    GlobalBotSettings,
    DEFAULT_GLOBAL_SETTINGS,
)

from src.bots.models import (
    BotOrder,
    BotExecution,
    BotPerformance,
    BotPosition,
    Signal,
    GridLevel,
    ScheduledRun,
    BotSummary,
)

from src.bots.base import BaseBot, BrokerInterface
from src.bots.dca import DCABot
from src.bots.rebalance import RebalanceBot
from src.bots.signal import SignalBot
from src.bots.grid import GridBot
from src.bots.scheduler import BotScheduler
from src.bots.engine import BotEngine

__all__ = [
    # Enums
    "BotType",
    "BotStatus",
    "ExecutionStatus",
    "ScheduleFrequency",
    "ExecutionTime",
    "OrderType",
    "SignalType",
    "SignalCondition",
    "PositionSizeMethod",
    "RebalanceMethod",
    "GridType",
    "TradeSide",
    # Config
    "ScheduleConfig",
    "RiskConfig",
    "ExecutionConfig",
    "DCAConfig",
    "RebalanceConfig",
    "SignalBotConfig",
    "GridConfig",
    "BotConfig",
    "GlobalBotSettings",
    "DEFAULT_GLOBAL_SETTINGS",
    # Models
    "BotOrder",
    "BotExecution",
    "BotPerformance",
    "BotPosition",
    "Signal",
    "GridLevel",
    "ScheduledRun",
    "BotSummary",
    # Bot classes
    "BaseBot",
    "BrokerInterface",
    "DCABot",
    "RebalanceBot",
    "SignalBot",
    "GridBot",
    # Scheduler & Engine
    "BotScheduler",
    "BotEngine",
]
