"""Webull Broker Integration (PRD-159).

Full-featured Webull API integration with REST client, WebSocket streaming,
and built-in stock screener. Zero-commission, extended hours (4am-8pm ET),
crypto, stocks, options, and ETFs.

Supports 3-mode fallback: webull SDK -> httpx HTTP -> Demo mode.
Uses device_id + trade_pin authentication (not OAuth2).

Example:
    from src.webull_broker import WebullClient, WebullConfig

    config = WebullConfig(
        device_id="YOUR_DEVICE_ID",
        access_token="YOUR_TOKEN",
    )
    client = WebullClient(config)
    await client.connect()
    account = await client.get_account()
"""

from src.webull_broker.client import (
    WebullConfig,
    WebullClient,
    WebullAccount,
    WebullPosition,
    WebullOrder,
    WebullQuote,
    WebullCandle,
    WebullScreenerResult,
)
from src.webull_broker.streaming import (
    WebullStreaming,
    StreamChannel,
    StreamEvent,
)

__all__ = [
    # Client
    "WebullConfig",
    "WebullClient",
    "WebullAccount",
    "WebullPosition",
    "WebullOrder",
    "WebullQuote",
    "WebullCandle",
    "WebullScreenerResult",
    # Streaming
    "WebullStreaming",
    "StreamChannel",
    "StreamEvent",
]
