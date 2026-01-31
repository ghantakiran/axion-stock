"""Broker Integrations.

Multi-broker support for connecting to brokerage accounts,
syncing positions, and executing trades.

Supported Brokers:
- Alpaca (stocks, ETFs, crypto)
- Charles Schwab (full service)
- Interactive Brokers (global markets)
- Tradier (stocks, options)
- Robinhood (stocks, options, crypto)

Example:
    from src.brokers import BrokerManager, BrokerType
    
    # Create manager
    manager = BrokerManager()
    
    # Add Alpaca connection
    await manager.add_broker(
        BrokerType.ALPACA,
        credentials={"api_key": "...", "api_secret": "..."},
        sandbox=True,
    )
    
    # Get all positions
    positions = await manager.get_all_positions()
    
    # Place an order
    from src.brokers import OrderRequest, OrderSide, OrderType
    order = OrderRequest(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )
    result = await manager.place_order(order)
"""

from src.brokers.config import (
    BrokerType,
    AuthMethod,
    AccountType,
    AccountStatus,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    AssetType,
    ConnectionStatus,
    BrokerCapabilities,
    BROKER_CAPABILITIES,
    BrokerConfig,
    OAUTH_ENDPOINTS,
    API_BASE_URLS,
)

from src.brokers.models import (
    BrokerAccount,
    AccountBalances,
    Position,
    Order,
    OrderRequest,
    OrderModify,
    OrderResult,
    Transaction,
    BrokerConnection,
    Quote,
)

from src.brokers.interface import BrokerInterface, BaseBroker
from src.brokers.credentials import (
    BrokerCredentials,
    CredentialManager,
    OAuthManager,
)
from src.brokers.manager import BrokerManager
from src.brokers.implementations import create_broker


__all__ = [
    # Config
    "BrokerType",
    "AuthMethod",
    "AccountType",
    "AccountStatus",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "OrderStatus",
    "AssetType",
    "ConnectionStatus",
    "BrokerCapabilities",
    "BROKER_CAPABILITIES",
    "BrokerConfig",
    "OAUTH_ENDPOINTS",
    "API_BASE_URLS",
    # Models
    "BrokerAccount",
    "AccountBalances",
    "Position",
    "Order",
    "OrderRequest",
    "OrderModify",
    "OrderResult",
    "Transaction",
    "BrokerConnection",
    "Quote",
    # Interface
    "BrokerInterface",
    "BaseBroker",
    # Credentials
    "BrokerCredentials",
    "CredentialManager",
    "OAuthManager",
    # Manager
    "BrokerManager",
    # Factory
    "create_broker",
]
