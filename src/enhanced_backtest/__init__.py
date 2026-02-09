"""Enhanced Backtesting Realism (PRD-167).

Adds production-grade realism to the backtesting engine:
- Survivorship bias filter (only trade tickers that were tradable at each date)
- Convex market impact model (non-linear slippage for large orders)
- Monte Carlo path sampling (1000+ random entry/exit permutations)
- Gap risk simulation (overnight and earnings gaps)
- Stop-loss slippage modeling (worst-case fills on fast moves)
"""

from src.enhanced_backtest.survivorship import (
    SurvivorshipFilter,
    SurvivorshipConfig,
)
from src.enhanced_backtest.impact_model import (
    ConvexImpactModel,
    ImpactConfig,
    ImpactResult,
)
from src.enhanced_backtest.monte_carlo import (
    MonteCarloSimulator,
    MonteCarloConfig,
    MonteCarloResult,
    PathStatistics,
)
from src.enhanced_backtest.gap_simulator import (
    GapSimulator,
    GapConfig,
    GapEvent,
)

__all__ = [
    # Survivorship
    "SurvivorshipFilter",
    "SurvivorshipConfig",
    # Impact
    "ConvexImpactModel",
    "ImpactConfig",
    "ImpactResult",
    # Monte Carlo
    "MonteCarloSimulator",
    "MonteCarloConfig",
    "MonteCarloResult",
    "PathStatistics",
    # Gap simulation
    "GapSimulator",
    "GapConfig",
    "GapEvent",
]
