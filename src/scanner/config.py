"""Market Scanner Configuration.

Enums, constants, and configuration for market scanning.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import time


# =============================================================================
# Enums
# =============================================================================

class Operator(str, Enum):
    """Comparison operators."""
    GT = "gt"           # Greater than
    LT = "lt"           # Less than
    EQ = "eq"           # Equals
    GTE = "gte"         # Greater than or equal
    LTE = "lte"         # Less than or equal
    BETWEEN = "between" # Between two values
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    INCREASING = "increasing"
    DECREASING = "decreasing"


class ScanCategory(str, Enum):
    """Scan categories."""
    PRICE_ACTION = "price_action"
    VOLUME = "volume"
    TECHNICAL = "technical"
    MOMENTUM = "momentum"
    UNUSUAL = "unusual"
    PATTERN = "pattern"
    CUSTOM = "custom"


class ActivityType(str, Enum):
    """Unusual activity types."""
    VOLUME_SURGE = "volume_surge"
    PRICE_SPIKE = "price_spike"
    OPTIONS_ACTIVITY = "options_activity"
    BLOCK_TRADE = "block_trade"
    HALT = "halt"
    GAP = "gap"


class PatternType(str, Enum):
    """Chart pattern types."""
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_shoulders"
    INV_HEAD_SHOULDERS = "inv_head_shoulders"
    TRIANGLE_ASC = "triangle_ascending"
    TRIANGLE_DESC = "triangle_descending"
    TRIANGLE_SYM = "triangle_symmetric"
    FLAG = "flag"
    PENNANT = "pennant"
    CUP_HANDLE = "cup_handle"
    WEDGE_RISING = "wedge_rising"
    WEDGE_FALLING = "wedge_falling"


class CandlePattern(str, Enum):
    """Candlestick patterns."""
    DOJI = "doji"
    HAMMER = "hammer"
    INV_HAMMER = "inverted_hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING_BULL = "engulfing_bullish"
    ENGULFING_BEAR = "engulfing_bearish"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"
    HARAMI_BULL = "harami_bullish"
    HARAMI_BEAR = "harami_bearish"


class SignalStrength(str, Enum):
    """Signal strength levels."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class Universe(str, Enum):
    """Scan universe."""
    ALL = "all"
    SP500 = "sp500"
    NASDAQ100 = "nasdaq100"
    DOW30 = "dow30"
    RUSSELL2000 = "russell2000"
    SECTOR = "sector"
    CUSTOM = "custom"


# =============================================================================
# Constants
# =============================================================================

# Default thresholds
DEFAULT_GAP_THRESHOLD = 3.0  # 3%
DEFAULT_VOLUME_THRESHOLD = 2.0  # 2x average
DEFAULT_RSI_OVERSOLD = 30
DEFAULT_RSI_OVERBOUGHT = 70

# Scan intervals (seconds)
SCAN_INTERVALS = {
    "realtime": 5,
    "fast": 15,
    "normal": 60,
    "slow": 300,
}

# Market hours (Eastern)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
PREMARKET_OPEN = time(4, 0)
AFTERHOURS_CLOSE = time(20, 0)

# Available scan fields
SCAN_FIELDS = {
    # Price
    "open": "Open Price",
    "high": "High Price",
    "low": "Low Price",
    "close": "Last Price",
    "price": "Last Price",
    "change": "Price Change",
    "change_pct": "Change %",
    "gap_pct": "Gap %",
    "high_52w": "52W High",
    "low_52w": "52W Low",
    "dist_52w_high": "Distance from 52W High",
    "dist_52w_low": "Distance from 52W Low",
    
    # Volume
    "volume": "Volume",
    "avg_volume": "Avg Volume (20d)",
    "relative_volume": "Relative Volume",
    "dollar_volume": "Dollar Volume",
    
    # Moving Averages
    "sma_5": "SMA 5",
    "sma_10": "SMA 10",
    "sma_20": "SMA 20",
    "sma_50": "SMA 50",
    "sma_200": "SMA 200",
    "ema_9": "EMA 9",
    "ema_21": "EMA 21",
    "dist_sma_50": "Distance from SMA 50",
    "dist_sma_200": "Distance from SMA 200",
    
    # Oscillators
    "rsi": "RSI (14)",
    "stoch_k": "Stochastic %K",
    "stoch_d": "Stochastic %D",
    "cci": "CCI (20)",
    "williams_r": "Williams %R",
    "mfi": "Money Flow Index",
    
    # Trend
    "macd": "MACD",
    "macd_signal": "MACD Signal",
    "macd_hist": "MACD Histogram",
    "adx": "ADX",
    "plus_di": "+DI",
    "minus_di": "-DI",
    
    # Volatility
    "atr": "ATR (14)",
    "bb_upper": "BB Upper",
    "bb_lower": "BB Lower",
    "bb_width": "BB Width %",
    "bb_pct_b": "BB %B",
    
    # Fundamentals
    "market_cap": "Market Cap",
    "pe_ratio": "P/E Ratio",
    "float_shares": "Float",
    "short_float": "Short % of Float",
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ScannerConfig:
    """Configuration for scanner."""
    max_results: int = 50
    scan_interval: int = 60
    enable_alerts: bool = True
    market_hours_only: bool = True
    min_price: float = 1.0
    min_volume: int = 100000
    min_market_cap: float = 100e6


@dataclass  
class UnusualActivityConfig:
    """Configuration for unusual activity detection."""
    volume_std_threshold: float = 3.0
    price_std_threshold: float = 3.0
    min_dollar_volume: float = 1e6
    lookback_days: int = 20


DEFAULT_SCANNER_CONFIG = ScannerConfig()
DEFAULT_UNUSUAL_CONFIG = UnusualActivityConfig()
