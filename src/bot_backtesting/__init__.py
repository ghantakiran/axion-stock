"""Bot Strategy Backtesting Integration (PRD-138).

Bridges the backtesting engine with the autonomous trading bot's
EMA Cloud Signal Engine, enabling historical validation of bot
strategies with signal-type attribution and replay analysis.
"""

from src.bot_backtesting.strategy import EMACloudStrategy, StrategyConfig
from src.bot_backtesting.runner import (
    BotBacktestRunner,
    BotBacktestConfig,
    EnrichedBacktestResult,
)
from src.bot_backtesting.attribution import (
    SignalAttributor,
    SignalTypeStats,
    AttributionReport,
)
from src.bot_backtesting.replay import (
    SignalReplay,
    ReplayResult,
    ReplayEntry,
)

__all__ = [
    # Strategy adapter
    "EMACloudStrategy",
    "StrategyConfig",
    # Runner
    "BotBacktestRunner",
    "BotBacktestConfig",
    "EnrichedBacktestResult",
    # Attribution
    "SignalAttributor",
    "SignalTypeStats",
    "AttributionReport",
    # Replay
    "SignalReplay",
    "ReplayResult",
    "ReplayEntry",
]
