"""Robinhood Broker Implementation.

Placeholder implementation for Robinhood API.
"""

from src.brokers.config import BrokerType, BrokerCapabilities, BROKER_CAPABILITIES
from src.brokers.implementations.mock import MockBroker


class RobinhoodBroker(MockBroker):
    """Robinhood broker implementation.
    
    Currently uses mock implementation. Full implementation would
    integrate with Robinhood's API.
    
    Example:
        broker = RobinhoodBroker(
            access_token="...",
            account_id="...",
        )
    """
    
    def __init__(
        self,
        access_token: str = "",
        account_id: str = "",
    ):
        super().__init__(
            broker_type=BrokerType.ROBINHOOD,
            account_id=account_id or "robinhood_demo",
        )
        self._access_token = access_token
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BROKER_CAPABILITIES.get(
            BrokerType.ROBINHOOD,
            super().capabilities
        )
