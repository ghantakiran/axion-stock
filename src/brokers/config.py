"""Broker Integrations Configuration.

Enums, constants, and configuration for broker connections.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class BrokerType(str, Enum):
    """Supported broker types."""
    ALPACA = "alpaca"
    SCHWAB = "schwab"
    FIDELITY = "fidelity"
    IBKR = "ibkr"  # Interactive Brokers
    TD_AMERITRADE = "td_ameritrade"
    ROBINHOOD = "robinhood"
    TRADIER = "tradier"
    WEBULL = "webull"
    TASTYTRADE = "tastytrade"
    ETRADE = "etrade"


class AuthMethod(str, Enum):
    """Authentication method."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    USERNAME_PASSWORD = "username_password"


class AccountType(str, Enum):
    """Brokerage account type."""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    IRA_TRADITIONAL = "ira_traditional"
    IRA_ROTH = "ira_roth"
    IRA_SEP = "ira_sep"
    MARGIN = "margin"
    CASH = "cash"
    CUSTODIAL = "custodial"
    TRUST = "trust"
    CORPORATE = "corporate"


class AccountStatus(str, Enum):
    """Account status."""
    ACTIVE = "active"
    PENDING = "pending"
    RESTRICTED = "restricted"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"
    SELL_SHORT = "sell_short"
    BUY_TO_COVER = "buy_to_cover"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    DAY = "day"
    GTC = "gtc"  # Good til canceled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    OPG = "opg"  # Market on open
    CLS = "cls"  # Market on close
    GTD = "gtd"  # Good til date


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REPLACED = "replaced"


class AssetType(str, Enum):
    """Asset type."""
    STOCK = "stock"
    ETF = "etf"
    OPTION = "option"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"


class ConnectionStatus(str, Enum):
    """Broker connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TOKEN_EXPIRED = "token_expired"


# =============================================================================
# Broker Capabilities
# =============================================================================

@dataclass
class BrokerCapabilities:
    """Capabilities of a broker."""
    broker: BrokerType
    
    # Trading
    stocks: bool = True
    options: bool = False
    etfs: bool = True
    mutual_funds: bool = False
    bonds: bool = False
    crypto: bool = False
    forex: bool = False
    futures: bool = False
    
    # Account types
    margin: bool = True
    short_selling: bool = False
    
    # Features
    extended_hours: bool = False
    fractional_shares: bool = False
    real_time_quotes: bool = True
    streaming: bool = False
    
    # Order types
    market_orders: bool = True
    limit_orders: bool = True
    stop_orders: bool = True
    trailing_stops: bool = False
    
    # API
    auth_method: AuthMethod = AuthMethod.OAUTH2
    rate_limit_per_minute: int = 60
    supports_websocket: bool = False


# Broker capability definitions
BROKER_CAPABILITIES = {
    BrokerType.ALPACA: BrokerCapabilities(
        broker=BrokerType.ALPACA,
        stocks=True, options=False, etfs=True, crypto=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=True,
        trailing_stops=True,
        auth_method=AuthMethod.API_KEY,
        rate_limit_per_minute=200,
        supports_websocket=True,
    ),
    BrokerType.SCHWAB: BrokerCapabilities(
        broker=BrokerType.SCHWAB,
        stocks=True, options=True, etfs=True, mutual_funds=True, bonds=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=True,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=120,
    ),
    BrokerType.IBKR: BrokerCapabilities(
        broker=BrokerType.IBKR,
        stocks=True, options=True, etfs=True, bonds=True, forex=True, futures=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=False,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=50,
        supports_websocket=True,
    ),
    BrokerType.ROBINHOOD: BrokerCapabilities(
        broker=BrokerType.ROBINHOOD,
        stocks=True, options=True, etfs=True, crypto=True,
        margin=True, short_selling=False,
        extended_hours=True, fractional_shares=True,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=60,
    ),
    BrokerType.TRADIER: BrokerCapabilities(
        broker=BrokerType.TRADIER,
        stocks=True, options=True, etfs=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=False,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=120,
        supports_websocket=True,
    ),
    BrokerType.TD_AMERITRADE: BrokerCapabilities(
        broker=BrokerType.TD_AMERITRADE,
        stocks=True, options=True, etfs=True, mutual_funds=True, bonds=True, futures=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=False,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=120,
        supports_websocket=True,
    ),
    BrokerType.FIDELITY: BrokerCapabilities(
        broker=BrokerType.FIDELITY,
        stocks=True, options=True, etfs=True, mutual_funds=True, bonds=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=True,
        trailing_stops=True,
        auth_method=AuthMethod.OAUTH2,
        rate_limit_per_minute=60,
    ),
    BrokerType.TASTYTRADE: BrokerCapabilities(
        broker=BrokerType.TASTYTRADE,
        stocks=True, options=True, etfs=True, futures=True, crypto=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=False,
        trailing_stops=True,
        auth_method=AuthMethod.USERNAME_PASSWORD,
        rate_limit_per_minute=60,
        supports_websocket=True,
    ),
    BrokerType.WEBULL: BrokerCapabilities(
        broker=BrokerType.WEBULL,
        stocks=True, options=True, etfs=True, crypto=True,
        margin=True, short_selling=True,
        extended_hours=True, fractional_shares=True,
        trailing_stops=True,
        auth_method=AuthMethod.API_KEY,
        rate_limit_per_minute=60,
    ),
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class BrokerConfig:
    """Configuration for a broker connection."""
    broker: BrokerType
    
    # OAuth settings
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8000/callback"
    
    # API settings
    api_key: str = ""
    api_secret: str = ""
    
    # Environment
    sandbox: bool = True
    base_url: Optional[str] = None
    
    # Timeouts
    connect_timeout: int = 30
    read_timeout: int = 60
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


# OAuth endpoints
OAUTH_ENDPOINTS = {
    BrokerType.SCHWAB: {
        "authorize": "https://api.schwabapi.com/v1/oauth/authorize",
        "token": "https://api.schwabapi.com/v1/oauth/token",
        "scope": "read write",
    },
    BrokerType.IBKR: {
        "authorize": "https://www.interactivebrokers.com/oauth/authorize",
        "token": "https://www.interactivebrokers.com/oauth/token",
        "scope": "trading",
    },
    BrokerType.TRADIER: {
        "authorize": "https://api.tradier.com/v1/oauth/authorize",
        "token": "https://api.tradier.com/v1/oauth/accesstoken",
        "scope": "read write market trade",
    },
    BrokerType.TD_AMERITRADE: {
        "authorize": "https://auth.tdameritrade.com/auth",
        "token": "https://api.tdameritrade.com/v1/oauth2/token",
        "scope": "PlaceTrades AccountAccess MoveMoney",
    },
}


# API base URLs
API_BASE_URLS = {
    BrokerType.ALPACA: {
        "live": "https://api.alpaca.markets",
        "paper": "https://paper-api.alpaca.markets",
    },
    BrokerType.SCHWAB: {
        "live": "https://api.schwabapi.com/trader/v1",
        "paper": "https://api.schwabapi.com/trader/v1",  # Same endpoint, sandbox account
    },
    BrokerType.IBKR: {
        "live": "https://localhost:5000/v1/api",  # Client Portal Gateway
        "paper": "https://localhost:5000/v1/api",
    },
    BrokerType.TRADIER: {
        "live": "https://api.tradier.com/v1",
        "paper": "https://sandbox.tradier.com/v1",
    },
}
