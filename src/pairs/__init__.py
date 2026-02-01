"""Pairs Trading Module.

Statistical pairs trading with cointegration testing,
spread analysis, pair selection, and signal generation.

Example:
    from src.pairs import CointegrationTester, SpreadAnalyzer, PairSelector

    tester = CointegrationTester()
    result = tester.test_pair(prices_a, prices_b, "AAPL", "MSFT")
    print(f"Cointegrated: {result.is_cointegrated} (p={result.pvalue})")

    analyzer = SpreadAnalyzer()
    spread = analyzer.analyze(prices_a, prices_b, result.hedge_ratio)
    print(f"Z-score: {spread.zscore}, Signal: {spread.signal.value}")
"""

from src.pairs.config import (
    PairSignalType,
    SpreadMethod,
    HedgeMethod,
    PairStatus,
    CointegrationConfig,
    SpreadConfig,
    SelectorConfig,
    PairsConfig,
    DEFAULT_COINTEGRATION_CONFIG,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_SELECTOR_CONFIG,
    DEFAULT_CONFIG,
)

from src.pairs.models import (
    CointegrationResult,
    SpreadAnalysis,
    PairScore,
    PairSignal,
    PairTrade,
)

from src.pairs.cointegration import CointegrationTester
from src.pairs.spread import SpreadAnalyzer
from src.pairs.selector import PairSelector

__all__ = [
    # Config
    "PairSignalType",
    "SpreadMethod",
    "HedgeMethod",
    "PairStatus",
    "CointegrationConfig",
    "SpreadConfig",
    "SelectorConfig",
    "PairsConfig",
    "DEFAULT_COINTEGRATION_CONFIG",
    "DEFAULT_SPREAD_CONFIG",
    "DEFAULT_SELECTOR_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "CointegrationResult",
    "SpreadAnalysis",
    "PairScore",
    "PairSignal",
    "PairTrade",
    # Components
    "CointegrationTester",
    "SpreadAnalyzer",
    "PairSelector",
]
