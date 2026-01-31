"""Corporate Events Tracking.

Tracks dividends, splits, M&A, IPOs, and other corporate actions.
"""

from datetime import date, timedelta
from typing import Optional
import logging

from src.news.config import (
    CorporateEventType,
    DividendFrequency,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
)
from src.news.models import DividendEvent, CorporateEvent

logger = logging.getLogger(__name__)


class CorporateEventsTracker:
    """Tracks corporate events and actions.
    
    Features:
    - Dividend calendar (ex-dates, pay dates)
    - Stock splits
    - M&A activity
    - IPO tracking
    """
    
    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or DEFAULT_NEWS_CONFIG
        self._dividends: dict[str, DividendEvent] = {}  # event_id -> event
        self._events: dict[str, CorporateEvent] = {}  # event_id -> event
        self._symbol_dividends: dict[str, list[str]] = {}  # symbol -> dividend_ids
        self._symbol_events: dict[str, list[str]] = {}  # symbol -> event_ids
    
    def add_dividend(self, dividend: DividendEvent) -> DividendEvent:
        """Add a dividend event.
        
        Args:
            dividend: DividendEvent to add.
            
        Returns:
            The added dividend.
        """
        self._dividends[dividend.event_id] = dividend
        
        if dividend.symbol not in self._symbol_dividends:
            self._symbol_dividends[dividend.symbol] = []
        self._symbol_dividends[dividend.symbol].append(dividend.event_id)
        
        logger.debug(
            f"Added dividend: {dividend.symbol} ${dividend.amount} ex-date {dividend.ex_date}"
        )
        return dividend
    
    def add_event(self, event: CorporateEvent) -> CorporateEvent:
        """Add a corporate event.
        
        Args:
            event: CorporateEvent to add.
            
        Returns:
            The added event.
        """
        self._events[event.event_id] = event
        
        if event.symbol not in self._symbol_events:
            self._symbol_events[event.symbol] = []
        self._symbol_events[event.symbol].append(event.event_id)
        
        logger.debug(
            f"Added corporate event: {event.symbol} {event.event_type.value} "
            f"on {event.event_date}"
        )
        return event
    
    def get_upcoming_dividends(
        self,
        days: int = 30,
        symbols: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[DividendEvent]:
        """Get upcoming dividend ex-dates.
        
        Args:
            days: Days to look ahead.
            symbols: Filter by symbols.
            limit: Maximum events to return.
            
        Returns:
            List of upcoming dividends.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        dividends = []
        for div in self._dividends.values():
            if div.ex_date < today or div.ex_date > end_date:
                continue
            if symbols and div.symbol not in symbols:
                continue
            dividends.append(div)
        
        dividends.sort(key=lambda d: d.ex_date)
        return dividends[:limit]
    
    def get_ex_dates_this_week(self) -> list[DividendEvent]:
        """Get dividend ex-dates for this week."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        dividends = []
        for div in self._dividends.values():
            if week_start <= div.ex_date <= week_end:
                dividends.append(div)
        
        dividends.sort(key=lambda d: (d.ex_date, d.symbol))
        return dividends
    
    def get_dividend_history(
        self,
        symbol: str,
        years: int = 5,
    ) -> list[DividendEvent]:
        """Get dividend history for a symbol.
        
        Args:
            symbol: Stock symbol.
            years: Years of history.
            
        Returns:
            List of historical dividends (most recent first).
        """
        cutoff = date.today() - timedelta(days=years * 365)
        
        event_ids = self._symbol_dividends.get(symbol, [])
        dividends = []
        
        for eid in event_ids:
            div = self._dividends.get(eid)
            if div and div.ex_date >= cutoff:
                dividends.append(div)
        
        dividends.sort(key=lambda d: d.ex_date, reverse=True)
        return dividends
    
    def get_dividend_stats(self, symbol: str) -> dict:
        """Get dividend statistics for a symbol.
        
        Args:
            symbol: Stock symbol.
            
        Returns:
            Dict with dividend stats.
        """
        history = self.get_dividend_history(symbol, years=5)
        
        if not history:
            return {
                "symbol": symbol,
                "has_dividend": False,
            }
        
        recent = history[0]
        amounts = [d.amount for d in history]
        
        # Check for dividend growth
        if len(history) >= 4:
            year_ago_divs = [d for d in history if d.ex_date < date.today() - timedelta(days=365)]
            if year_ago_divs:
                growth = (recent.amount - year_ago_divs[0].amount) / year_ago_divs[0].amount * 100
            else:
                growth = None
        else:
            growth = None
        
        return {
            "symbol": symbol,
            "has_dividend": True,
            "latest_amount": recent.amount,
            "frequency": recent.frequency.value,
            "annualized": recent.annualized_amount,
            "yield": recent.yield_on_ex_date,
            "next_ex_date": recent.ex_date if recent.ex_date >= date.today() else None,
            "payment_count": len(history),
            "avg_amount": sum(amounts) / len(amounts),
            "min_amount": min(amounts),
            "max_amount": max(amounts),
            "yoy_growth_pct": growth,
        }
    
    def get_upcoming_splits(
        self,
        days: int = 30,
    ) -> list[CorporateEvent]:
        """Get upcoming stock splits.
        
        Args:
            days: Days to look ahead.
            
        Returns:
            List of upcoming splits.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        splits = []
        for event in self._events.values():
            if event.event_type not in [CorporateEventType.STOCK_SPLIT, CorporateEventType.REVERSE_SPLIT]:
                continue
            if event.event_date < today or event.event_date > end_date:
                continue
            splits.append(event)
        
        splits.sort(key=lambda e: e.event_date)
        return splits
    
    def get_recent_ma_activity(
        self,
        days: int = 90,
    ) -> list[CorporateEvent]:
        """Get recent M&A activity.
        
        Args:
            days: Days to look back.
            
        Returns:
            List of M&A events.
        """
        cutoff = date.today() - timedelta(days=days)
        
        ma_events = []
        for event in self._events.values():
            if event.event_type not in [
                CorporateEventType.MERGER,
                CorporateEventType.ACQUISITION,
                CorporateEventType.SPINOFF,
            ]:
                continue
            if event.event_date < cutoff:
                continue
            ma_events.append(event)
        
        ma_events.sort(key=lambda e: e.event_date, reverse=True)
        return ma_events
    
    def get_recent_ipos(
        self,
        days: int = 30,
    ) -> list[CorporateEvent]:
        """Get recent IPOs.
        
        Args:
            days: Days to look back.
            
        Returns:
            List of IPO events.
        """
        cutoff = date.today() - timedelta(days=days)
        
        ipos = []
        for event in self._events.values():
            if event.event_type != CorporateEventType.IPO:
                continue
            if event.event_date < cutoff:
                continue
            ipos.append(event)
        
        ipos.sort(key=lambda e: e.event_date, reverse=True)
        return ipos
    
    def get_events_for_symbol(
        self,
        symbol: str,
        event_types: Optional[list[CorporateEventType]] = None,
        limit: int = 20,
    ) -> list[CorporateEvent]:
        """Get corporate events for a symbol.
        
        Args:
            symbol: Stock symbol.
            event_types: Filter by event types.
            limit: Maximum events to return.
            
        Returns:
            List of corporate events.
        """
        event_ids = self._symbol_events.get(symbol, [])
        
        events = []
        for eid in event_ids:
            event = self._events.get(eid)
            if not event:
                continue
            if event_types and event.event_type not in event_types:
                continue
            events.append(event)
        
        events.sort(key=lambda e: e.event_date, reverse=True)
        return events[:limit]
    
    def get_portfolio_dividends(
        self,
        symbols: list[str],
        days: int = 30,
    ) -> list[DividendEvent]:
        """Get upcoming dividends for portfolio symbols.
        
        Args:
            symbols: Portfolio symbols.
            days: Days to look ahead.
            
        Returns:
            List of upcoming dividends.
        """
        return self.get_upcoming_dividends(days=days, symbols=symbols)
    
    def get_calendar_view(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, dict]:
        """Get events organized by date for calendar view.
        
        Args:
            start_date: Calendar start.
            end_date: Calendar end.
            
        Returns:
            Dict mapping dates to events.
        """
        calendar: dict[date, dict] = {}
        
        current = start_date
        while current <= end_date:
            calendar[current] = {"dividends": [], "events": []}
            current += timedelta(days=1)
        
        # Add dividends
        for div in self._dividends.values():
            if start_date <= div.ex_date <= end_date:
                calendar[div.ex_date]["dividends"].append(div)
        
        # Add other events
        for event in self._events.values():
            if start_date <= event.event_date <= end_date:
                calendar[event.event_date]["events"].append(event)
        
        return calendar
