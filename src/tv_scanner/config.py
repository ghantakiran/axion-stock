"""TradingView Scanner configuration — enums, field mappings, and defaults."""

from dataclasses import dataclass, field
from enum import Enum


class AssetClass(str, Enum):
    """Supported TradingView screener asset classes."""

    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    BOND = "bond"
    FUTURES = "futures"
    COIN = "coin"


class TVFieldCategory(str, Enum):
    """Logical grouping for tvscreener fields."""

    PRICE = "price"
    VOLUME = "volume"
    VALUATION = "valuation"
    DIVIDEND = "dividend"
    OSCILLATORS = "oscillators"
    MOVING_AVERAGES = "moving_averages"
    PERFORMANCE = "performance"
    EARNINGS = "earnings"
    PROFITABILITY = "profitability"


class TVTimeInterval(str, Enum):
    """Time intervals for technical indicator fields."""

    MIN_1 = "1"
    MIN_5 = "5"
    MIN_15 = "15"
    MIN_30 = "30"
    HOUR_1 = "60"
    HOUR_2 = "120"
    HOUR_4 = "240"
    DAY = "1D"
    WEEK = "1W"
    MONTH = "1M"


class TVScanCategory(str, Enum):
    """Categories for preset scan configurations."""

    MOMENTUM = "momentum"
    VALUE = "value"
    VOLUME = "volume"
    TECHNICAL = "technical"
    DIVIDEND = "dividend"
    GROWTH = "growth"
    CRYPTO = "crypto"


# Map tvscreener DataFrame column names → Axion-friendly names
TV_FIELD_MAP: dict[str, str] = {
    "close": "price",
    "change": "change_pct",
    "volume": "volume",
    "relative_volume_10d_calc": "relative_volume",
    "RSI": "rsi",
    "RSI7": "rsi_7",
    "MACD.macd": "macd",
    "MACD.signal": "macd_signal",
    "SMA20": "sma_20",
    "SMA50": "sma_50",
    "SMA200": "sma_200",
    "EMA20": "ema_20",
    "EMA50": "ema_50",
    "EMA200": "ema_200",
    "Recommend.All": "tv_rating",
    "market_cap_basic": "market_cap",
    "price_earnings_ttm": "pe_ratio",
    "dividend_yield_recent": "dividend_yield",
    "sector": "sector",
    "name": "company_name",
    "description": "company_name",
    "Perf.W": "perf_week",
    "Perf.1M": "perf_month",
    "Perf.Y": "perf_year",
    "BB.lower": "bb_lower",
    "BB.upper": "bb_upper",
    "earnings_per_share_basic_ttm": "eps",
    "revenue_per_share_ttm": "revenue_per_share",
    "Volatility.D": "volatility_day",
    "high": "high",
    "low": "low",
    "open": "open",
}


@dataclass
class TVScannerConfig:
    """Global configuration for the TradingView scanner engine."""

    default_asset_class: AssetClass = AssetClass.STOCK
    max_results: int = 150
    cache_ttl_seconds: int = 30
    timeout_seconds: int = 15
    min_price: float = 1.0
    min_volume: int = 100_000
    default_sort_ascending: bool = False
