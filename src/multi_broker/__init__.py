"""Smart Multi-Broker Execution (PRD-146).

Unified routing layer that aggregates all connected brokers (Alpaca, Robinhood,
Coinbase, Schwab) and routes orders intelligently based on cost, speed, asset
support, and availability. Provides failover, portfolio aggregation, and a
single pane of glass for multi-broker trading.

Example:
    from src.multi_broker import (
        BrokerRegistry, OrderRouter, PortfolioAggregator, MultiBrokerExecutor,
    )

    registry = BrokerRegistry()
    registry.register("alpaca", alpaca_adapter)
    registry.register("coinbase", coinbase_adapter)

    router = OrderRouter(registry)
    decision = router.route(order)

    executor = MultiBrokerExecutor(registry, router)
    result = executor.execute(order)
"""

from src.multi_broker.registry import (
    BrokerAdapter,
    BrokerInfo,
    BrokerRegistry,
    BrokerStatus,
    DEFAULT_FEE_SCHEDULES,
)
from src.multi_broker.router import (
    RoutingRule,
    RouteDecision,
    RoutingCriteria,
    OrderRouter,
)
from src.multi_broker.aggregator import (
    AggregatedPosition,
    AggregatedPortfolio,
    PortfolioAggregator,
)
from src.multi_broker.executor import (
    ExecutionResult,
    ExecutionStatus,
    MultiBrokerExecutor,
)

__all__ = [
    # Registry
    "BrokerAdapter",
    "BrokerInfo",
    "BrokerRegistry",
    "BrokerStatus",
    "DEFAULT_FEE_SCHEDULES",
    # Router
    "RoutingRule",
    "RouteDecision",
    "RoutingCriteria",
    "OrderRouter",
    # Aggregator
    "AggregatedPosition",
    "AggregatedPortfolio",
    "PortfolioAggregator",
    # Executor
    "ExecutionResult",
    "ExecutionStatus",
    "MultiBrokerExecutor",
]
