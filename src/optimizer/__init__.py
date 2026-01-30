"""Portfolio Optimization & Construction Module.

Provides mean-variance optimization, Black-Litterman, risk parity,
HRP, tax-aware rebalancing, and portfolio templates.
"""

from src.optimizer.analytics import (
    PortfolioAnalytics,
    PortfolioXRay,
    WhatIfAnalyzer,
    WhatIfResult,
)
from src.optimizer.black_litterman import (
    BLResult,
    BlackLittermanModel,
    View,
)
from src.optimizer.config import (
    ConstraintConfig,
    OptimizationConfig,
    PortfolioConfig,
    TaxConfig,
)
from src.optimizer.constraints import (
    Constraint,
    ConstraintEngine,
    CountConstraint,
    PositionConstraint,
    SectorConstraint,
    TurnoverConstraint,
)
from src.optimizer.objectives import (
    HRPOptimizer,
    MeanVarianceOptimizer,
    OptimizationResult,
    RiskParityOptimizer,
)
from src.optimizer.tax import (
    HarvestCandidate,
    Position,
    RebalanceTrade,
    TaxAwareRebalancer,
    TaxLossHarvester,
)
from src.optimizer.templates import (
    PortfolioTemplate,
    StrategyBlender,
    TemplateSpec,
    TEMPLATES,
)

__all__ = [
    # Config
    "OptimizationConfig",
    "ConstraintConfig",
    "TaxConfig",
    "PortfolioConfig",
    # Objectives
    "MeanVarianceOptimizer",
    "RiskParityOptimizer",
    "HRPOptimizer",
    "OptimizationResult",
    # Black-Litterman
    "BlackLittermanModel",
    "View",
    "BLResult",
    # Constraints
    "Constraint",
    "ConstraintEngine",
    "PositionConstraint",
    "SectorConstraint",
    "TurnoverConstraint",
    "CountConstraint",
    # Tax
    "TaxLossHarvester",
    "TaxAwareRebalancer",
    "Position",
    "HarvestCandidate",
    "RebalanceTrade",
    # Templates
    "PortfolioTemplate",
    "StrategyBlender",
    "TemplateSpec",
    "TEMPLATES",
    # Analytics
    "PortfolioAnalytics",
    "PortfolioXRay",
    "WhatIfAnalyzer",
    "WhatIfResult",
]
