"""Qullamaggie Momentum Strategies.

Implements Kristjan Kullamagi's 3 core setups:
- Breakout: Flag/consolidation breakout after a prior move
- Episodic Pivot: Earnings gap-up from a flat base
- Parabolic Short: Shorting exhaustion after vertical surges

Also provides 5 scanner presets and shared indicator helpers.
"""

from src.qullamaggie.config import BreakoutConfig, EpisodicPivotConfig, ParabolicShortConfig
from src.qullamaggie.indicators import (
    ConsolidationResult,
    compute_adr,
    compute_atr,
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_adx,
    compute_vwap,
    detect_consolidation,
    detect_higher_lows,
    volume_contraction,
)
from src.qullamaggie.breakout_strategy import QullamaggieBreakoutStrategy
from src.qullamaggie.episodic_pivot_strategy import EpisodicPivotStrategy
from src.qullamaggie.parabolic_short_strategy import ParabolicShortStrategy
from src.qullamaggie.scanner import QULLAMAGGIE_PRESETS

__all__ = [
    "BreakoutConfig",
    "EpisodicPivotConfig",
    "ParabolicShortConfig",
    "ConsolidationResult",
    "compute_adr",
    "compute_atr",
    "compute_sma",
    "compute_ema",
    "compute_rsi",
    "compute_adx",
    "compute_vwap",
    "detect_consolidation",
    "detect_higher_lows",
    "volume_contraction",
    "QullamaggieBreakoutStrategy",
    "EpisodicPivotStrategy",
    "ParabolicShortStrategy",
    "QULLAMAGGIE_PRESETS",
]
