"""Portfolio Scenarios.

What-if analysis, hypothetical portfolios, rebalancing simulation,
market stress testing, portfolio comparison, and goal-based planning.

Example:
    from src.scenarios import (
        WhatIfAnalyzer, Portfolio, Holding, ProposedTrade, TradeAction
    )
    
    # Create a portfolio
    portfolio = Portfolio(
        name="My Portfolio",
        holdings=[
            Holding(symbol="AAPL", shares=100, current_price=185),
            Holding(symbol="MSFT", shares=50, current_price=378),
        ],
        cash=10000,
    )
    
    # What-if analysis
    analyzer = WhatIfAnalyzer()
    trade = ProposedTrade(symbol="GOOGL", action=TradeAction.BUY, dollar_amount=5000)
    result = analyzer.simulate(portfolio, [trade])
    
    print(f"New portfolio value: ${result.resulting_portfolio.total_value:,.2f}")
"""

from src.scenarios.config import (
    TradeAction,
    SizeMethod,
    RebalanceStrategy,
    ScenarioType,
    GoalType,
    GoalPriority,
    SECTOR_BETAS,
    SimulationConfig,
    GoalConfig,
    DEFAULT_SIMULATION_CONFIG,
    DEFAULT_GOAL_CONFIG,
)

from src.scenarios.models import (
    Holding,
    Portfolio,
    HypotheticalPortfolio,
    ProposedTrade,
    RiskImpact,
    TaxImpact,
    TradeSimulation,
    TargetAllocation,
    RebalanceSimulation,
    MarketScenario,
    PositionImpact,
    ScenarioResult,
    PortfolioMetrics,
    PortfolioComparison,
    InvestmentGoal,
    GoalProjection,
)

from src.scenarios.what_if import WhatIfAnalyzer
from src.scenarios.rebalance import RebalanceSimulator
from src.scenarios.market_scenarios import (
    ScenarioAnalyzer,
    PREDEFINED_SCENARIOS,
)
from src.scenarios.comparison import PortfolioComparer
from src.scenarios.goals import GoalPlanner


__all__ = [
    # Config
    "TradeAction",
    "SizeMethod",
    "RebalanceStrategy",
    "ScenarioType",
    "GoalType",
    "GoalPriority",
    "SECTOR_BETAS",
    "SimulationConfig",
    "GoalConfig",
    "DEFAULT_SIMULATION_CONFIG",
    "DEFAULT_GOAL_CONFIG",
    # Models
    "Holding",
    "Portfolio",
    "HypotheticalPortfolio",
    "ProposedTrade",
    "RiskImpact",
    "TaxImpact",
    "TradeSimulation",
    "TargetAllocation",
    "RebalanceSimulation",
    "MarketScenario",
    "PositionImpact",
    "ScenarioResult",
    "PortfolioMetrics",
    "PortfolioComparison",
    "InvestmentGoal",
    "GoalProjection",
    # Analyzers
    "WhatIfAnalyzer",
    "RebalanceSimulator",
    "ScenarioAnalyzer",
    "PREDEFINED_SCENARIOS",
    "PortfolioComparer",
    "GoalPlanner",
]
