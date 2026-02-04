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

from src.liquidity.redemption import (
    RedemptionScenario,
    LiquidityBuffer,
    LiquidationItem,
    LiquidationSchedule,
    RedemptionRiskModeler,
)

from src.liquidity.lavar import (
    VaRResult,
    LiquidityCost,
    PositionLaVaR,
    LaVaR,
    LaVaRCalculator,
)
from src.liquidity.spread_model import (
    RollSpreadEstimate,
    SpreadDecomposition,
    SpreadForecast,
    SpreadRegimeProfile,
    SpreadModeler,
)
from src.liquidity.depth_analyzer import (
    DepthLevel,
    DepthSnapshot,
    DepthResilience,
    TopOfBookImbalance,
    DepthProfile,
    MarketDepthAnalyzer,
)
from src.liquidity.liquidity_premium import (
    AmihudRatio,
    PastorStambaughFactor,
    IlliquidityPremium,
    CrossSectionalPremium,
    IlliquidityPremiumEstimator,
)
from src.liquidity.concentration import (
    PositionLiquidity,
    ConcentrationMetrics,
    LiquidityLimit,
    LiquidityRiskReport,
    LiquidityConcentrationAnalyzer,
)
from src.liquidity.cost_curve import (
    CostPoint,
    CostCurve,
    CostComparison,
    OptimalExecution,
    CostCurveBuilder,
)

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
    # Redemption Risk (PRD-54)
    "RedemptionScenario",
    "LiquidityBuffer",
    "LiquidationItem",
    "LiquidationSchedule",
    "RedemptionRiskModeler",
    # Liquidity-Adjusted VaR (PRD-54)
    "VaRResult",
    "LiquidityCost",
    "PositionLaVaR",
    "LaVaR",
    "LaVaRCalculator",
    # Spread Modeling (PRD-62)
    "RollSpreadEstimate",
    "SpreadDecomposition",
    "SpreadForecast",
    "SpreadRegimeProfile",
    "SpreadModeler",
    # Market Depth (PRD-62)
    "DepthLevel",
    "DepthSnapshot",
    "DepthResilience",
    "TopOfBookImbalance",
    "DepthProfile",
    "MarketDepthAnalyzer",
    # Illiquidity Premium (PRD-62)
    "AmihudRatio",
    "PastorStambaughFactor",
    "IlliquidityPremium",
    "CrossSectionalPremium",
    "IlliquidityPremiumEstimator",
    # Concentration (PRD-62)
    "PositionLiquidity",
    "ConcentrationMetrics",
    "LiquidityLimit",
    "LiquidityRiskReport",
    "LiquidityConcentrationAnalyzer",
    # Cost Curves (PRD-62)
    "CostPoint",
    "CostCurve",
    "CostComparison",
    "OptimalExecution",
    "CostCurveBuilder",
]
