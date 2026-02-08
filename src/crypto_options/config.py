"""Crypto Options Configuration and Enums."""

from dataclasses import dataclass
from enum import Enum


class CryptoOptionType(Enum):
    """Crypto option type."""
    CALL = "call"
    PUT = "put"


class CryptoDerivativeType(Enum):
    """Types of crypto derivatives."""
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    OPTION = "option"
    INVERSE_PERPETUAL = "inverse_perpetual"
    INVERSE_FUTURES = "inverse_futures"


class CryptoExchange(Enum):
    """Supported crypto exchanges."""
    DERIBIT = "deribit"
    BINANCE = "binance"
    OKX = "okx"
    BYBIT = "bybit"
    CME = "cme"


class SettlementType(Enum):
    """Settlement type for crypto derivatives."""
    CASH = "cash"
    PHYSICAL = "physical"
    INVERSE = "inverse"


class MarginType(Enum):
    """Margin type for derivatives."""
    CROSS = "cross"
    ISOLATED = "isolated"
    PORTFOLIO = "portfolio"


# Supported underlyings for crypto options
SUPPORTED_UNDERLYINGS = {
    "BTC": {"tick_size": 0.01, "contract_size": 1.0, "min_order": 0.01},
    "ETH": {"tick_size": 0.01, "contract_size": 1.0, "min_order": 0.1},
    "SOL": {"tick_size": 0.01, "contract_size": 1.0, "min_order": 1.0},
}


@dataclass
class CryptoOptionsConfig:
    """Configuration for crypto options platform."""
    enabled: bool = True
    default_exchange: CryptoExchange = CryptoExchange.DERIBIT
    default_margin_type: MarginType = MarginType.CROSS
    max_leverage: float = 100.0
    funding_rate_interval_hours: int = 8
    default_risk_free_rate: float = 0.05
    iv_smoothing_window: int = 5
    greeks_update_interval_seconds: int = 30
    max_portfolio_delta: float = 10.0
    max_portfolio_gamma: float = 5.0


DEFAULT_CRYPTO_OPTIONS_CONFIG = CryptoOptionsConfig()
