"""Earnings Calendar & Analysis.

Track upcoming earnings, analyze historical patterns,
assess quality metrics, and monitor price reactions.

Example:
    from src.earnings import (
        EarningsCalendar, EarningsEvent, EarningsTime,
        HistoryAnalyzer, QualityAnalyzer, ReactionAnalyzer,
    )
    
    # Create calendar and add events
    calendar = EarningsCalendar()
    calendar.add_event(EarningsEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        report_date=date(2024, 1, 25),
        report_time=EarningsTime.AFTER_MARKET,
        eps_estimate=2.10,
    ))
    
    # Get upcoming earnings
    upcoming = calendar.get_upcoming(days=7)
    for event in upcoming:
        print(f"{event.symbol}: {event.report_date} {event.report_time.value}")
"""

from src.earnings.config import (
    EarningsTime,
    SurpriseType,
    ReactionDirection,
    AlertType,
    QualityRating,
    CalendarView,
    BEAT_THRESHOLD,
    MISS_THRESHOLD,
    BENEISH_THRESHOLD,
    EarningsConfig,
    CalendarConfig,
    DEFAULT_EARNINGS_CONFIG,
    DEFAULT_CALENDAR_CONFIG,
)

from src.earnings.models import (
    EarningsEvent,
    EarningsEstimate,
    QuarterlyEarnings,
    EarningsHistory,
    EarningsQuality,
    EarningsReaction,
    EarningsAlert,
)

from src.earnings.calendar import (
    EarningsCalendar,
    generate_sample_calendar,
)

from src.earnings.estimates import (
    EstimateTracker,
    generate_sample_estimates,
)

from src.earnings.history import (
    HistoryAnalyzer,
    generate_sample_history,
)

from src.earnings.quality import (
    QualityAnalyzer,
    FinancialData,
)

from src.earnings.reactions import ReactionAnalyzer

from src.earnings.alerts import EarningsAlertManager


__all__ = [
    # Config
    "EarningsTime",
    "SurpriseType",
    "ReactionDirection",
    "AlertType",
    "QualityRating",
    "CalendarView",
    "BEAT_THRESHOLD",
    "MISS_THRESHOLD",
    "BENEISH_THRESHOLD",
    "EarningsConfig",
    "CalendarConfig",
    "DEFAULT_EARNINGS_CONFIG",
    "DEFAULT_CALENDAR_CONFIG",
    # Models
    "EarningsEvent",
    "EarningsEstimate",
    "QuarterlyEarnings",
    "EarningsHistory",
    "EarningsQuality",
    "EarningsReaction",
    "EarningsAlert",
    # Calendar
    "EarningsCalendar",
    "generate_sample_calendar",
    # Estimates
    "EstimateTracker",
    "generate_sample_estimates",
    # History
    "HistoryAnalyzer",
    "generate_sample_history",
    # Quality
    "QualityAnalyzer",
    "FinancialData",
    # Reactions
    "ReactionAnalyzer",
    # Alerts
    "EarningsAlertManager",
]
