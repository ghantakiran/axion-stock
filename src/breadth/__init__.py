"""Market Breadth Analytics Module.

Advance-decline analysis, McClellan Oscillator, breadth thrust
detection, market health scoring, and sector breadth breakdowns.

Example:
    from src.breadth import BreadthIndicators, AdvanceDecline, HealthScorer
    from datetime import date

    indicators = BreadthIndicators()
    snapshot = indicators.process_day(AdvanceDecline(
        date=date.today(), advancing=2200, declining=1300, unchanged=500,
    ))
    print(f"AD Line: {snapshot.cumulative_ad_line}")

    scorer = HealthScorer()
    health = scorer.score(snapshot)
    print(f"Market Health: {health.level.value} ({health.score}/100)")
"""

from src.breadth.config import (
    BreadthIndicator,
    MarketHealthLevel,
    BreadthSignal,
    BreadthTimeframe,
    GICS_SECTORS,
    McClellanConfig,
    ThrustConfig,
    HealthConfig,
    NewHighsLowsConfig,
    BreadthConfig,
    DEFAULT_MCCLELLAN_CONFIG,
    DEFAULT_THRUST_CONFIG,
    DEFAULT_HEALTH_CONFIG,
    DEFAULT_NHNL_CONFIG,
    DEFAULT_BREADTH_CONFIG,
)

from src.breadth.models import (
    AdvanceDecline,
    NewHighsLows,
    McClellanData,
    BreadthThrustData,
    BreadthSnapshot,
    SectorBreadth,
    MarketHealth,
)

from src.breadth.indicators import BreadthIndicators
from src.breadth.health import HealthScorer
from src.breadth.sector import SectorBreadthAnalyzer

__all__ = [
    # Config
    "BreadthIndicator",
    "MarketHealthLevel",
    "BreadthSignal",
    "BreadthTimeframe",
    "GICS_SECTORS",
    "McClellanConfig",
    "ThrustConfig",
    "HealthConfig",
    "NewHighsLowsConfig",
    "BreadthConfig",
    "DEFAULT_MCCLELLAN_CONFIG",
    "DEFAULT_THRUST_CONFIG",
    "DEFAULT_HEALTH_CONFIG",
    "DEFAULT_NHNL_CONFIG",
    "DEFAULT_BREADTH_CONFIG",
    # Models
    "AdvanceDecline",
    "NewHighsLows",
    "McClellanData",
    "BreadthThrustData",
    "BreadthSnapshot",
    "SectorBreadth",
    "MarketHealth",
    # Components
    "BreadthIndicators",
    "HealthScorer",
    "SectorBreadthAnalyzer",
]
