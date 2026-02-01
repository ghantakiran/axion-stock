"""Portfolio Rebalancing Module.

Drift monitoring, rebalance planning with tax and cost optimization,
and calendar/threshold-based scheduling.

Example:
    from src.rebalancing import DriftMonitor, RebalancePlanner, RebalanceScheduler
    from src.rebalancing import Holding

    holdings = [
        Holding(symbol="AAPL", current_weight=0.30, target_weight=0.25, price=150),
        Holding(symbol="MSFT", current_weight=0.20, target_weight=0.25, price=350),
    ]

    monitor = DriftMonitor()
    drift = monitor.compute_drift(holdings)
    print(f"Max drift: {drift.max_drift:.2%}")

    planner = RebalancePlanner()
    plan = planner.plan_threshold_rebalance(holdings, portfolio_value=100000)
    print(f"Trades: {plan.n_trades}, Cost: ${plan.estimated_cost:.2f}")
"""

from src.rebalancing.config import (
    RebalanceTrigger,
    RebalanceFrequency,
    DriftMethod,
    RebalanceStatus,
    DriftConfig,
    CalendarConfig,
    TaxConfig,
    CostConfig,
    RebalancingConfig,
    DEFAULT_DRIFT_CONFIG,
    DEFAULT_CALENDAR_CONFIG,
    DEFAULT_TAX_CONFIG,
    DEFAULT_COST_CONFIG,
    DEFAULT_CONFIG,
)

from src.rebalancing.models import (
    Holding,
    DriftAnalysis,
    PortfolioDrift,
    RebalanceTrade,
    RebalancePlan,
    ScheduleState,
)

from src.rebalancing.drift import DriftMonitor
from src.rebalancing.planner import RebalancePlanner
from src.rebalancing.scheduler import RebalanceScheduler

__all__ = [
    # Config
    "RebalanceTrigger",
    "RebalanceFrequency",
    "DriftMethod",
    "RebalanceStatus",
    "DriftConfig",
    "CalendarConfig",
    "TaxConfig",
    "CostConfig",
    "RebalancingConfig",
    "DEFAULT_DRIFT_CONFIG",
    "DEFAULT_CALENDAR_CONFIG",
    "DEFAULT_TAX_CONFIG",
    "DEFAULT_COST_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "Holding",
    "DriftAnalysis",
    "PortfolioDrift",
    "RebalanceTrade",
    "RebalancePlan",
    "ScheduleState",
    # Components
    "DriftMonitor",
    "RebalancePlanner",
    "RebalanceScheduler",
]
