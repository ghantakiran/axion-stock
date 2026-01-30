"""Multi-Asset Configuration.

Asset class definitions, contract specifications, market configs,
and cross-asset portfolio templates.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AssetClass(str, Enum):
    US_EQUITY = "us_equity"
    INTL_EQUITY = "intl_equity"
    CRYPTO = "crypto"
    FUTURES = "futures"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    CASH = "cash"


class CryptoCategory(str, Enum):
    MAJOR = "major"
    DEFI = "defi"
    LAYER2 = "layer2"
    STABLECOIN = "stablecoin"
    ALT = "alt"


class FuturesCategory(str, Enum):
    EQUITY_INDEX = "equity_index"
    TREASURY = "treasury"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    VOLATILITY = "volatility"


class SettlementType(str, Enum):
    CASH = "cash"
    PHYSICAL = "physical"


class MarginAlertLevel(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"       # 80%
    CRITICAL = "critical"     # 90%
    MARGIN_CALL = "margin_call"  # 100%
    LIQUIDATION = "liquidation"  # 110%


# ─── Supported Instruments ──────────────────────────────────────────────

SUPPORTED_CRYPTO = {
    "BTC": CryptoCategory.MAJOR, "ETH": CryptoCategory.MAJOR,
    "SOL": CryptoCategory.MAJOR, "ADA": CryptoCategory.MAJOR,
    "DOT": CryptoCategory.MAJOR, "AVAX": CryptoCategory.MAJOR,
    "LINK": CryptoCategory.MAJOR, "MATIC": CryptoCategory.MAJOR,
    "UNI": CryptoCategory.DEFI, "AAVE": CryptoCategory.DEFI,
    "MKR": CryptoCategory.DEFI, "CRV": CryptoCategory.DEFI,
    "SNX": CryptoCategory.DEFI, "ARB": CryptoCategory.LAYER2,
    "OP": CryptoCategory.LAYER2,
    "USDC": CryptoCategory.STABLECOIN, "USDT": CryptoCategory.STABLECOIN,
}

SUPPORTED_FUTURES = {
    "ES": FuturesCategory.EQUITY_INDEX,
    "NQ": FuturesCategory.EQUITY_INDEX,
    "YM": FuturesCategory.EQUITY_INDEX,
    "RTY": FuturesCategory.EQUITY_INDEX,
    "ZN": FuturesCategory.TREASURY,
    "ZB": FuturesCategory.TREASURY,
    "ZF": FuturesCategory.TREASURY,
    "CL": FuturesCategory.COMMODITY,
    "GC": FuturesCategory.COMMODITY,
    "SI": FuturesCategory.COMMODITY,
    "NG": FuturesCategory.COMMODITY,
    "6E": FuturesCategory.CURRENCY,
    "6J": FuturesCategory.CURRENCY,
    "6B": FuturesCategory.CURRENCY,
    "VX": FuturesCategory.VOLATILITY,
}

INTL_MARKETS = {
    "UK": {"exchange": "LSE", "currency": "GBP", "hours": "03:00-11:30"},
    "Germany": {"exchange": "XETRA", "currency": "EUR", "hours": "03:00-11:30"},
    "France": {"exchange": "Euronext", "currency": "EUR", "hours": "03:00-11:30"},
    "Japan": {"exchange": "TSE", "currency": "JPY", "hours": "19:00-01:00"},
    "HongKong": {"exchange": "HKEX", "currency": "HKD", "hours": "21:30-04:00"},
    "Australia": {"exchange": "ASX", "currency": "AUD", "hours": "19:00-01:00"},
    "Canada": {"exchange": "TSX", "currency": "CAD", "hours": "09:30-16:00"},
}


# ─── Contract Specs ─────────────────────────────────────────────────────

@dataclass
class ContractSpec:
    """Futures contract specification."""

    symbol: str
    name: str
    category: FuturesCategory
    multiplier: float
    tick_size: float
    tick_value: float
    margin_initial: float
    margin_maintenance: float
    trading_hours: str
    expiration_months: list[str] = field(default_factory=lambda: ["H", "M", "U", "Z"])
    settlement: SettlementType = SettlementType.CASH
    currency: str = "USD"


DEFAULT_CONTRACT_SPECS: dict[str, ContractSpec] = {
    "ES": ContractSpec("ES", "E-mini S&P 500", FuturesCategory.EQUITY_INDEX,
                       50, 0.25, 12.50, 12_650, 11_500, "Sun 6pm-Fri 5pm ET"),
    "NQ": ContractSpec("NQ", "E-mini Nasdaq 100", FuturesCategory.EQUITY_INDEX,
                       20, 0.25, 5.00, 17_600, 16_000, "Sun 6pm-Fri 5pm ET"),
    "YM": ContractSpec("YM", "E-mini Dow", FuturesCategory.EQUITY_INDEX,
                       5, 1.0, 5.00, 9_500, 8_600, "Sun 6pm-Fri 5pm ET"),
    "RTY": ContractSpec("RTY", "E-mini Russell 2000", FuturesCategory.EQUITY_INDEX,
                        50, 0.10, 5.00, 6_800, 6_200, "Sun 6pm-Fri 5pm ET"),
    "ZN": ContractSpec("ZN", "10-Year T-Note", FuturesCategory.TREASURY,
                       1000, 1/64, 15.625, 2_200, 2_000, "Sun 6pm-Fri 5pm ET",
                       settlement=SettlementType.PHYSICAL),
    "ZB": ContractSpec("ZB", "30-Year T-Bond", FuturesCategory.TREASURY,
                       1000, 1/32, 31.25, 4_400, 4_000, "Sun 6pm-Fri 5pm ET",
                       settlement=SettlementType.PHYSICAL),
    "ZF": ContractSpec("ZF", "5-Year T-Note", FuturesCategory.TREASURY,
                       1000, 1/128, 7.8125, 1_500, 1_350, "Sun 6pm-Fri 5pm ET",
                       settlement=SettlementType.PHYSICAL),
    "CL": ContractSpec("CL", "Crude Oil", FuturesCategory.COMMODITY,
                       1000, 0.01, 10.00, 6_600, 6_000, "Sun 6pm-Fri 5pm ET",
                       expiration_months=["F","G","H","J","K","M","N","Q","U","V","X","Z"],
                       settlement=SettlementType.PHYSICAL),
    "GC": ContractSpec("GC", "Gold", FuturesCategory.COMMODITY,
                       100, 0.10, 10.00, 10_000, 9_100, "Sun 6pm-Fri 5pm ET",
                       expiration_months=["G","J","M","Q","V","Z"]),
    "SI": ContractSpec("SI", "Silver", FuturesCategory.COMMODITY,
                       5000, 0.005, 25.00, 9_500, 8_600, "Sun 6pm-Fri 5pm ET",
                       expiration_months=["H","K","N","U","Z"]),
    "NG": ContractSpec("NG", "Natural Gas", FuturesCategory.COMMODITY,
                       10000, 0.001, 10.00, 3_850, 3_500, "Sun 6pm-Fri 5pm ET",
                       expiration_months=["F","G","H","J","K","M","N","Q","U","V","X","Z"],
                       settlement=SettlementType.PHYSICAL),
    "VX": ContractSpec("VX", "VIX Futures", FuturesCategory.VOLATILITY,
                       1000, 0.05, 50.00, 10_000, 9_100, "Sun 6pm-Fri 4:15pm ET"),
}


# ─── Cross-Asset Templates ──────────────────────────────────────────────

CROSS_ASSET_TEMPLATES: dict[str, dict[AssetClass, float]] = {
    "conservative": {
        AssetClass.US_EQUITY: 0.30, AssetClass.INTL_EQUITY: 0.10,
        AssetClass.FIXED_INCOME: 0.40, AssetClass.COMMODITY: 0.05,
        AssetClass.CRYPTO: 0.00, AssetClass.CASH: 0.15,
    },
    "balanced": {
        AssetClass.US_EQUITY: 0.40, AssetClass.INTL_EQUITY: 0.10,
        AssetClass.FIXED_INCOME: 0.25, AssetClass.COMMODITY: 0.05,
        AssetClass.CRYPTO: 0.05, AssetClass.CASH: 0.15,
    },
    "growth": {
        AssetClass.US_EQUITY: 0.45, AssetClass.INTL_EQUITY: 0.15,
        AssetClass.FIXED_INCOME: 0.10, AssetClass.COMMODITY: 0.05,
        AssetClass.CRYPTO: 0.15, AssetClass.CASH: 0.10,
    },
    "aggressive": {
        AssetClass.US_EQUITY: 0.35, AssetClass.INTL_EQUITY: 0.15,
        AssetClass.FIXED_INCOME: 0.00, AssetClass.COMMODITY: 0.10,
        AssetClass.CRYPTO: 0.25, AssetClass.CASH: 0.15,
    },
    "ray_dalio": {
        AssetClass.US_EQUITY: 0.30, AssetClass.INTL_EQUITY: 0.00,
        AssetClass.FIXED_INCOME: 0.55, AssetClass.COMMODITY: 0.075,
        AssetClass.CRYPTO: 0.00, AssetClass.CASH: 0.075,
    },
}


# ─── Config Dataclasses ─────────────────────────────────────────────────

@dataclass
class CryptoConfig:
    """Cryptocurrency integration settings."""

    enabled: bool = True
    max_portfolio_pct: float = 0.15
    settlement_type: str = "T+0"
    trading_hours: str = "24/7"
    stablecoin_as_cash: bool = True


@dataclass
class FuturesConfig:
    """Futures integration settings."""

    enabled: bool = True
    max_notional_pct: float = 0.50
    roll_threshold_days: int = 5
    margin_warning_pct: float = 0.80
    margin_critical_pct: float = 0.90
    margin_call_pct: float = 1.00
    auto_liquidation_pct: float = 1.10


@dataclass
class FXConfig:
    """Foreign exchange settings."""

    base_currency: str = "USD"
    hedge_threshold: float = 0.10
    auto_hedge: bool = False


@dataclass
class MultiAssetConfig:
    """Top-level multi-asset configuration."""

    crypto: CryptoConfig = field(default_factory=CryptoConfig)
    futures: FuturesConfig = field(default_factory=FuturesConfig)
    fx: FXConfig = field(default_factory=FXConfig)
    max_asset_classes: int = 6
    rebalance_threshold: float = 0.05


DEFAULT_MULTI_ASSET_CONFIG = MultiAssetConfig()
