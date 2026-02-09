"""Schwab Broker Integration (PRD-145).

Full-featured Schwab/Fidelity API integration with REST client, WebSocket
streaming, and research tools. Uses Schwab's API (post-Fidelity acquisition).

Supports 3-mode fallback: schwab SDK -> HTTP/OAuth -> Demo mode.

Example:
    from src.schwab_broker import SchwabClient, SchwabConfig

    config = SchwabConfig(
        app_key="YOUR_APP_KEY",
        app_secret="YOUR_APP_SECRET",
    )
    client = SchwabClient(config)
    await client.connect()
    accounts = await client.get_accounts()
"""

from src.schwab_broker.client import (
    SchwabConfig,
    SchwabClient,
    SchwabAccount,
    SchwabPosition,
    SchwabOrder,
    SchwabQuote,
    SchwabCandle,
    SchwabMover,
)
from src.schwab_broker.streaming import (
    SchwabStreaming,
    StreamChannel,
    StreamEvent,
)
from src.schwab_broker.research import (
    SchwabResearch,
    FundamentalData,
    ScreenerResult,
    AnalystRating,
)

__all__ = [
    # Client
    "SchwabConfig",
    "SchwabClient",
    "SchwabAccount",
    "SchwabPosition",
    "SchwabOrder",
    "SchwabQuote",
    "SchwabCandle",
    "SchwabMover",
    # Streaming
    "SchwabStreaming",
    "StreamChannel",
    "StreamEvent",
    # Research
    "SchwabResearch",
    "FundamentalData",
    "ScreenerResult",
    "AnalystRating",
]
