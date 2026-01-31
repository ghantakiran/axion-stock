"""Economic Calendar Management.

Track and filter economic events.
"""

from datetime import datetime, date, time, timedelta, timezone
from typing import Optional
import logging

from src.economic.config import (
    ImpactLevel,
    EventCategory,
    Country,
    CalendarConfig,
    DEFAULT_CALENDAR_CONFIG,
    HIGH_IMPACT_EVENTS,
)
from src.economic.models import EconomicEvent

logger = logging.getLogger(__name__)


class EconomicCalendar:
    """Manages economic calendar events.
    
    Example:
        calendar = EconomicCalendar()
        
        # Add events
        calendar.add_event(EconomicEvent(
            name="Non-Farm Payrolls",
            release_date=date(2024, 2, 2),
            release_time=time(8, 30),
            impact=ImpactLevel.HIGH,
            forecast=180.0,
            previous=216.0,
        ))
        
        # Get upcoming high-impact events
        events = calendar.get_upcoming(
            days=7,
            min_impact=ImpactLevel.HIGH
        )
    """
    
    def __init__(self, config: Optional[CalendarConfig] = None):
        self.config = config or DEFAULT_CALENDAR_CONFIG
        self._events: dict[str, EconomicEvent] = {}
    
    # =========================================================================
    # Event CRUD
    # =========================================================================
    
    def add_event(self, event: EconomicEvent) -> None:
        """Add an economic event."""
        self._events[event.event_id] = event
    
    def get_event(self, event_id: str) -> Optional[EconomicEvent]:
        """Get event by ID."""
        return self._events.get(event_id)
    
    def update_event(self, event: EconomicEvent) -> None:
        """Update an existing event."""
        if event.event_id in self._events:
            self._events[event.event_id] = event
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        if event_id in self._events:
            del self._events[event_id]
            return True
        return False
    
    def record_release(
        self,
        event_id: str,
        actual: float,
        release_time: Optional[datetime] = None,
    ) -> Optional[EconomicEvent]:
        """Record actual value when event is released."""
        event = self._events.get(event_id)
        if event:
            event.actual = actual
            event.is_released = True
            event.release_timestamp = release_time or datetime.now(timezone.utc)
            return event
        return None
    
    # =========================================================================
    # Calendar Views
    # =========================================================================
    
    def get_day(
        self,
        target_date: date,
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
    ) -> list[EconomicEvent]:
        """Get events for a specific day."""
        events = [
            e for e in self._events.values()
            if e.release_date == target_date
        ]
        
        return self._apply_filters(events, country, min_impact)
    
    def get_week(
        self,
        start_date: Optional[date] = None,
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
    ) -> dict[date, list[EconomicEvent]]:
        """Get events for a week."""
        if start_date is None:
            start_date = date.today()
            # Adjust to Monday
            start_date = start_date - timedelta(days=start_date.weekday())
        
        week_events = {}
        for i in range(7):
            day = start_date + timedelta(days=i)
            week_events[day] = self.get_day(day, country, min_impact)
        
        return week_events
    
    def get_month(
        self,
        year: int,
        month: int,
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
    ) -> dict[date, list[EconomicEvent]]:
        """Get events for a month."""
        from calendar import monthrange
        
        _, days_in_month = monthrange(year, month)
        month_events = {}
        
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            events = self.get_day(d, country, min_impact)
            if events:
                month_events[d] = events
        
        return month_events
    
    def get_upcoming(
        self,
        days: int = 7,
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
        limit: int = 50,
    ) -> list[EconomicEvent]:
        """Get upcoming events."""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = [
            e for e in self._events.values()
            if e.release_date and today <= e.release_date <= end_date
            and not e.is_released
        ]
        
        events = self._apply_filters(events, country, min_impact)
        events.sort(key=lambda e: (e.release_date, e.release_time or time(0, 0)))
        
        return events[:limit]
    
    def get_today(
        self,
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
    ) -> list[EconomicEvent]:
        """Get today's events."""
        return self.get_day(date.today(), country, min_impact)
    
    def get_by_category(
        self,
        category: EventCategory,
        days: int = 30,
    ) -> list[EconomicEvent]:
        """Get events by category."""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = [
            e for e in self._events.values()
            if e.category == category
            and e.release_date
            and today <= e.release_date <= end_date
        ]
        
        events.sort(key=lambda e: e.release_date)
        return events
    
    def get_high_impact(self, days: int = 7) -> list[EconomicEvent]:
        """Get high-impact events."""
        return self.get_upcoming(days=days, min_impact=ImpactLevel.HIGH)
    
    # =========================================================================
    # Filtering
    # =========================================================================
    
    def _apply_filters(
        self,
        events: list[EconomicEvent],
        country: Optional[Country] = None,
        min_impact: Optional[ImpactLevel] = None,
    ) -> list[EconomicEvent]:
        """Apply filters to event list."""
        if country:
            events = [e for e in events if e.country == country]
        
        if min_impact:
            impact_order = {
                ImpactLevel.LOW: 0,
                ImpactLevel.MEDIUM: 1,
                ImpactLevel.HIGH: 2,
            }
            min_level = impact_order[min_impact]
            events = [
                e for e in events
                if impact_order.get(e.impact, 0) >= min_level
            ]
        
        return events
    
    def search(self, query: str) -> list[EconomicEvent]:
        """Search events by name."""
        query_lower = query.lower()
        return [
            e for e in self._events.values()
            if query_lower in e.name.lower()
        ]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_event_count_by_day(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, int]:
        """Get event count per day."""
        counts = {}
        current = start_date
        
        while current <= end_date:
            events = self.get_day(current)
            if events:
                counts[current] = len(events)
            current += timedelta(days=1)
        
        return counts
    
    def get_released_events(
        self,
        days: int = 7,
    ) -> list[EconomicEvent]:
        """Get recently released events."""
        today = date.today()
        start_date = today - timedelta(days=days)
        
        events = [
            e for e in self._events.values()
            if e.is_released
            and e.release_date
            and start_date <= e.release_date <= today
        ]
        
        events.sort(key=lambda e: e.release_timestamp or datetime.min, reverse=True)
        return events


def generate_sample_calendar() -> EconomicCalendar:
    """Generate sample calendar with common US events."""
    calendar = EconomicCalendar()
    today = date.today()
    
    # Sample events for the next 2 weeks
    sample_events = [
        # This week
        EconomicEvent(
            name="Non-Farm Payrolls",
            country=Country.US,
            category=EventCategory.EMPLOYMENT,
            release_date=today + timedelta(days=1),
            release_time=time(8, 30),
            impact=ImpactLevel.HIGH,
            previous=216.0,
            forecast=180.0,
            unit="K",
            description="Change in non-farm employment",
        ),
        EconomicEvent(
            name="Unemployment Rate",
            country=Country.US,
            category=EventCategory.EMPLOYMENT,
            release_date=today + timedelta(days=1),
            release_time=time(8, 30),
            impact=ImpactLevel.HIGH,
            previous=3.7,
            forecast=3.7,
            unit="%",
        ),
        EconomicEvent(
            name="ISM Manufacturing PMI",
            country=Country.US,
            category=EventCategory.MANUFACTURING,
            release_date=today + timedelta(days=2),
            release_time=time(10, 0),
            impact=ImpactLevel.MEDIUM,
            previous=47.4,
            forecast=47.0,
            unit="index",
        ),
        EconomicEvent(
            name="Initial Jobless Claims",
            country=Country.US,
            category=EventCategory.EMPLOYMENT,
            release_date=today + timedelta(days=3),
            release_time=time(8, 30),
            impact=ImpactLevel.MEDIUM,
            previous=218.0,
            forecast=215.0,
            unit="K",
        ),
        # Next week
        EconomicEvent(
            name="CPI",
            country=Country.US,
            category=EventCategory.INFLATION,
            release_date=today + timedelta(days=7),
            release_time=time(8, 30),
            impact=ImpactLevel.HIGH,
            previous=3.4,
            forecast=3.2,
            unit="%",
            description="Consumer Price Index year-over-year",
        ),
        EconomicEvent(
            name="Core CPI",
            country=Country.US,
            category=EventCategory.INFLATION,
            release_date=today + timedelta(days=7),
            release_time=time(8, 30),
            impact=ImpactLevel.HIGH,
            previous=3.9,
            forecast=3.7,
            unit="%",
        ),
        EconomicEvent(
            name="Retail Sales",
            country=Country.US,
            category=EventCategory.CONSUMER,
            release_date=today + timedelta(days=9),
            release_time=time(8, 30),
            impact=ImpactLevel.MEDIUM,
            previous=0.6,
            forecast=0.4,
            unit="%",
        ),
        EconomicEvent(
            name="Fed Interest Rate Decision",
            country=Country.US,
            category=EventCategory.CENTRAL_BANK,
            release_date=today + timedelta(days=10),
            release_time=time(14, 0),
            impact=ImpactLevel.HIGH,
            previous=5.50,
            forecast=5.50,
            unit="%",
            description="Federal Reserve interest rate decision",
        ),
        EconomicEvent(
            name="Housing Starts",
            country=Country.US,
            category=EventCategory.HOUSING,
            release_date=today + timedelta(days=11),
            release_time=time(8, 30),
            impact=ImpactLevel.LOW,
            previous=1.46,
            forecast=1.42,
            unit="M",
        ),
        EconomicEvent(
            name="Michigan Consumer Sentiment",
            country=Country.US,
            category=EventCategory.CONSUMER,
            release_date=today + timedelta(days=12),
            release_time=time(10, 0),
            impact=ImpactLevel.MEDIUM,
            previous=78.8,
            forecast=79.0,
            unit="index",
        ),
    ]
    
    for event in sample_events:
        calendar.add_event(event)
    
    return calendar
