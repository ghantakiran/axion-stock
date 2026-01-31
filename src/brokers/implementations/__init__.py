"""Broker Implementations.

Concrete implementations for each supported broker.
"""

from typing import Optional

from src.brokers.config import BrokerType, BROKER_CAPABILITIES
from src.brokers.interface import BrokerInterface


def create_broker(
    broker_type: BrokerType,
    credentials: dict,
    account_id: str = "",
    sandbox: bool = True,
) -> BrokerInterface:
    """Factory function to create a broker instance.
    
    Args:
        broker_type: Type of broker.
        credentials: Authentication credentials.
        account_id: Account ID.
        sandbox: Use sandbox environment.
        
    Returns:
        Broker instance implementing BrokerInterface.
    """
    if broker_type == BrokerType.ALPACA:
        from src.brokers.implementations.alpaca import AlpacaBroker
        return AlpacaBroker(
            api_key=credentials.get("api_key", ""),
            api_secret=credentials.get("api_secret", ""),
            account_id=account_id,
            sandbox=sandbox,
        )
    
    elif broker_type == BrokerType.SCHWAB:
        from src.brokers.implementations.schwab import SchwabBroker
        return SchwabBroker(
            access_token=credentials.get("access_token", ""),
            refresh_token=credentials.get("refresh_token", ""),
            account_id=account_id,
        )
    
    elif broker_type == BrokerType.IBKR:
        from src.brokers.implementations.ibkr import IBKRBroker
        return IBKRBroker(
            account_id=account_id,
        )
    
    elif broker_type == BrokerType.TRADIER:
        from src.brokers.implementations.tradier import TradierBroker
        return TradierBroker(
            access_token=credentials.get("access_token", ""),
            account_id=account_id,
            sandbox=sandbox,
        )
    
    elif broker_type == BrokerType.ROBINHOOD:
        from src.brokers.implementations.robinhood import RobinhoodBroker
        return RobinhoodBroker(
            access_token=credentials.get("access_token", ""),
            account_id=account_id,
        )
    
    else:
        # Return a mock broker for unsupported types
        from src.brokers.implementations.mock import MockBroker
        return MockBroker(broker_type=broker_type, account_id=account_id)


__all__ = ["create_broker"]
