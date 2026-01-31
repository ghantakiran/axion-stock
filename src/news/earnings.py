"""Earnings Calendar Management.

Tracks earnings announcements, estimates, actuals, and surprises.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
import logging

from src.news.config import (
    ReportTime,
    EarningsConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
)
from src.news.models import EarningsEvent

logger = logging.getLogger(__name__)


class EarningsCalendar:
    """Manages earnings calendar and tracking.
    
    Features:
    - Upcoming earnings calendar
    - Historical earnings with beat/miss tracking
    - Earnings surprise analysis
    - Portfolio earnings view
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._earnings_config = self.config.earnings
        self._events: dict[str, EarningsEvent] = {}  # event_id -> event
        self._symbol_index: dict[str, list[str]] = {}  # symbol -> event_ids (chronological)
    
    def add_event(self, event: EarningsEvent) -> EarningsEvent:
        """Add an earnings event.
        
        Args:
            event: EarningsEvent to add.
            
        Returns:
            The added event.
        """
        self._events[event.event_id] = event
        
        if event.symbol not in self._symbol_index:
            self._symbol_index[event.symbol] = []
        
        # Insert in chronological order
        idx = 0
        for i, eid in enumerate(self._symbol_index[event.symbol]):
            existing = self._events[eid]
            if event.report_date < existing.report_date:
                break
            idx = i + 1
        
        self._symbol_index[event.symbol].insert(idx, event.event_id)
        
        logger.debug(f"Added earnings event: {event.symbol} on {event.report_date}")
        return event
    
    def get_event(self, event_id: str) -> Optional[EarningsEvent]:
        """Get an earnings event by ID."""
        return self._events.get(event_id)
    
    def get_upcoming(
        self,
        days: int = 14,
        symbols: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[EarningsEvent]:
        """Get upcoming earnings events.
        
        Args:
            days: Days to look ahead.
            symbols: Filter by symbols.
            limit: Maximum events to return.
            
        Returns:
            List of upcoming earnings events.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = []
        for event in self._events.values():
            if event.report_date < today or event.report_date > end_date:
                continue
            if symbols and event.symbol not in symbols:
                continue
            events.append(event)
        
        # Sort by date
        events.sort(key=lambda e: (e.report_date, e.symbol))
        return events[:limit]
    
    def get_today(self) -> list[EarningsEvent]:
        """Get earnings events for today."""
        today = date.today()
        return [e for e in self._events.values() if e.report_date == today]
    
    def get_this_week(self) -> list[EarningsEvent]:
        """Get earnings events for this week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        events = []
        for event in self._events.values():
            if week_start <= event.report_date <= week_end:
                events.append(event)
        
        events.sort(key=lambda e: (e.report_date, e.symbol))
        return events
    
    def get_for_symbol(
        self,
        symbol: str,
        quarters: int = 8,
    ) -> list[EarningsEvent]:
        """Get earnings history for a symbol.
        
        Args:
            symbol: Stock symbol.
            quarters: Number of quarters to include.
            
        Returns:
            List of earnings events (most recent first).
        """
        event_ids = self._symbol_index.get(symbol, [])
        events = [self._events[eid] for eid in event_ids]
        
        # Return most recent first
        events.sort(key=lambda e: e.report_date, reverse=True)
        return events[:quarters]
    
    def get_portfolio_earnings(
        self,
        symbols: list[str],
        days: int = 30,
    ) -> list[EarningsEvent]:
        """Get upcoming earnings for portfolio symbols.
        
        Args:
            symbols: Portfolio symbols.
            days: Days to look ahead.
            
        Returns:
            List of upcoming earnings for portfolio.
        """
        return self.get_upcoming(days=days, symbols=symbols)
    
    def update_actuals(
        self,
        event_id: str,
        eps_actual: float,
        revenue_actual: Optional[float] = None,
        price_before: Optional[float] = None,
        price_after: Optional[float] = None,
    ) -> Optional[EarningsEvent]:
        """Update an event with actual results.
        
        Args:
            event_id: Event to update.
            eps_actual: Actual EPS.
            revenue_actual: Actual revenue.
            price_before: Price before earnings.
            price_after: Price after earnings.
            
        Returns:
            Updated event or None if not found.
        """
        event = self._events.get(event_id)
        if not event:
            return None
        
        event.eps_actual = eps_actual
        if revenue_actual is not None:
            event.revenue_actual = revenue_actual
        if price_before is not None:
            event.price_before = price_before
        if price_after is not None:
            event.price_after = price_after
        
        logger.info(
            f"Updated {event.symbol} earnings: EPS actual = {eps_actual}, "
            f"surprise = {event.eps_surprise}"
        )
        return event
    
    def get_beats(
        self,
        days: int = 90,
        min_surprise_pct: float = 0.0,
    ) -> list[EarningsEvent]:
        """Get recent earnings beats.
        
        Args:
            days: Days to look back.
            min_surprise_pct: Minimum surprise percentage.
            
        Returns:
            List of earnings beats.
        """
        cutoff = date.today() - timedelta(days=days)
        
        beats = []
        for event in self._events.values():
            if event.report_date < cutoff:
                continue
            if not event.is_reported:
                continue
            if event.is_beat and (event.eps_surprise_pct or 0) >= min_surprise_pct:
                beats.append(event)
        
        beats.sort(key=lambda e: e.eps_surprise_pct or 0, reverse=True)
        return beats
    
    def get_misses(
        self,
        days: int = 90,
        max_surprise_pct: float = 0.0,
    ) -> list[EarningsEvent]:
        """Get recent earnings misses.
        
        Args:
            days: Days to look back.
            max_surprise_pct: Maximum (most negative) surprise percentage.
            
        Returns:
            List of earnings misses.
        """
        cutoff = date.today() - timedelta(days=days)
        
        misses = []
        for event in self._events.values():
            if event.report_date < cutoff:
                continue
            if not event.is_reported:
                continue
            if not event.is_beat and (event.eps_surprise_pct or 0) <= max_surprise_pct:
                misses.append(event)
        
        misses.sort(key=lambda e: e.eps_surprise_pct or 0)
        return misses
    
    def get_surprise_stats(self, symbol: str) -> dict:
        """Get earnings surprise statistics for a symbol.
        
        Returns:
            Dict with beat rate, average surprise, etc.
        """
        events = self.get_for_symbol(symbol)
        reported = [e for e in events if e.is_reported]
        
        if not reported:
            return {
                "symbol": symbol,
                "total_quarters": 0,
                "beat_rate": None,
                "avg_surprise_pct": None,
            }
        
        beats = [e for e in reported if e.is_beat]
        surprises = [e.eps_surprise_pct for e in reported if e.eps_surprise_pct is not None]
        
        return {
            "symbol": symbol,
            "total_quarters": len(reported),
            "beats": len(beats),
            "misses": len(reported) - len(beats),
            "beat_rate": len(beats) / len(reported) * 100,
            "avg_surprise_pct": sum(surprises) / len(surprises) if surprises else None,
            "max_beat_pct": max(surprises) if surprises else None,
            "max_miss_pct": min(surprises) if surprises else None,
        }
    
    def get_calendar_view(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, list[EarningsEvent]]:
        """Get earnings organized by date for calendar view.
        
        Args:
            start_date: Calendar start.
            end_date: Calendar end.
            
        Returns:
            Dict mapping dates to events.
        """
        calendar: dict[date, list[EarningsEvent]] = {}
        
        current = start_date
        while current <= end_date:
            calendar[current] = []
            current += timedelta(days=1)
        
        for event in self._events.values():
            if start_date <= event.report_date <= end_date:
                calendar[event.report_date].append(event)
        
        # Sort each day's events
        for d in calendar:
            calendar[d].sort(key=lambda e: e.symbol)
        
        return calendar
