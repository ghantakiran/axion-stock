"""Alpaca Live Broker Integration (PRD-139).

Full-featured Alpaca API integration with REST client, WebSocket streaming,
account synchronization, order lifecycle management, and market data.

Upgrades the existing demo AlpacaBroker stub to real API connectivity
with graceful fallback to demo mode when credentials aren't available.

Example:
    from src.alpaca_live import AlpacaClient, AlpacaConfig, AlpacaEnvironment

    config = AlpacaConfig(
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        environment=AlpacaEnvironment.PAPER,
    )
    client = AlpacaClient(config)
    await client.connect()
    account = await client.get_account()
"""

from src.alpaca_live.client import (
    AlpacaClient,
    AlpacaConfig,
    AlpacaEnvironment,
    AlpacaAccount,
    AlpacaPosition,
    AlpacaOrder,
    AlpacaBar,
    AlpacaQuote,
    AlpacaSnapshot,
)
from src.alpaca_live.streaming import (
    AlpacaStreaming,
    StreamChannel,
    StreamEvent,
    OrderUpdate,
)
from src.alpaca_live.account_sync import (
    AccountSync,
    SyncState,
    SyncConfig,
)
from src.alpaca_live.order_manager import (
    OrderManager,
    ManagedOrder,
    OrderLifecycleState,
)
from src.alpaca_live.market_data import (
    MarketDataProvider,
    BarRequest,
    MarketDataCache,
)

__all__ = [
    # Client
    "AlpacaClient",
    "AlpacaConfig",
    "AlpacaEnvironment",
    "AlpacaAccount",
    "AlpacaPosition",
    "AlpacaOrder",
    "AlpacaBar",
    "AlpacaQuote",
    "AlpacaSnapshot",
    # Streaming
    "AlpacaStreaming",
    "StreamChannel",
    "StreamEvent",
    "OrderUpdate",
    # Account Sync
    "AccountSync",
    "SyncState",
    "SyncConfig",
    # Order Management
    "OrderManager",
    "ManagedOrder",
    "OrderLifecycleState",
    # Market Data
    "MarketDataProvider",
    "BarRequest",
    "MarketDataCache",
]
