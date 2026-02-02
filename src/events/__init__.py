"""Event-Driven Analytics.

Earnings event modeling, M&A probability scoring, corporate action
tracking, and event-driven signal generation.
"""

from src.events.config import (
    EventType,
    EarningsResult,
    DealStatus,
    SignalStrength,
    EarningsConfig,
    MergerConfig,
    CorporateConfig,
    SignalConfig,
    EventConfig,
    DEFAULT_EVENT_CONFIG,
)

from src.events.models import (
    EarningsEvent,
    EarningsSummary,
    MergerEvent,
    CorporateAction,
    DividendSummary,
    EventSignal,
    CompositeEventScore,
)

from src.events.earnings import EarningsAnalyzer
from src.events.mergers import MergerAnalyzer
from src.events.corporate import CorporateActionTracker
from src.events.signals import EventSignalGenerator

__all__ = [
    # Config
    "EventType",
    "EarningsResult",
    "DealStatus",
    "SignalStrength",
    "EarningsConfig",
    "MergerConfig",
    "CorporateConfig",
    "SignalConfig",
    "EventConfig",
    "DEFAULT_EVENT_CONFIG",
    # Models
    "EarningsEvent",
    "EarningsSummary",
    "MergerEvent",
    "CorporateAction",
    "DividendSummary",
    "EventSignal",
    "CompositeEventScore",
    # Analyzers
    "EarningsAnalyzer",
    "MergerAnalyzer",
    "CorporateActionTracker",
    "EventSignalGenerator",
]
