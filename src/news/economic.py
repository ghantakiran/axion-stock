"""Economic Calendar Management.

Tracks economic events, releases, and market impact.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
import logging

from src.news.config import (
    EconomicCategory,
    EventImportance,
    EconomicConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
    MAJOR_ECONOMIC_EVENTS,
)
from src.news.models import EconomicEvent

logger = logging.getLogger(__name__)


class EconomicCalendar:
    """Manages economic calendar and events.
    
    Features:
    - Upcoming economic releases
    - Historical data with actual vs forecast
    - Impact analysis
    - Country filtering
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._econ_config = self.config.economic
        self._events: dict[str, EconomicEvent] = {}  # event_id -> event
        self._category_index: dict[EconomicCategory, set[str]] = {}
    
    def add_event(self, event: EconomicEvent) -> EconomicEvent:
        """Add an economic event.
        
        Args:
            event: EconomicEvent to add.
            
        Returns:
            The added event.
        """
        self._events[event.event_id] = event
        
        if event.category not in self._category_index:
            self._category_index[event.category] = set()
        self._category_index[event.category].add(event.event_id)
        
        logger.debug(f"Added economic event: {event.name} on {event.release_date}")
        return event
    
    def get_event(self, event_id: str) -> Optional[EconomicEvent]:
        """Get an economic event by ID."""
        return self._events.get(event_id)
    
    def get_upcoming(
        self,
        days: int = 14,
        countries: Optional[list[str]] = None,
        categories: Optional[list[EconomicCategory]] = None,
        min_importance: Optional[EventImportance] = None,
        limit: int = 50,
    ) -> list[EconomicEvent]:
        """Get upcoming economic events.
        
        Args:
            days: Days to look ahead.
            countries: Filter by countries.
            categories: Filter by categories.
            min_importance: Minimum importance level.
            limit: Maximum events to return.
            
        Returns:
            List of upcoming economic events.
        """
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=days)
        
        # Importance ordering for filtering
        importance_order = {
            EventImportance.HIGH: 3,
            EventImportance.MEDIUM: 2,
            EventImportance.LOW: 1,
        }
        min_level = importance_order.get(min_importance, 0) if min_importance else 0
        
        events = []
        for event in self._events.values():
            if event.release_date < now or event.release_date > end_time:
                continue
            
            if countries and event.country not in countries:
                continue
            
            if categories and event.category not in categories:
                continue
            
            if importance_order.get(event.importance, 0) < min_level:
                continue
            
            events.append(event)
        
        # Sort by date, then importance
        events.sort(
            key=lambda e: (e.release_date, -importance_order.get(e.importance, 0))
        )
        return events[:limit]
    
    def get_today(self, country: str = "US") -> list[EconomicEvent]:
        """Get economic events for today."""
        today = date.today()
        
        events = []
        for event in self._events.values():
            if event.release_date.date() == today and event.country == country:
                events.append(event)
        
        events.sort(key=lambda e: e.release_date)
        return events
    
    def get_this_week(
        self,
        countries: Optional[list[str]] = None,
        high_importance_only: bool = False,
    ) -> list[EconomicEvent]:
        """Get economic events for this week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        events = []
        for event in self._events.values():
            event_date = event.release_date.date()
            if week_start <= event_date <= week_end:
                if countries and event.country not in countries:
                    continue
                if high_importance_only and event.importance != EventImportance.HIGH:
                    continue
                events.append(event)
        
        events.sort(key=lambda e: e.release_date)
        return events
    
    def get_by_category(
        self,
        category: EconomicCategory,
        days: int = 30,
    ) -> list[EconomicEvent]:
        """Get events by category.
        
        Args:
            category: Event category.
            days: Days to look back/forward.
            
        Returns:
            List of events in category.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        end = now + timedelta(days=days)
        
        event_ids = self._category_index.get(category, set())
        events = []
        
        for eid in event_ids:
            event = self._events.get(eid)
            if event and start <= event.release_date <= end:
                events.append(event)
        
        events.sort(key=lambda e: e.release_date)
        return events
    
    def get_fomc_meetings(self, year: Optional[int] = None) -> list[EconomicEvent]:
        """Get FOMC meeting dates.
        
        Args:
            year: Filter by year.
            
        Returns:
            List of FOMC events.
        """
        events = []
        for event in self._events.values():
            if "fomc" in event.name.lower() or "fed" in event.name.lower():
                if year is None or event.release_date.year == year:
                    events.append(event)
        
        events.sort(key=lambda e: e.release_date)
        return events
    
    def update_actual(
        self,
        event_id: str,
        actual: float,
        market_impact: Optional[str] = None,
    ) -> Optional[EconomicEvent]:
        """Update an event with actual value.
        
        Args:
            event_id: Event to update.
            actual: Actual value.
            market_impact: Market impact assessment.
            
        Returns:
            Updated event or None if not found.
        """
        event = self._events.get(event_id)
        if not event:
            return None
        
        event.actual = actual
        if market_impact:
            event.market_impact = market_impact
        
        logger.info(
            f"Updated {event.name}: actual = {actual}, "
            f"surprise = {event.surprise}"
        )
        return event
    
    def get_surprise_history(
        self,
        event_name: str,
        limit: int = 12,
    ) -> list[EconomicEvent]:
        """Get historical releases for an event type.
        
        Args:
            event_name: Event name to match.
            limit: Maximum events to return.
            
        Returns:
            Historical events (most recent first).
        """
        name_lower = event_name.lower()
        
        events = []
        for event in self._events.values():
            if name_lower in event.name.lower() and event.is_released:
                events.append(event)
        
        events.sort(key=lambda e: e.release_date, reverse=True)
        return events[:limit]
    
    def get_high_impact_events(self, days: int = 7) -> list[EconomicEvent]:
        """Get upcoming high-impact events.
        
        Args:
            days: Days to look ahead.
            
        Returns:
            High importance events.
        """
        return self.get_upcoming(
            days=days,
            min_importance=EventImportance.HIGH,
        )
    
    def get_calendar_view(
        self,
        start_date: date,
        end_date: date,
        country: str = "US",
    ) -> dict[date, list[EconomicEvent]]:
        """Get events organized by date for calendar view.
        
        Args:
            start_date: Calendar start.
            end_date: Calendar end.
            country: Country filter.
            
        Returns:
            Dict mapping dates to events.
        """
        calendar: dict[date, list[EconomicEvent]] = {}
        
        current = start_date
        while current <= end_date:
            calendar[current] = []
            current += timedelta(days=1)
        
        for event in self._events.values():
            event_date = event.release_date.date()
            if start_date <= event_date <= end_date:
                if event.country == country:
                    calendar[event_date].append(event)
        
        # Sort each day's events by time
        for d in calendar:
            calendar[d].sort(key=lambda e: e.release_date)
        
        return calendar
    
    def is_major_event(self, event: EconomicEvent) -> bool:
        """Check if event is a major market-moving event."""
        return any(
            major.lower() in event.name.lower()
            for major in MAJOR_ECONOMIC_EVENTS
        )
