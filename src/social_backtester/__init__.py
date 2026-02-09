"""Social Signal Backtester (PRD-161).

Validates social signals against historical price data. Archives social
signals with timestamps, replays them through the backtesting engine,
and measures predictiveness via outcome tracking and correlation analysis.
"""
from src.social_backtester.config import (
    BacktesterConfig, OutcomeHorizon, ValidationMethod,
)
from src.social_backtester.archive import (
    SignalArchive, ArchivedSignal, ArchiveStats,
)
from src.social_backtester.validator import (
    OutcomeValidator, SignalOutcome, ValidationReport,
)
from src.social_backtester.correlation import (
    CorrelationAnalyzer, CorrelationResult, LagAnalysis,
)
from src.social_backtester.strategy import (
    SocialSignalStrategy, StrategyConfig, SocialBacktestRunner,
    SocialBacktestResult,
)

__all__ = [
    "BacktesterConfig", "OutcomeHorizon", "ValidationMethod",
    "SignalArchive", "ArchivedSignal", "ArchiveStats",
    "OutcomeValidator", "SignalOutcome", "ValidationReport",
    "CorrelationAnalyzer", "CorrelationResult", "LagAnalysis",
    "SocialSignalStrategy", "StrategyConfig", "SocialBacktestRunner",
    "SocialBacktestResult",
]
