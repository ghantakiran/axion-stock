"""EMA Cloud Signal Engine for autonomous trading bot.

Implements the Ripster EMA Cloud methodology with 4 cloud layers,
10 signal types, multi-timeframe confluence, and conviction scoring.
Core signal generation engine consumed by the Trade Executor (PRD-135),
Options Scalper (PRD-136), and Bot Dashboard (PRD-137).
"""

from src.ema_signals.clouds import (
    CloudConfig,
    CloudState,
    EMACloudCalculator,
    EMASignalConfig,
)
from src.ema_signals.conviction import ConvictionScore, ConvictionScorer
from src.ema_signals.data_feed import DataFeed
from src.ema_signals.detector import SignalDetector, SignalType, TradeSignal
from src.ema_signals.mtf import MTFEngine
from src.ema_signals.scanner import UniverseScanner

# Convenience alias
EMACloudEngine = EMACloudCalculator

__all__ = [
    "CloudConfig",
    "CloudState",
    "EMACloudCalculator",
    "EMACloudEngine",
    "EMASignalConfig",
    "ConvictionScore",
    "ConvictionScorer",
    "DataFeed",
    "SignalDetector",
    "SignalType",
    "TradeSignal",
    "MTFEngine",
    "UniverseScanner",
]
