"""Interactive Brokers (IBKR) Integration (PRD-157).

Full-featured IBKR Client Portal Gateway integration with REST client,
WebSocket streaming, and gateway management. Uses IBKR's local gateway
API (localhost:5000) and supports stocks, options, futures, forex, and bonds.

Supports 3-mode fallback: ib_insync SDK -> httpx Gateway -> Demo mode.

Example:
    from src.ibkr_broker import IBKRClient, IBKRConfig

    config = IBKRConfig(
        account_id="U1234567",
    )
    client = IBKRClient(config)
    await client.connect()
    accounts = await client.get_accounts()
"""

from src.ibkr_broker.client import (
    IBKRConfig,
    IBKRClient,
    IBKRAccount,
    IBKRPosition,
    IBKROrder,
    IBKRQuote,
    IBKRCandle,
    IBKRContract,
)
from src.ibkr_broker.streaming import (
    IBKRStreaming,
    StreamChannel,
    StreamEvent,
)
from src.ibkr_broker.gateway import (
    IBKRGateway,
    GatewayStatus,
)

__all__ = [
    # Client
    "IBKRConfig",
    "IBKRClient",
    "IBKRAccount",
    "IBKRPosition",
    "IBKROrder",
    "IBKRQuote",
    "IBKRCandle",
    "IBKRContract",
    # Streaming
    "IBKRStreaming",
    "StreamChannel",
    "StreamEvent",
    # Gateway
    "IBKRGateway",
    "GatewayStatus",
]
