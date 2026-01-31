"""Earnings Calendar.

Track and manage upcoming earnings events.
"""

from datetime import date, datetime, timedelta
from typing import Optional
import logging

from src.earnings.config import (
    EarningsTime,
    CalendarView,
    CalendarConfig,
    DEFAULT_CALENDAR_CONFIG,
)
from src.earnings.models import EarningsEvent

logger = logging.getLogger(__name__)


class EarningsCalendar:
    """Manages earnings calendar events.
    
    Tracks upcoming earnings dates, provides calendar views,
    and filters by portfolio/watchlist.
    
    Example:
        calendar = EarningsCalendar()
        
        # Add earnings events
        calendar.add_event(EarningsEvent(
            symbol="AAPL",
            report_date=date(2024, 1, 25),
            report_time=EarningsTime.AFTER_MARKET,
        ))
        
        # Get this week's earnings
        events = calendar.get_week(date.today())
    """
    
    def __init__(self, config: Optional[CalendarConfig] = None):
        self.config = config or DEFAULT_CALENDAR_CONFIG
        self._events: dict[str, EarningsEvent] = {}  # event_id -> event
        self._by_symbol: dict[str, list[str]] = {}   # symbol -> event_ids
        self._by_date: dict[date, list[str]] = {}    # date -> event_ids
    
    def add_event(self, event: EarningsEvent) -> None:
        """Add an earnings event."""
        self._events[event.event_id] = event
        
        # Index by symbol
        if event.symbol not in self._by_symbol:
            self._by_symbol[event.symbol] = []
        self._by_symbol[event.symbol].append(event.event_id)
        
        # Index by date
        if event.report_date:
            if event.report_date not in self._by_date:
                self._by_date[event.report_date] = []
            self._by_date[event.report_date].append(event.event_id)
    
    def update_event(self, event: EarningsEvent) -> None:
        """Update an existing event."""
        if event.event_id in self._events:
            old_event = self._events[event.event_id]
            
            # Remove from old date index
            if old_event.report_date and old_event.report_date in self._by_date:
                if event.event_id in self._by_date[old_event.report_date]:
                    self._by_date[old_event.report_date].remove(event.event_id)
            
            # Update
            self._events[event.event_id] = event
            
            # Add to new date index
            if event.report_date:
                if event.report_date not in self._by_date:
                    self._by_date[event.report_date] = []
                self._by_date[event.report_date].append(event.event_id)
    
    def get_event(self, event_id: str) -> Optional[EarningsEvent]:
        """Get event by ID."""
        return self._events.get(event_id)
    
    def get_events_for_symbol(self, symbol: str) -> list[EarningsEvent]:
        """Get all events for a symbol."""
        event_ids = self._by_symbol.get(symbol, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]
    
    def get_next_event(self, symbol: str) -> Optional[EarningsEvent]:
        """Get the next upcoming event for a symbol."""
        events = self.get_events_for_symbol(symbol)
        today = date.today()
        
        future_events = [e for e in events if e.report_date and e.report_date >= today]
        if not future_events:
            return None
        
        return min(future_events, key=lambda e: e.report_date)
    
    def get_day(self, target_date: date) -> list[EarningsEvent]:
        """Get earnings for a specific day."""
        event_ids = self._by_date.get(target_date, [])
        events = [self._events[eid] for eid in event_ids if eid in self._events]
        return sorted(events, key=lambda e: (e.report_time.value, e.symbol))
    
    def get_week(self, week_start: date) -> dict[date, list[EarningsEvent]]:
        """Get earnings for a week.
        
        Args:
            week_start: Start of week (Monday).
            
        Returns:
            Dict of date -> events.
        """
        # Adjust to Monday
        days_since_monday = week_start.weekday()
        monday = week_start - timedelta(days=days_since_monday)
        
        result = {}
        for i in range(5):  # Mon-Fri
            day = monday + timedelta(days=i)
            result[day] = self.get_day(day)
        
        return result
    
    def get_month(self, year: int, month: int) -> dict[date, list[EarningsEvent]]:
        """Get earnings for a month."""
        result = {}
        
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        
        current = start
        while current < end:
            events = self.get_day(current)
            if events:
                result[current] = events
            current += timedelta(days=1)
        
        return result
    
    def get_upcoming(
        self,
        days: int = 7,
        symbols: Optional[list[str]] = None,
    ) -> list[EarningsEvent]:
        """Get upcoming earnings.
        
        Args:
            days: Number of days ahead to look.
            symbols: Filter to specific symbols.
            
        Returns:
            List of upcoming events sorted by date.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = []
        for event in self._events.values():
            if not event.report_date:
                continue
            
            if today <= event.report_date <= end_date:
                if symbols is None or event.symbol in symbols:
                    events.append(event)
        
        return sorted(events, key=lambda e: (e.report_date, e.report_time.value))
    
    def get_by_time(
        self,
        target_date: date,
        report_time: EarningsTime,
    ) -> list[EarningsEvent]:
        """Get earnings by time of day."""
        events = self.get_day(target_date)
        return [e for e in events if e.report_time == report_time]
    
    def get_before_market(self, target_date: date) -> list[EarningsEvent]:
        """Get before-market earnings."""
        return self.get_by_time(target_date, EarningsTime.BEFORE_MARKET)
    
    def get_after_market(self, target_date: date) -> list[EarningsEvent]:
        """Get after-market earnings."""
        return self.get_by_time(target_date, EarningsTime.AFTER_MARKET)
    
    def filter_by_portfolio(
        self,
        events: list[EarningsEvent],
        portfolio_symbols: list[str],
    ) -> list[EarningsEvent]:
        """Filter events to portfolio holdings."""
        return [e for e in events if e.symbol in portfolio_symbols]
    
    def filter_by_watchlist(
        self,
        events: list[EarningsEvent],
        watchlist_symbols: list[str],
    ) -> list[EarningsEvent]:
        """Filter events to watchlist."""
        return [e for e in events if e.symbol in watchlist_symbols]
    
    def count_by_day(self, target_date: date) -> dict[str, int]:
        """Count earnings by time of day."""
        events = self.get_day(target_date)
        
        counts = {
            "before_market": 0,
            "after_market": 0,
            "during_market": 0,
            "unknown": 0,
        }
        
        for event in events:
            if event.report_time == EarningsTime.BEFORE_MARKET:
                counts["before_market"] += 1
            elif event.report_time == EarningsTime.AFTER_MARKET:
                counts["after_market"] += 1
            elif event.report_time == EarningsTime.DURING_MARKET:
                counts["during_market"] += 1
            else:
                counts["unknown"] += 1
        
        return counts
    
    def get_all_events(self) -> list[EarningsEvent]:
        """Get all events."""
        return list(self._events.values())
    
    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
        self._by_symbol.clear()
        self._by_date.clear()


def generate_sample_calendar() -> EarningsCalendar:
    """Generate a sample earnings calendar for testing."""
    calendar = EarningsCalendar()
    today = date.today()
    
    # Sample upcoming earnings
    sample_events = [
        ("AAPL", "Apple Inc.", 2, EarningsTime.AFTER_MARKET, 2.10, 94.5e9),
        ("MSFT", "Microsoft Corp.", 3, EarningsTime.AFTER_MARKET, 2.95, 62.0e9),
        ("GOOGL", "Alphabet Inc.", 4, EarningsTime.AFTER_MARKET, 1.55, 86.0e9),
        ("AMZN", "Amazon.com Inc.", 5, EarningsTime.AFTER_MARKET, 0.85, 165.0e9),
        ("META", "Meta Platforms", 1, EarningsTime.AFTER_MARKET, 4.95, 39.0e9),
        ("NVDA", "NVIDIA Corp.", 6, EarningsTime.AFTER_MARKET, 4.60, 24.0e9),
        ("TSLA", "Tesla Inc.", 2, EarningsTime.AFTER_MARKET, 0.75, 25.0e9),
        ("JPM", "JPMorgan Chase", 0, EarningsTime.BEFORE_MARKET, 3.85, 40.0e9),
        ("V", "Visa Inc.", 3, EarningsTime.AFTER_MARKET, 2.45, 9.0e9),
        ("JNJ", "Johnson & Johnson", 1, EarningsTime.BEFORE_MARKET, 2.65, 21.5e9),
    ]
    
    for symbol, name, days_offset, time, eps_est, rev_est in sample_events:
        event = EarningsEvent(
            symbol=symbol,
            company_name=name,
            report_date=today + timedelta(days=days_offset),
            report_time=time,
            fiscal_quarter="Q4 2025",
            fiscal_year=2025,
            eps_estimate=eps_est,
            revenue_estimate=rev_est,
            is_confirmed=True,
        )
        calendar.add_event(event)
    
    return calendar
