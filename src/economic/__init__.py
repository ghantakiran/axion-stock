"""Economic Calendar Module.

Track economic events, Fed meetings, and market impact.

Example:
    from src.economic import (
        EconomicCalendar, EconomicEvent, ImpactLevel,
        FedWatcher, HistoryAnalyzer, ImpactAnalyzer,
        EconomicAlertManager,
    )
    
    # Create calendar
    calendar = EconomicCalendar()
    
    # Get high-impact events this week
    events = calendar.get_upcoming(days=7, min_impact=ImpactLevel.HIGH)
    
    # Analyze market impact
    analyzer = ImpactAnalyzer()
    for event in events:
        impact = analyzer.analyze_event(event)
        print(f"{event.name}: Expected volatility {impact.expected_volatility}")
"""

from src.economic.config import (
    ImpactLevel,
    EventCategory,
    Country,
    RateDecision,
    AlertTrigger,
    HIGH_IMPACT_EVENTS,
    CATEGORY_INFO,
    TYPICAL_REACTIONS,
    CalendarConfig,
    FedWatchConfig,
    DEFAULT_CALENDAR_CONFIG,
    DEFAULT_FED_CONFIG,
)

from src.economic.models import (
    EconomicEvent,
    HistoricalRelease,
    EventStats,
    FedMeeting,
    RateExpectation,
    EventAlert,
    AlertNotification,
    MarketImpact,
)

from src.economic.calendar import (
    EconomicCalendar,
    generate_sample_calendar,
)

from src.economic.history import (
    HistoryAnalyzer,
    generate_sample_history,
)

from src.economic.fed import (
    FedWatcher,
    generate_sample_fed_data,
)

from src.economic.alerts import (
    EconomicAlertManager,
    create_default_alerts,
)

from src.economic.impact import (
    ImpactAnalyzer,
    SECTOR_SENSITIVITY,
)


__all__ = [
    # Config
    "ImpactLevel",
    "EventCategory",
    "Country",
    "RateDecision",
    "AlertTrigger",
    "HIGH_IMPACT_EVENTS",
    "CATEGORY_INFO",
    "TYPICAL_REACTIONS",
    "CalendarConfig",
    "FedWatchConfig",
    "DEFAULT_CALENDAR_CONFIG",
    "DEFAULT_FED_CONFIG",
    # Models
    "EconomicEvent",
    "HistoricalRelease",
    "EventStats",
    "FedMeeting",
    "RateExpectation",
    "EventAlert",
    "AlertNotification",
    "MarketImpact",
    # Calendar
    "EconomicCalendar",
    "generate_sample_calendar",
    # History
    "HistoryAnalyzer",
    "generate_sample_history",
    # Fed
    "FedWatcher",
    "generate_sample_fed_data",
    # Alerts
    "EconomicAlertManager",
    "create_default_alerts",
    # Impact
    "ImpactAnalyzer",
    "SECTOR_SENSITIVITY",
]
