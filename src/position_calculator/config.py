"""Position Calculator Configuration.

Enums and configuration dataclasses for trade-level position sizing,
portfolio heat tracking, and drawdown management.
"""

from dataclasses import dataclass, field
from enum import Enum


class StopType(str, Enum):
    """Stop-loss calculation method."""
    FIXED = "fixed"
    ATR_BASED = "atr_based"
    PERCENT = "percent"


class InstrumentType(str, Enum):
    """Tradeable instrument types."""
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"


class SizingMethod(str, Enum):
    """Position sizing methodology."""
    FIXED_RISK = "fixed_risk"
    KELLY = "kelly"
    HALF_KELLY = "half_kelly"
    QUARTER_KELLY = "quarter_kelly"
    FIXED_DOLLAR = "fixed_dollar"
    FIXED_SHARES = "fixed_shares"


class DrawdownAction(str, Enum):
    """Action when drawdown limit is approached."""
    NONE = "none"
    REDUCE_SIZE = "reduce_size"
    BLOCK_NEW = "block_new"
    ALERT_ONLY = "alert_only"


# Contract multipliers by instrument type
DEFAULT_MULTIPLIERS: dict[str, int] = {
    "stock": 1,
    "option": 100,
    "future": 1,  # Varies by contract; override per-instrument
}


@dataclass
class SizingConfig:
    """Configuration for position sizing."""
    default_risk_pct: float = 1.0         # Default 1% risk per trade
    max_risk_pct: float = 3.0             # Max 3% risk per trade
    max_position_pct: float = 15.0        # Max 15% of account in one position
    default_sizing_method: SizingMethod = SizingMethod.FIXED_RISK
    round_down: bool = True               # Always round shares down
    min_position_value: float = 100.0     # Minimum $100 per position


@dataclass
class KellyConfig:
    """Configuration for Kelly Criterion sizing."""
    kelly_fraction: float = 0.25          # Quarter-Kelly by default
    min_win_rate: float = 0.40            # Minimum win rate to apply Kelly
    min_trades: int = 30                  # Minimum trade history
    max_kelly_pct: float = 10.0           # Cap Kelly at 10%


@dataclass
class HeatConfig:
    """Configuration for portfolio heat tracking."""
    max_heat_pct: float = 6.0             # Max 6% total portfolio heat
    warn_heat_pct: float = 4.0            # Warn at 4%
    include_unrealized: bool = True       # Include unrealized risk in heat


@dataclass
class DrawdownConfig:
    """Configuration for drawdown monitoring."""
    max_drawdown_pct: float = 10.0        # Max 10% drawdown
    warn_drawdown_pct: float = 7.0        # Warn at 7%
    reduce_at_pct: float = 8.0            # Reduce size at 8%
    size_reduction_factor: float = 0.5    # Cut size by 50% when reducing
    block_at_pct: float = 10.0            # Block new trades at 10%
    drawdown_action: DrawdownAction = DrawdownAction.REDUCE_SIZE


@dataclass
class PositionCalculatorConfig:
    """Top-level configuration for the position calculator."""
    sizing: SizingConfig = field(default_factory=SizingConfig)
    kelly: KellyConfig = field(default_factory=KellyConfig)
    heat: HeatConfig = field(default_factory=HeatConfig)
    drawdown: DrawdownConfig = field(default_factory=DrawdownConfig)


DEFAULT_SIZING_CONFIG = SizingConfig()
DEFAULT_KELLY_CONFIG = KellyConfig()
DEFAULT_HEAT_CONFIG = HeatConfig()
DEFAULT_DRAWDOWN_CONFIG = DrawdownConfig()
DEFAULT_CONFIG = PositionCalculatorConfig()
