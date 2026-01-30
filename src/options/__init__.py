"""Advanced Options Trading Platform.

Provides options pricing, volatility surface modeling, strategy
building, unusual activity detection, and backtesting.
"""

from src.options.config import (
    OptionsConfig,
    PricingConfig,
    VolatilityConfig,
    StrategyConfig,
    ActivityConfig,
    BacktestConfig,
)
from src.options.pricing import (
    OptionsPricingEngine,
    OptionPrice,
    OptionLeg,
    OptionType,
)
from src.options.volatility import (
    VolatilitySurfaceBuilder,
    VolSurface,
    VolAnalytics,
    VolPoint,
)
from src.options.strategies import (
    StrategyBuilder,
    StrategyAnalysis,
    StrategyType,
    PayoffCurve,
)
from src.options.activity import (
    UnusualActivityDetector,
    ActivitySignal,
    ActivitySummary,
    SignalType,
)
from src.options.backtest import (
    OptionsBacktester,
    BacktestResult,
    BacktestTrade,
    EntryRules,
    ExitRules,
)

__all__ = [
    # Config
    "OptionsConfig",
    "PricingConfig",
    "VolatilityConfig",
    "StrategyConfig",
    "ActivityConfig",
    "BacktestConfig",
    # Pricing
    "OptionsPricingEngine",
    "OptionPrice",
    "OptionLeg",
    "OptionType",
    # Volatility
    "VolatilitySurfaceBuilder",
    "VolSurface",
    "VolAnalytics",
    "VolPoint",
    # Strategies
    "StrategyBuilder",
    "StrategyAnalysis",
    "StrategyType",
    "PayoffCurve",
    # Activity
    "UnusualActivityDetector",
    "ActivitySignal",
    "ActivitySummary",
    "SignalType",
    # Backtest
    "OptionsBacktester",
    "BacktestResult",
    "BacktestTrade",
    "EntryRules",
    "ExitRules",
]
