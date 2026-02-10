"""PRD-177: Multi-Strategy Bot — pluggable strategy framework.

Provides a BotStrategy protocol, a StrategyRegistry for dynamic
registration, and 3 built-in strategies: VWAP, ORB, RSI Divergence.
"""

from src.strategies.base import BotStrategy
from src.strategies.registry import StrategyRegistry
from src.strategies.vwap_strategy import VWAPStrategy
from src.strategies.orb_strategy import ORBStrategy
from src.strategies.rsi_divergence import RSIDivergenceStrategy

__all__ = [
    "BotStrategy",
    "StrategyRegistry",
    "VWAPStrategy",
    "ORBStrategy",
    "RSIDivergenceStrategy",
]
