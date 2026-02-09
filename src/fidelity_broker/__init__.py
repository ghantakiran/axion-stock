"""Fidelity Broker Integration (PRD-156).

Full-featured Fidelity API integration with REST client, WebSocket
streaming, and research tools. Includes mutual fund screening unique
to Fidelity's platform.

Supports 3-mode fallback: fidelity SDK -> HTTP/OAuth -> Demo mode.

Example:
    from src.fidelity_broker import FidelityClient, FidelityConfig

    config = FidelityConfig(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
    )
    client = FidelityClient(config)
    await client.connect()
    accounts = await client.get_accounts()
"""

from src.fidelity_broker.client import (
    FidelityConfig,
    FidelityClient,
    FidelityAccount,
    FidelityPosition,
    FidelityOrder,
    FidelityQuote,
    FidelityCandle,
    FidelityMutualFund,
)
from src.fidelity_broker.streaming import (
    FidelityStreaming,
    StreamChannel,
    StreamEvent,
)
from src.fidelity_broker.research import (
    FidelityResearch,
    FundScreenResult,
    AnalystRating,
    FundamentalData,
)

__all__ = [
    # Client
    "FidelityConfig",
    "FidelityClient",
    "FidelityAccount",
    "FidelityPosition",
    "FidelityOrder",
    "FidelityQuote",
    "FidelityCandle",
    "FidelityMutualFund",
    # Streaming
    "FidelityStreaming",
    "StreamChannel",
    "StreamEvent",
    # Research
    "FidelityResearch",
    "FundScreenResult",
    "AnalystRating",
    "FundamentalData",
]
