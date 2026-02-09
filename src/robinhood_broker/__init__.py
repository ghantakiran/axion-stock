"""Robinhood Broker Integration (PRD-143).

Full-featured Robinhood API integration with REST client, polling-based
streaming, portfolio tracking, and order management.

Uses robin_stocks SDK when available, falls back to raw HTTP via requests,
then to demo mode when no credentials are provided.

Example:
    from src.robinhood_broker import RobinhoodClient, RobinhoodConfig

    config = RobinhoodConfig(
        username="your_email@example.com",
        password="your_password",
    )
    client = RobinhoodClient(config)
    client.connect()
    account = client.get_account()
"""

from src.robinhood_broker.client import (
    RobinhoodClient,
    RobinhoodConfig,
    RobinhoodAccount,
    RobinhoodPosition,
    RobinhoodOrder,
    RobinhoodQuote,
)
from src.robinhood_broker.streaming import (
    RobinhoodStreaming,
    QuoteUpdate,
    OrderStatusUpdate,
)
from src.robinhood_broker.portfolio import (
    PortfolioTracker,
    PortfolioSnapshot,
)

__all__ = [
    # Client
    "RobinhoodClient",
    "RobinhoodConfig",
    "RobinhoodAccount",
    "RobinhoodPosition",
    "RobinhoodOrder",
    "RobinhoodQuote",
    # Streaming
    "RobinhoodStreaming",
    "QuoteUpdate",
    "OrderStatusUpdate",
    # Portfolio
    "PortfolioTracker",
    "PortfolioSnapshot",
]
