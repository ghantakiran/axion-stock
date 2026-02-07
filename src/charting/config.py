"""Configuration for Advanced Charting."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChartType(Enum):
    """Chart display types."""
    CANDLESTICK = "candlestick"
    OHLC = "ohlc"
    LINE = "line"
    AREA = "area"
    HEIKIN_ASHI = "heikin_ashi"
    RENKO = "renko"
    POINT_FIGURE = "point_figure"


class Timeframe(Enum):
    """Chart timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN = "1M"


class DrawingType(Enum):
    """Drawing tool types."""
    TRENDLINE = "trendline"
    HORIZONTAL_LINE = "horizontal_line"
    VERTICAL_LINE = "vertical_line"
    CHANNEL = "channel"
    FIBONACCI_RETRACEMENT = "fib_retracement"
    FIBONACCI_EXTENSION = "fib_extension"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    ARROW = "arrow"
    TEXT = "text"
    PRICE_LABEL = "price_label"
    MEASURE = "measure"
    PITCHFORK = "pitchfork"
    GANN_FAN = "gann_fan"


class IndicatorCategory(Enum):
    """Indicator categories."""
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    SUPPORT_RESISTANCE = "support_resistance"
    CUSTOM = "custom"


class LineStyle(Enum):
    """Line drawing styles."""
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


@dataclass
class ChartConfig:
    """Chart configuration."""
    
    # Display settings
    default_chart_type: ChartType = ChartType.CANDLESTICK
    default_timeframe: Timeframe = Timeframe.D1
    candle_up_color: str = "#26A69A"
    candle_down_color: str = "#EF5350"
    background_color: str = "#131722"
    grid_color: str = "#363A45"
    
    # Axis settings
    show_volume: bool = True
    volume_height_pct: float = 0.2
    price_scale_position: str = "right"
    time_scale_visible: bool = True
    
    # Interaction
    enable_zoom: bool = True
    enable_pan: bool = True
    enable_crosshair: bool = True
    
    # Limits
    max_indicators: int = 10
    max_drawings: int = 100
    max_layouts: int = 50
    
    # Data
    max_candles: int = 5000
    default_candles_visible: int = 100


DEFAULT_CHART_CONFIG = ChartConfig()


# Indicator definitions
INDICATOR_DEFINITIONS: dict[str, dict] = {
    # Trend indicators
    "SMA": {
        "name": "Simple Moving Average",
        "category": IndicatorCategory.TREND,
        "params": {"period": 20},
        "overlay": True,
    },
    "EMA": {
        "name": "Exponential Moving Average",
        "category": IndicatorCategory.TREND,
        "params": {"period": 20},
        "overlay": True,
    },
    "WMA": {
        "name": "Weighted Moving Average",
        "category": IndicatorCategory.TREND,
        "params": {"period": 20},
        "overlay": True,
    },
    "VWAP": {
        "name": "Volume Weighted Average Price",
        "category": IndicatorCategory.TREND,
        "params": {},
        "overlay": True,
    },
    "BB": {
        "name": "Bollinger Bands",
        "category": IndicatorCategory.TREND,
        "params": {"period": 20, "std": 2.0},
        "overlay": True,
    },
    "ICHIMOKU": {
        "name": "Ichimoku Cloud",
        "category": IndicatorCategory.TREND,
        "params": {"tenkan": 9, "kijun": 26, "senkou": 52},
        "overlay": True,
    },
    # Momentum indicators
    "RSI": {
        "name": "Relative Strength Index",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"period": 14},
        "overlay": False,
    },
    "MACD": {
        "name": "MACD",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "overlay": False,
    },
    "STOCH": {
        "name": "Stochastic",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"k": 14, "d": 3},
        "overlay": False,
    },
    "CCI": {
        "name": "Commodity Channel Index",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"period": 20},
        "overlay": False,
    },
    "WILLR": {
        "name": "Williams %R",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"period": 14},
        "overlay": False,
    },
    "ROC": {
        "name": "Rate of Change",
        "category": IndicatorCategory.MOMENTUM,
        "params": {"period": 12},
        "overlay": False,
    },
    # Volume indicators
    "OBV": {
        "name": "On Balance Volume",
        "category": IndicatorCategory.VOLUME,
        "params": {},
        "overlay": False,
    },
    "VPROFILE": {
        "name": "Volume Profile",
        "category": IndicatorCategory.VOLUME,
        "params": {"rows": 24},
        "overlay": True,
    },
    "ADL": {
        "name": "Accumulation/Distribution",
        "category": IndicatorCategory.VOLUME,
        "params": {},
        "overlay": False,
    },
    "CMF": {
        "name": "Chaikin Money Flow",
        "category": IndicatorCategory.VOLUME,
        "params": {"period": 20},
        "overlay": False,
    },
    # Volatility indicators
    "ATR": {
        "name": "Average True Range",
        "category": IndicatorCategory.VOLATILITY,
        "params": {"period": 14},
        "overlay": False,
    },
    "KC": {
        "name": "Keltner Channel",
        "category": IndicatorCategory.VOLATILITY,
        "params": {"period": 20, "mult": 2.0},
        "overlay": True,
    },
    "DC": {
        "name": "Donchian Channel",
        "category": IndicatorCategory.VOLATILITY,
        "params": {"period": 20},
        "overlay": True,
    },
    # Support/Resistance
    "PIVOT": {
        "name": "Pivot Points",
        "category": IndicatorCategory.SUPPORT_RESISTANCE,
        "params": {"type": "standard"},
        "overlay": True,
    },
    "FIB": {
        "name": "Auto Fibonacci",
        "category": IndicatorCategory.SUPPORT_RESISTANCE,
        "params": {"lookback": 100},
        "overlay": True,
    },
}
