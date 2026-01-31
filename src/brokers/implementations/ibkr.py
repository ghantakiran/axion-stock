"""Interactive Brokers Implementation.

Placeholder implementation for IBKR API.
"""

from src.brokers.config import BrokerType, BrokerCapabilities, BROKER_CAPABILITIES
from src.brokers.implementations.mock import MockBroker


class IBKRBroker(MockBroker):
    """Interactive Brokers implementation.
    
    Currently uses mock implementation. Full implementation would
    integrate with IBKR's Client Portal Gateway API.
    
    Example:
        broker = IBKRBroker(account_id="...")
    """
    
    def __init__(self, account_id: str = ""):
        super().__init__(
            broker_type=BrokerType.IBKR,
            account_id=account_id or "ibkr_demo",
        )
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BROKER_CAPABILITIES.get(
            BrokerType.IBKR,
            super().capabilities
        )
