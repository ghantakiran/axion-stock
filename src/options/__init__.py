"""Advanced Options Trading Platform.

Provides options pricing, volatility surface modeling, strategy
building, unusual activity detection, backtesting, chain analysis,
and flow classification.
"""

from src.options.config import (
    OptionsConfig,
    PricingConfig,
    VolatilityConfig,
    StrategyConfig,
    ActivityConfig,
    BacktestConfig,
    ChainConfig,
    FlowConfig,
    FlowType,
    ActivityLevel,
    Sentiment,
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
from src.options.models import (
    OptionGreeks,
    OptionContract,
    ChainSummary,
    OptionsFlow,
    UnusualActivity,
)
from src.options.chain import ChainAnalyzer
from src.options.flow import FlowDetector

__all__ = [
    # Config
    "OptionsConfig",
    "PricingConfig",
    "VolatilityConfig",
    "StrategyConfig",
    "ActivityConfig",
    "BacktestConfig",
    "ChainConfig",
    "FlowConfig",
    "FlowType",
    "ActivityLevel",
    "Sentiment",
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
    # Chain Analysis (PRD-43)
    "OptionGreeks",
    "OptionContract",
    "ChainSummary",
    "OptionsFlow",
    "UnusualActivity",
    "ChainAnalyzer",
    "FlowDetector",
]
