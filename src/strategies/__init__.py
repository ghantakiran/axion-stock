"""PRD-177: Multi-Strategy Bot — pluggable strategy framework.

Provides a BotStrategy protocol, a StrategyRegistry for dynamic
registration, and 6 built-in strategies: VWAP, ORB, RSI Divergence,
Pullback-to-Cloud, Trend Day, and Session Scalp.
"""

from src.strategies.base import BotStrategy
from src.strategies.registry import StrategyRegistry
from src.strategies.vwap_strategy import VWAPStrategy
from src.strategies.orb_strategy import ORBStrategy
from src.strategies.rsi_divergence import RSIDivergenceStrategy
from src.strategies.pullback_strategy import PullbackToCloudStrategy
from src.strategies.trend_day_strategy import TrendDayStrategy
from src.strategies.session_scalp_strategy import SessionScalpStrategy
from src.qullamaggie.breakout_strategy import QullamaggieBreakoutStrategy
from src.qullamaggie.episodic_pivot_strategy import EpisodicPivotStrategy
from src.qullamaggie.parabolic_short_strategy import ParabolicShortStrategy

__all__ = [
    "BotStrategy",
    "StrategyRegistry",
    "VWAPStrategy",
    "ORBStrategy",
    "RSIDivergenceStrategy",
    "PullbackToCloudStrategy",
    "TrendDayStrategy",
    "SessionScalpStrategy",
    "QullamaggieBreakoutStrategy",
    "EpisodicPivotStrategy",
    "ParabolicShortStrategy",
]
