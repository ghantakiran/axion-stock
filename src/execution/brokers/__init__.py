"""Broker implementations for order execution.

Provides PaperBroker for simulated trading and AlpacaBroker
for live/paper trading via Alpaca API.
"""

from typing import Literal, Optional

from src.execution.brokers.base import BaseBroker, BrokerInterface


def get_broker(
    broker_type: Literal["paper", "alpaca"] = "paper",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    paper: bool = True,
    initial_cash: float = 100_000.0,
) -> BrokerInterface:
    """Factory function to create broker instances.

    Args:
        broker_type: Type of broker ('paper' or 'alpaca').
        api_key: Alpaca API key (required for alpaca).
        secret_key: Alpaca secret key (required for alpaca).
        paper: Use paper trading for Alpaca.
        initial_cash: Starting cash for paper broker.

    Returns:
        BrokerInterface implementation.

    Raises:
        ValueError: If invalid broker_type or missing credentials.
    """
    if broker_type == "paper":
        from src.execution.brokers.paper import PaperBroker

        return PaperBroker(initial_cash=initial_cash)

    elif broker_type == "alpaca":
        if not api_key or not secret_key:
            raise ValueError("Alpaca broker requires api_key and secret_key")

        from src.execution.brokers.alpaca import AlpacaBroker

        return AlpacaBroker(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )

    else:
        raise ValueError(f"Unknown broker type: {broker_type}")


__all__ = [
    "BaseBroker",
    "BrokerInterface",
    "get_broker",
]
