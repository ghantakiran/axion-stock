"""Order Execution & Brokerage Integration Module.

This module provides:
- Broker abstraction layer for multiple brokerages
- Paper trading with realistic simulation
- Alpaca integration for live/paper trading
- Smart order routing and execution
- Position sizing algorithms
- Automated rebalancing engine
- Trade journaling and audit trail
- High-level trading service

Usage:
    from src.execution import TradingService, TradingConfig

    # Initialize trading service
    config = TradingConfig(paper_trading=True, initial_cash=100_000)
    service = TradingService(config)
    await service.connect()

    # Execute trades
    result = await service.buy("AAPL", dollars=5000)

    # Rebalance portfolio
    weights = {"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4}
    proposal = await service.preview_rebalance(weights)
    proposal.approved = True
    await service.execute_rebalance(proposal)
"""

from src.execution.models import (
    OrderSide,
    OrderType,
    OrderStatus,
    OrderTimeInForce,
    OrderRequest,
    Order,
    Position,
    AccountInfo,
    Trade,
    ExecutionResult,
)
from src.execution.interfaces import (
    BrokerInterface,
    BrokerError,
    OrderValidationError,
    InsufficientFundsError,
    PositionLimitError,
    MarketClosedError,
)
from src.execution.paper_broker import PaperBroker
from src.execution.alpaca_broker import AlpacaBroker
from src.execution.order_manager import (
    OrderManager,
    PreTradeValidator,
    ValidationConfig,
    SmartOrderRouter,
)
from src.execution.position_sizer import PositionSizer, SizingConstraints
from src.execution.rebalancer import (
    RebalanceEngine,
    RebalanceTrigger,
    RebalanceConfig,
    RebalanceProposal,
)
from src.execution.journal import TradeJournal
from src.execution.trading_service import TradingService, TradingConfig
from src.execution.tca import (
    CostComponent,
    TCAResult,
    AggregateTCA,
    TCAEngine,
)
from src.execution.scheduling import (
    TimeSlice,
    ExecutionSchedule,
    ScheduleComparison,
    ExecutionScheduler,
)
from src.execution.broker_compare import (
    BrokerStats,
    BrokerComparison,
    TradeRecord,
    BrokerComparator,
)
from src.execution.fill_quality import (
    FillMetrics,
    FillDistribution,
    SymbolFillProfile,
    FillQualityAnalyzer,
)

__all__ = [
    # Models
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "OrderTimeInForce",
    "OrderRequest",
    "Order",
    "Position",
    "AccountInfo",
    "Trade",
    "ExecutionResult",
    # Interfaces & Exceptions
    "BrokerInterface",
    "BrokerError",
    "OrderValidationError",
    "InsufficientFundsError",
    "PositionLimitError",
    "MarketClosedError",
    # Brokers
    "PaperBroker",
    "AlpacaBroker",
    # Order Management
    "OrderManager",
    "PreTradeValidator",
    "ValidationConfig",
    "SmartOrderRouter",
    # Position Sizing
    "PositionSizer",
    "SizingConstraints",
    # Rebalancing
    "RebalanceEngine",
    "RebalanceTrigger",
    "RebalanceConfig",
    "RebalanceProposal",
    # Trade Journal
    "TradeJournal",
    # Trading Service
    "TradingService",
    "TradingConfig",
    # TCA
    "CostComponent",
    "TCAResult",
    "AggregateTCA",
    "TCAEngine",
    # Scheduling
    "TimeSlice",
    "ExecutionSchedule",
    "ScheduleComparison",
    "ExecutionScheduler",
    # Broker Comparison
    "BrokerStats",
    "BrokerComparison",
    "TradeRecord",
    "BrokerComparator",
    # Fill Quality
    "FillMetrics",
    "FillDistribution",
    "SymbolFillProfile",
    "FillQualityAnalyzer",
]
