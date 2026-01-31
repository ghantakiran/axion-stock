"""Pre-Built Scanners.

Ready-to-use scanners for common trading setups.
"""

from src.scanner.config import Operator, ScanCategory
from src.scanner.models import Scanner, ScanCriterion


def _criterion(field: str, op: Operator, value, **kwargs) -> ScanCriterion:
    """Helper to create criterion."""
    return ScanCriterion(field=field, operator=op, value=value, **kwargs)


# =============================================================================
# Price Action Scans
# =============================================================================

GAP_UP_SCAN = Scanner(
    name="Gap Up >3%",
    description="Stocks gapping up more than 3% from previous close",
    category=ScanCategory.PRICE_ACTION,
    criteria=[
        _criterion("gap_pct", Operator.GT, 3.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

GAP_DOWN_SCAN = Scanner(
    name="Gap Down >3%",
    description="Stocks gapping down more than 3% from previous close",
    category=ScanCategory.PRICE_ACTION,
    criteria=[
        _criterion("gap_pct", Operator.LT, -3.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

NEW_HIGH_SCAN = Scanner(
    name="New 52-Week High",
    description="Stocks making new 52-week highs",
    category=ScanCategory.PRICE_ACTION,
    criteria=[
        _criterion("dist_52w_high", Operator.GTE, -0.5),  # Within 0.5% of high
        _criterion("change_pct", Operator.GT, 0),
    ],
    is_preset=True,
)

NEW_LOW_SCAN = Scanner(
    name="New 52-Week Low",
    description="Stocks making new 52-week lows",
    category=ScanCategory.PRICE_ACTION,
    criteria=[
        _criterion("dist_52w_low", Operator.LTE, 0.5),  # Within 0.5% of low
        _criterion("change_pct", Operator.LT, 0),
    ],
    is_preset=True,
)

BREAKOUT_SCAN = Scanner(
    name="Volume Breakout",
    description="Price breakout with high volume confirmation",
    category=ScanCategory.PRICE_ACTION,
    criteria=[
        _criterion("change_pct", Operator.GT, 2.0),
        _criterion("relative_volume", Operator.GT, 2.0),
        _criterion("price", Operator.GT, 5.0),
    ],
    is_preset=True,
)


# =============================================================================
# Volume Scans
# =============================================================================

VOLUME_SPIKE_SCAN = Scanner(
    name="Volume Spike",
    description="Stocks with volume > 200% of average",
    category=ScanCategory.VOLUME,
    criteria=[
        _criterion("relative_volume", Operator.GT, 2.0),
        _criterion("volume", Operator.GT, 1000000),
    ],
    is_preset=True,
)

UNUSUAL_VOLUME_SCAN = Scanner(
    name="Unusual Volume",
    description="Extreme volume activity (>300% average)",
    category=ScanCategory.VOLUME,
    criteria=[
        _criterion("relative_volume", Operator.GT, 3.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

HIGH_DOLLAR_VOLUME = Scanner(
    name="High Dollar Volume",
    description="Stocks with high dollar volume",
    category=ScanCategory.VOLUME,
    criteria=[
        _criterion("dollar_volume", Operator.GT, 50000000),
    ],
    is_preset=True,
)


# =============================================================================
# Technical Scans
# =============================================================================

RSI_OVERSOLD_SCAN = Scanner(
    name="RSI Oversold",
    description="Stocks with RSI below 30",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("rsi", Operator.LT, 30),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

RSI_OVERBOUGHT_SCAN = Scanner(
    name="RSI Overbought",
    description="Stocks with RSI above 70",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("rsi", Operator.GT, 70),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

GOLDEN_CROSS_SCAN = Scanner(
    name="Golden Cross",
    description="50 SMA crossing above 200 SMA",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("sma_50", Operator.CROSSES_ABOVE, 0, compare_field="sma_200"),
    ],
    is_preset=True,
)

DEATH_CROSS_SCAN = Scanner(
    name="Death Cross",
    description="50 SMA crossing below 200 SMA",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("sma_50", Operator.CROSSES_BELOW, 0, compare_field="sma_200"),
    ],
    is_preset=True,
)

MACD_BULLISH_SCAN = Scanner(
    name="MACD Bullish Cross",
    description="MACD crossing above signal line",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("macd", Operator.CROSSES_ABOVE, 0, compare_field="macd_signal"),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

MACD_BEARISH_SCAN = Scanner(
    name="MACD Bearish Cross",
    description="MACD crossing below signal line",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("macd", Operator.CROSSES_BELOW, 0, compare_field="macd_signal"),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

ABOVE_SMA200_SCAN = Scanner(
    name="Above 200 SMA",
    description="Price trading above 200-day moving average",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("dist_sma_200", Operator.GT, 0),
        _criterion("change_pct", Operator.GT, 0),
    ],
    is_preset=True,
)

BELOW_SMA200_SCAN = Scanner(
    name="Below 200 SMA",
    description="Price trading below 200-day moving average",
    category=ScanCategory.TECHNICAL,
    criteria=[
        _criterion("dist_sma_200", Operator.LT, 0),
        _criterion("change_pct", Operator.LT, 0),
    ],
    is_preset=True,
)


# =============================================================================
# Momentum Scans
# =============================================================================

BIG_GAINERS_SCAN = Scanner(
    name="Big Gainers (>5%)",
    description="Stocks up more than 5% today",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.GT, 5.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

BIG_LOSERS_SCAN = Scanner(
    name="Big Losers (>5%)",
    description="Stocks down more than 5% today",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.LT, -5.0),
        _criterion("volume", Operator.GT, 500000),
    ],
    is_preset=True,
)

MOMENTUM_LEADERS_SCAN = Scanner(
    name="Momentum Leaders",
    description="High momentum stocks with strong price action",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("change_pct", Operator.GT, 3.0),
        _criterion("relative_volume", Operator.GT, 1.5),
        _criterion("rsi", Operator.BETWEEN, (50, 80)),
    ],
    is_preset=True,
)

REVERSAL_CANDIDATES_SCAN = Scanner(
    name="Reversal Candidates",
    description="Oversold stocks showing signs of reversal",
    category=ScanCategory.MOMENTUM,
    criteria=[
        _criterion("rsi", Operator.LT, 35),
        _criterion("change_pct", Operator.GT, 1.0),
        _criterion("relative_volume", Operator.GT, 1.5),
    ],
    is_preset=True,
)


# =============================================================================
# All Preset Scanners
# =============================================================================

PRESET_SCANNERS = {
    # Price Action
    "gap_up": GAP_UP_SCAN,
    "gap_down": GAP_DOWN_SCAN,
    "new_high": NEW_HIGH_SCAN,
    "new_low": NEW_LOW_SCAN,
    "breakout": BREAKOUT_SCAN,
    
    # Volume
    "volume_spike": VOLUME_SPIKE_SCAN,
    "unusual_volume": UNUSUAL_VOLUME_SCAN,
    "high_dollar_volume": HIGH_DOLLAR_VOLUME,
    
    # Technical
    "rsi_oversold": RSI_OVERSOLD_SCAN,
    "rsi_overbought": RSI_OVERBOUGHT_SCAN,
    "golden_cross": GOLDEN_CROSS_SCAN,
    "death_cross": DEATH_CROSS_SCAN,
    "macd_bullish": MACD_BULLISH_SCAN,
    "macd_bearish": MACD_BEARISH_SCAN,
    "above_sma200": ABOVE_SMA200_SCAN,
    "below_sma200": BELOW_SMA200_SCAN,
    
    # Momentum
    "big_gainers": BIG_GAINERS_SCAN,
    "big_losers": BIG_LOSERS_SCAN,
    "momentum_leaders": MOMENTUM_LEADERS_SCAN,
    "reversal_candidates": REVERSAL_CANDIDATES_SCAN,
}


def get_preset_scanner(name: str) -> Scanner:
    """Get a preset scanner by name."""
    return PRESET_SCANNERS.get(name)


def get_presets_by_category(category: ScanCategory) -> list[Scanner]:
    """Get preset scanners by category."""
    return [s for s in PRESET_SCANNERS.values() if s.category == category]


def get_all_presets() -> list[Scanner]:
    """Get all preset scanners."""
    return list(PRESET_SCANNERS.values())
