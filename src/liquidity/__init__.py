"""Liquidity Analysis Module.

Bid-ask spread analysis, volume profiling, market impact estimation,
slippage prediction, and composite liquidity scoring.

Example:
    from src.liquidity import LiquidityEngine, MarketImpactEstimator, LiquidityScorer
    import pandas as pd

    engine = LiquidityEngine()
    spread = engine.analyze_spread(bid_series, ask_series, symbol="AAPL")
    volume = engine.analyze_volume(vol_series, close_series, symbol="AAPL")

    estimator = MarketImpactEstimator()
    impact = estimator.estimate_impact(
        trade_size=10000, avg_volume=volume.avg_volume,
        avg_spread=spread.avg_spread, price=150.0
    )

    scorer = LiquidityScorer()
    score = scorer.score(spread, volume, impact, price=150.0)
    print(f"Liquidity: {score.level.value} ({score.score:.0f}/100)")
"""

from src.liquidity.config import (
    LiquidityLevel,
    ImpactModel,
    SpreadType,
    VolumeProfile,
    SpreadConfig,
    VolumeConfig,
    ImpactConfig,
    ScoringConfig,
    LiquidityConfig,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_VOLUME_CONFIG,
    DEFAULT_IMPACT_CONFIG,
    DEFAULT_SCORING_CONFIG,
    DEFAULT_CONFIG,
)

from src.liquidity.models import (
    SpreadAnalysis,
    VolumeAnalysis,
    MarketImpact,
    LiquidityScore,
    LiquiditySnapshot,
)

from src.liquidity.engine import LiquidityEngine
from src.liquidity.impact import MarketImpactEstimator
from src.liquidity.scoring import LiquidityScorer

__all__ = [
    # Config
    "LiquidityLevel",
    "ImpactModel",
    "SpreadType",
    "VolumeProfile",
    "SpreadConfig",
    "VolumeConfig",
    "ImpactConfig",
    "ScoringConfig",
    "LiquidityConfig",
    "DEFAULT_SPREAD_CONFIG",
    "DEFAULT_VOLUME_CONFIG",
    "DEFAULT_IMPACT_CONFIG",
    "DEFAULT_SCORING_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "SpreadAnalysis",
    "VolumeAnalysis",
    "MarketImpact",
    "LiquidityScore",
    "LiquiditySnapshot",
    # Components
    "LiquidityEngine",
    "MarketImpactEstimator",
    "LiquidityScorer",
]
