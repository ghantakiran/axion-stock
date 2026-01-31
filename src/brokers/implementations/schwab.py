"""Charles Schwab Broker Implementation.

Placeholder implementation for Schwab API.
"""

from src.brokers.config import BrokerType, BrokerCapabilities, BROKER_CAPABILITIES
from src.brokers.implementations.mock import MockBroker


class SchwabBroker(MockBroker):
    """Charles Schwab broker implementation.
    
    Currently uses mock implementation. Full implementation would
    integrate with Schwab's OAuth 2.0 API.
    
    Example:
        broker = SchwabBroker(
            access_token="...",
            refresh_token="...",
            account_id="...",
        )
    """
    
    def __init__(
        self,
        access_token: str = "",
        refresh_token: str = "",
        account_id: str = "",
    ):
        super().__init__(
            broker_type=BrokerType.SCHWAB,
            account_id=account_id or "schwab_demo",
        )
        self._access_token = access_token
        self._refresh_token = refresh_token
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BROKER_CAPABILITIES.get(
            BrokerType.SCHWAB,
            super().capabilities
        )
