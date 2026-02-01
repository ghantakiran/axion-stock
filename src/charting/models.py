"""Technical Charting Data Models."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from src.charting.config import PatternType, TrendDirection, SRType, CrossoverType


@dataclass
class ChartPattern:
    """Detected chart pattern."""
    pattern_type: PatternType = PatternType.DOUBLE_TOP
    start_idx: int = 0
    end_idx: int = 0
    neckline: float = 0.0
    target_price: float = 0.0
    confidence: float = 0.0
    confirmed: bool = False
    symbol: str = ""
    date: Optional[date] = None

    @property
    def pattern_height(self) -> float:
        """Distance from neckline to target."""
        return abs(self.target_price - self.neckline)

    @property
    def is_bullish(self) -> bool:
        return self.pattern_type in (
            PatternType.DOUBLE_BOTTOM,
            PatternType.INVERSE_HEAD_AND_SHOULDERS,
            PatternType.ASCENDING_TRIANGLE,
        )

    @property
    def is_bearish(self) -> bool:
        return self.pattern_type in (
            PatternType.DOUBLE_TOP,
            PatternType.HEAD_AND_SHOULDERS,
            PatternType.DESCENDING_TRIANGLE,
        )

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type.value,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "neckline": round(self.neckline, 4),
            "target_price": round(self.target_price, 4),
            "confidence": round(self.confidence, 3),
            "confirmed": self.confirmed,
            "is_bullish": self.is_bullish,
            "is_bearish": self.is_bearish,
        }


@dataclass
class TrendAnalysis:
    """Trend assessment."""
    direction: TrendDirection = TrendDirection.SIDEWAYS
    strength: float = 0.0
    slope: float = 0.0
    r_squared: float = 0.0
    ma_short: float = 0.0
    ma_medium: float = 0.0
    ma_long: float = 0.0
    symbol: str = ""
    date: Optional[date] = None

    @property
    def ma_aligned_bullish(self) -> bool:
        """Short > medium > long MA alignment."""
        if self.ma_short == 0 or self.ma_medium == 0 or self.ma_long == 0:
            return False
        return self.ma_short > self.ma_medium > self.ma_long

    @property
    def ma_aligned_bearish(self) -> bool:
        """Short < medium < long MA alignment."""
        if self.ma_short == 0 or self.ma_medium == 0 or self.ma_long == 0:
            return False
        return self.ma_short < self.ma_medium < self.ma_long

    def to_dict(self) -> dict:
        return {
            "direction": self.direction.value,
            "strength": round(self.strength, 2),
            "slope": round(self.slope, 6),
            "r_squared": round(self.r_squared, 4),
            "ma_short": round(self.ma_short, 4),
            "ma_medium": round(self.ma_medium, 4),
            "ma_long": round(self.ma_long, 4),
            "ma_aligned_bullish": self.ma_aligned_bullish,
            "ma_aligned_bearish": self.ma_aligned_bearish,
        }


@dataclass
class MACrossover:
    """Moving average crossover event."""
    crossover_type: CrossoverType = CrossoverType.GOLDEN_CROSS
    fast_window: int = 0
    slow_window: int = 0
    price_at_cross: float = 0.0
    idx: int = 0
    symbol: str = ""
    date: Optional[date] = None


@dataclass
class SRLevel:
    """Support or resistance level."""
    level_type: SRType = SRType.SUPPORT
    price: float = 0.0
    touches: int = 0
    strength: float = 0.0
    last_tested_idx: int = 0
    symbol: str = ""
    date: Optional[date] = None

    @property
    def is_strong(self) -> bool:
        """Level with 3+ touches and strength > 0.6."""
        return self.touches >= 3 and self.strength > 0.6

    def to_dict(self) -> dict:
        return {
            "level_type": self.level_type.value,
            "price": round(self.price, 4),
            "touches": self.touches,
            "strength": round(self.strength, 3),
            "is_strong": self.is_strong,
        }


@dataclass
class FibonacciLevels:
    """Fibonacci retracement and extension levels."""
    swing_high: float = 0.0
    swing_low: float = 0.0
    swing_high_idx: int = 0
    swing_low_idx: int = 0
    retracements: dict[float, float] = field(default_factory=dict)
    extensions: dict[float, float] = field(default_factory=dict)
    is_uptrend: bool = True
    symbol: str = ""
    date: Optional[date] = None

    @property
    def swing_range(self) -> float:
        return abs(self.swing_high - self.swing_low)

    def nearest_retracement(self, price: float) -> Optional[tuple[float, float]]:
        """Find nearest retracement level to price.

        Returns:
            (fib_ratio, fib_price) or None.
        """
        if not self.retracements:
            return None
        closest = min(
            self.retracements.items(),
            key=lambda x: abs(x[1] - price),
        )
        return closest

    def to_dict(self) -> dict:
        return {
            "swing_high": round(self.swing_high, 4),
            "swing_low": round(self.swing_low, 4),
            "swing_range": round(self.swing_range, 4),
            "is_uptrend": self.is_uptrend,
            "retracements": {
                str(k): round(v, 4) for k, v in self.retracements.items()
            },
            "extensions": {
                str(k): round(v, 4) for k, v in self.extensions.items()
            },
        }
