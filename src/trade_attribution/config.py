"""Configuration for Live Trade Attribution."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DecompositionMethod(str, Enum):
    """P&L decomposition methodology."""

    SIMPLE = "simple"  # Entry quality + market move + exit timing
    VWAP = "vwap"  # VWAP-based entry/exit quality
    IMPLEMENTATION = "implementation"  # Implementation shortfall (Perold)


class TimeWindow(str, Enum):
    """Rolling performance window."""

    LAST_20 = "last_20"
    LAST_50 = "last_50"
    LAST_100 = "last_100"
    LAST_7D = "last_7d"
    LAST_30D = "last_30d"
    LAST_90D = "last_90d"
    ALL_TIME = "all_time"


@dataclass
class AttributionConfig:
    """Configuration for the attribution engine."""

    decomposition_method: DecompositionMethod = DecompositionMethod.SIMPLE
    # Time windows to track
    windows: list[TimeWindow] = field(
        default_factory=lambda: [
            TimeWindow.LAST_20,
            TimeWindow.LAST_50,
            TimeWindow.ALL_TIME,
        ]
    )
    # Signal matching
    max_signal_age_seconds: int = 300  # 5 min max between signal and execution
    match_by_conviction: bool = True
    # Decomposition
    include_costs: bool = True
    slippage_model: str = "sqrt"  # sqrt market impact model
    commission_per_share: float = 0.005
    # Rolling tracker
    decay_factor: float = 0.95  # exponential decay for older trades
    min_trades_for_stats: int = 5
    # Regime awareness
    track_by_regime: bool = True
    regime_source: str = "regime_signals"
