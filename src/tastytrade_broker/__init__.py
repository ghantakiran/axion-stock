"""tastytrade Broker Integration (PRD-158).

Options-specialist broker integration with deep options chain analytics,
futures, and crypto support. Uses tastytrade's session-based auth with
REST client, WebSocket streaming, and options chain analyzer.

Supports 3-mode fallback: tastytrade SDK -> httpx session -> Demo mode.

Example:
    from src.tastytrade_broker import TastytradeClient, TastytradeConfig

    config = TastytradeConfig(
        username="YOUR_USERNAME",
        password="YOUR_PASSWORD",
    )
    client = TastytradeClient(config)
    await client.connect()
    accounts = await client.get_accounts()
"""

from src.tastytrade_broker.client import (
    TastytradeConfig,
    TastytradeClient,
    TastytradeAccount,
    TastytradePosition,
    TastytradeOrder,
    TastytradeQuote,
    TastytradeCandle,
)
from src.tastytrade_broker.streaming import (
    TastytradeStreaming,
    StreamChannel,
    StreamEvent,
)
from src.tastytrade_broker.options_chain import (
    OptionsChainAnalyzer,
    OptionGreeks,
    OptionExpiration,
    OptionStrike,
)

__all__ = [
    # Client
    "TastytradeConfig",
    "TastytradeClient",
    "TastytradeAccount",
    "TastytradePosition",
    "TastytradeOrder",
    "TastytradeQuote",
    "TastytradeCandle",
    # Streaming
    "TastytradeStreaming",
    "StreamChannel",
    "StreamEvent",
    # Options Chain
    "OptionsChainAnalyzer",
    "OptionGreeks",
    "OptionExpiration",
    "OptionStrike",
]
