"""Coinbase Broker Integration (PRD-144).

Full-featured Coinbase API integration with REST client, WebSocket streaming,
and crypto portfolio tracking. Supports Advanced Trade API with graceful
fallback to demo mode when credentials aren't available.

Example:
    from src.coinbase_broker import CoinbaseClient, CoinbaseConfig

    config = CoinbaseConfig(
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
    )
    client = CoinbaseClient(config)
    await client.connect()
    accounts = await client.get_accounts()
"""

from src.coinbase_broker.client import (
    CoinbaseClient,
    CoinbaseConfig,
    CoinbaseAccount,
    CoinbaseOrder,
    CoinbaseFill,
    CoinbaseProduct,
    CoinbaseCandle,
)
from src.coinbase_broker.streaming import (
    CoinbaseWebSocket,
    WSChannel,
    TickerEvent,
    MatchEvent,
)
from src.coinbase_broker.portfolio import (
    CryptoPortfolioTracker,
    PortfolioSnapshot,
)

__all__ = [
    # Client
    "CoinbaseClient",
    "CoinbaseConfig",
    "CoinbaseAccount",
    "CoinbaseOrder",
    "CoinbaseFill",
    "CoinbaseProduct",
    "CoinbaseCandle",
    # Streaming
    "CoinbaseWebSocket",
    "WSChannel",
    "TickerEvent",
    "MatchEvent",
    # Portfolio
    "CryptoPortfolioTracker",
    "PortfolioSnapshot",
]
