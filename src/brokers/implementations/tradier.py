"""Tradier Broker Implementation.

Placeholder implementation for Tradier API.
"""

from src.brokers.config import BrokerType, BrokerCapabilities, BROKER_CAPABILITIES
from src.brokers.implementations.mock import MockBroker


class TradierBroker(MockBroker):
    """Tradier broker implementation.
    
    Currently uses mock implementation. Full implementation would
    integrate with Tradier's REST API.
    
    Example:
        broker = TradierBroker(
            access_token="...",
            account_id="...",
        )
    """
    
    def __init__(
        self,
        access_token: str = "",
        account_id: str = "",
        sandbox: bool = True,
    ):
        super().__init__(
            broker_type=BrokerType.TRADIER,
            account_id=account_id or "tradier_demo",
        )
        self._access_token = access_token
        self._sandbox = sandbox
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BROKER_CAPABILITIES.get(
            BrokerType.TRADIER,
            super().capabilities
        )
