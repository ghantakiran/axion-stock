"""Professional Backtesting Engine.

A comprehensive event-driven backtesting framework with:
- Multi-timeframe support (minute to monthly)
- Realistic execution modeling (slippage, commissions, market impact)
- Walk-forward optimization to prevent overfitting
- Monte Carlo analysis for statistical significance
- Strategy comparison framework with proper benchmarking
- Visual reporting with tear sheets and trade analysis

Example:
    from src.backtesting import BacktestEngine, BacktestConfig
    from datetime import date

    # Configure backtest
    config = BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=100_000,
    )

    # Run backtest
    engine = BacktestEngine(config)
    engine.load_data(price_data)
    result = engine.run(my_strategy)

    # Generate tear sheet
    from src.backtesting import TearSheetGenerator
    tearsheet = TearSheetGenerator()
    print(tearsheet.generate(result))
"""

from src.backtesting.config import (
    BacktestConfig,
    CostModelConfig,
    ExecutionConfig,
    RiskConfig,
    WalkForwardConfig,
    MonteCarloConfig,
    BarType,
    RebalanceFrequency,
    FillModel,
    DEFAULT_BACKTEST,
    DEFAULT_COST_MODEL,
    DEFAULT_EXECUTION,
    DEFAULT_RISK,
    DEFAULT_WALK_FORWARD,
    DEFAULT_MONTE_CARLO,
)

from src.backtesting.models import (
    BarData,
    MarketEvent,
    Signal,
    Order,
    Fill,
    Position,
    Trade,
    PortfolioSnapshot,
    BacktestMetrics,
    BacktestResult,
    WalkForwardWindow,
    WalkForwardResult,
    MonteCarloResult,
    OrderSide,
    OrderType,
    OrderStatus,
)

from src.backtesting.execution import (
    CostModel,
    ExecutionSimulator,
    SimulatedBroker,
)

from src.backtesting.portfolio import (
    SimulatedPortfolio,
)

from src.backtesting.engine import (
    BacktestEngine,
    Strategy,
    BacktestRiskManager,
    HistoricalDataHandler,
)

from src.backtesting.optimization import (
    WalkForwardOptimizer,
    MonteCarloAnalyzer,
)

from src.backtesting.reporting import (
    TearSheetGenerator,
    StrategyComparator,
)

__all__ = [
    # Config
    "BacktestConfig",
    "CostModelConfig",
    "ExecutionConfig",
    "RiskConfig",
    "WalkForwardConfig",
    "MonteCarloConfig",
    "BarType",
    "RebalanceFrequency",
    "FillModel",
    "DEFAULT_BACKTEST",
    "DEFAULT_COST_MODEL",
    "DEFAULT_EXECUTION",
    "DEFAULT_RISK",
    "DEFAULT_WALK_FORWARD",
    "DEFAULT_MONTE_CARLO",
    # Models
    "BarData",
    "MarketEvent",
    "Signal",
    "Order",
    "Fill",
    "Position",
    "Trade",
    "PortfolioSnapshot",
    "BacktestMetrics",
    "BacktestResult",
    "WalkForwardWindow",
    "WalkForwardResult",
    "MonteCarloResult",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    # Execution
    "CostModel",
    "ExecutionSimulator",
    "SimulatedBroker",
    # Portfolio
    "SimulatedPortfolio",
    # Engine
    "BacktestEngine",
    "Strategy",
    "BacktestRiskManager",
    "HistoricalDataHandler",
    # Optimization
    "WalkForwardOptimizer",
    "MonteCarloAnalyzer",
    # Reporting
    "TearSheetGenerator",
    "StrategyComparator",
]
