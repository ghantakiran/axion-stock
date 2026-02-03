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
from src.events.scoring import (
    EarningsQualityScore,
    GuidanceRevision,
    EarningsScorecardSummary,
    EarningsScorer,
)
from src.events.probability import (
    DealRiskFactors,
    CompletionEstimate,
    HistoricalRates,
    DealProbabilityModeler,
)
from src.events.impact import (
    DividendImpact,
    SplitImpact,
    BuybackImpact,
    SpinoffImpact,
    ImpactSummary,
    CorporateActionImpactEstimator,
)
from src.events.calendar import (
    CalendarEvent,
    EventDensity,
    EventCluster,
    CatalystTimeline,
    CrossEventInteraction,
    EventCalendarAnalyzer,
)

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
    # Earnings Scoring
    "EarningsQualityScore",
    "GuidanceRevision",
    "EarningsScorecardSummary",
    "EarningsScorer",
    # M&A Probability
    "DealRiskFactors",
    "CompletionEstimate",
    "HistoricalRates",
    "DealProbabilityModeler",
    # Corporate Action Impact
    "DividendImpact",
    "SplitImpact",
    "BuybackImpact",
    "SpinoffImpact",
    "ImpactSummary",
    "CorporateActionImpactEstimator",
    # Event Calendar
    "CalendarEvent",
    "EventDensity",
    "EventCluster",
    "CatalystTimeline",
    "CrossEventInteraction",
    "EventCalendarAnalyzer",
]
