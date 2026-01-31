"""Paper Trading System.

Live paper trading engine with session management, simulated data feeds,
strategy automation, and real-time performance tracking.

Example:
    from src.paper_trading import SessionManager, SessionConfig

    manager = SessionManager()
    session = manager.create_session("Test Session", SessionConfig(
        initial_capital=100_000,
        symbols=["AAPL", "MSFT", "GOOGL"],
    ))
    manager.start_session(session.session_id)

    # Execute trades
    manager.execute_buy(session.session_id, "AAPL", 100)
    manager.advance_feed(session.session_id)
    manager.record_snapshot(session.session_id)

    # Get metrics
    metrics = manager.get_metrics(session.session_id)
"""

from src.paper_trading.config import (
    SessionStatus,
    DataFeedType,
    RebalanceSchedule,
    StrategyType,
    PerformancePeriod,
    DataFeedConfig,
    StrategyConfig,
    SessionConfig,
    DEFAULT_SESSION_CONFIG,
    DEFAULT_DATA_FEED_CONFIG,
    DEFAULT_STRATEGY_CONFIG,
)

from src.paper_trading.models import (
    SessionTrade,
    PortfolioPosition,
    SessionSnapshot,
    SessionMetrics,
    PaperSession,
    SessionComparison,
)

from src.paper_trading.data_feed import DataFeed
from src.paper_trading.performance import PerformanceTracker
from src.paper_trading.session import SessionManager

__all__ = [
    # Config
    "SessionStatus",
    "DataFeedType",
    "RebalanceSchedule",
    "StrategyType",
    "PerformancePeriod",
    "DataFeedConfig",
    "StrategyConfig",
    "SessionConfig",
    "DEFAULT_SESSION_CONFIG",
    "DEFAULT_DATA_FEED_CONFIG",
    "DEFAULT_STRATEGY_CONFIG",
    # Models
    "SessionTrade",
    "PortfolioPosition",
    "SessionSnapshot",
    "SessionMetrics",
    "PaperSession",
    "SessionComparison",
    # Components
    "DataFeed",
    "PerformanceTracker",
    "SessionManager",
]
