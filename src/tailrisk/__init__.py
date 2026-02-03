"""Tail Risk Hedging Module.

CVaR computation, tail dependence analysis, hedge construction,
and drawdown-based risk budgeting.

Example:
    from src.tailrisk import CVaRCalculator, HedgeConstructor

    calc = CVaRCalculator()
    cvar = calc.compute(returns, portfolio_value=1_000_000, confidence=0.95)
    print(f"CVaR(95%): {cvar.cvar_pct:.2%} (${cvar.cvar_dollar:,.0f})")

    hedger = HedgeConstructor()
    portfolio = hedger.build_hedge_portfolio(1_000_000, 0.20, cvar.cvar_pct)
"""

from src.tailrisk.config import (
    CVaRMethod,
    HedgeInstrument,
    DrawdownMethod,
    RiskBudgetMethod,
    CVaRConfig,
    DependenceConfig,
    HedgingConfig,
    BudgetingConfig,
)

from src.tailrisk.models import (
    CVaRResult,
    CVaRContribution,
    TailDependence,
    HedgeRecommendation,
    HedgePortfolio,
    DrawdownStats,
    DrawdownBudget,
)

from src.tailrisk.cvar import CVaRCalculator
from src.tailrisk.dependence import TailDependenceAnalyzer
from src.tailrisk.hedging import HedgeConstructor
from src.tailrisk.budgeting import DrawdownRiskBudgeter

__all__ = [
    # Config
    "CVaRMethod",
    "HedgeInstrument",
    "DrawdownMethod",
    "RiskBudgetMethod",
    "CVaRConfig",
    "DependenceConfig",
    "HedgingConfig",
    "BudgetingConfig",
    # Models
    "CVaRResult",
    "CVaRContribution",
    "TailDependence",
    "HedgeRecommendation",
    "HedgePortfolio",
    "DrawdownStats",
    "DrawdownBudget",
    # Components
    "CVaRCalculator",
    "TailDependenceAnalyzer",
    "HedgeConstructor",
    "DrawdownRiskBudgeter",
]
