"""Market Microstructure Module.

Bid-ask spread analysis, order book imbalance, tick-level
metrics, and price impact estimation.

Example:
    from src.microstructure import SpreadAnalyzer, TickAnalyzer

    analyzer = SpreadAnalyzer()
    metrics = analyzer.analyze(trades, bids, asks, "AAPL")
    print(f"Effective spread: {metrics.effective_spread_bps} bps")

    tick = TickAnalyzer()
    result = tick.analyze(trades, midpoints, "AAPL")
    print(f"VWAP: {result.vwap}, Kyle's lambda: {result.kyle_lambda}")
"""

from src.microstructure.config import (
    TradeClassification,
    SpreadType,
    ImpactModel,
    BookSide,
    SpreadConfig,
    OrderBookConfig,
    TickConfig,
    ImpactConfig,
    MicrostructureConfig,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_ORDERBOOK_CONFIG,
    DEFAULT_TICK_CONFIG,
    DEFAULT_IMPACT_CONFIG,
    DEFAULT_CONFIG,
)

from src.microstructure.models import (
    SpreadMetrics,
    BookLevel,
    OrderBookSnapshot,
    TickMetrics,
    Trade,
    ImpactEstimate,
)

from src.microstructure.spread import SpreadAnalyzer
from src.microstructure.orderbook import OrderBookAnalyzer
from src.microstructure.tick import TickAnalyzer
from src.microstructure.impact import ImpactEstimator

__all__ = [
    # Config
    "TradeClassification",
    "SpreadType",
    "ImpactModel",
    "BookSide",
    "SpreadConfig",
    "OrderBookConfig",
    "TickConfig",
    "ImpactConfig",
    "MicrostructureConfig",
    "DEFAULT_SPREAD_CONFIG",
    "DEFAULT_ORDERBOOK_CONFIG",
    "DEFAULT_TICK_CONFIG",
    "DEFAULT_IMPACT_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "SpreadMetrics",
    "BookLevel",
    "OrderBookSnapshot",
    "TickMetrics",
    "Trade",
    "ImpactEstimate",
    # Components
    "SpreadAnalyzer",
    "OrderBookAnalyzer",
    "TickAnalyzer",
    "ImpactEstimator",
]
