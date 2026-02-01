"""Technical Charting Module.

Chart pattern detection, trend analysis, support/resistance identification,
and Fibonacci retracement/extension calculations.

Example:
    from src.charting import TrendAnalyzer, FibCalculator
    import pandas as pd

    analyzer = TrendAnalyzer()
    close = pd.Series([100, 102, 104, 103, 105, 107, ...])
    trend = analyzer.analyze(close, symbol="AAPL")
    print(f"Direction: {trend.direction.value}, Strength: {trend.strength}")

    fib = FibCalculator()
    levels = fib.compute_from_points(swing_high=110, swing_low=95)
    print(f"61.8% retracement: {levels.retracements[0.618]}")
"""

from src.charting.config import (
    PatternType,
    TrendDirection,
    SRType,
    CrossoverType,
    PatternConfig,
    TrendConfig,
    SRConfig,
    FibConfig,
    ChartingConfig,
    DEFAULT_PATTERN_CONFIG,
    DEFAULT_TREND_CONFIG,
    DEFAULT_SR_CONFIG,
    DEFAULT_FIB_CONFIG,
    DEFAULT_CONFIG,
)

from src.charting.models import (
    ChartPattern,
    TrendAnalysis,
    MACrossover,
    SRLevel,
    FibonacciLevels,
)

from src.charting.patterns import PatternDetector
from src.charting.trend import TrendAnalyzer
from src.charting.support_resistance import SRDetector
from src.charting.fibonacci import FibCalculator

__all__ = [
    # Config
    "PatternType",
    "TrendDirection",
    "SRType",
    "CrossoverType",
    "PatternConfig",
    "TrendConfig",
    "SRConfig",
    "FibConfig",
    "ChartingConfig",
    "DEFAULT_PATTERN_CONFIG",
    "DEFAULT_TREND_CONFIG",
    "DEFAULT_SR_CONFIG",
    "DEFAULT_FIB_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "ChartPattern",
    "TrendAnalysis",
    "MACrossover",
    "SRLevel",
    "FibonacciLevels",
    # Components
    "PatternDetector",
    "TrendAnalyzer",
    "SRDetector",
    "FibCalculator",
]
