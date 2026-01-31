"""Dividend Calendar.

Track ex-dividend dates, payment dates, and dividend events.
"""

from datetime import date, timedelta
from typing import Optional
import logging

from src.dividends.config import DividendFrequency, DividendType
from src.dividends.models import DividendEvent

logger = logging.getLogger(__name__)


class DividendCalendar:
    """Manages dividend calendar events.
    
    Tracks upcoming ex-dates, payment dates, and dividend announcements.
    
    Example:
        calendar = DividendCalendar()
        
        calendar.add_event(DividendEvent(
            symbol="AAPL",
            ex_dividend_date=date(2024, 2, 9),
            payment_date=date(2024, 2, 15),
            amount=0.24,
        ))
        
        upcoming = calendar.get_upcoming_ex_dates(days=30)
    """
    
    def __init__(self):
        self._events: dict[str, DividendEvent] = {}  # event_id -> event
        self._by_symbol: dict[str, list[str]] = {}   # symbol -> event_ids
        self._by_ex_date: dict[date, list[str]] = {}  # ex_date -> event_ids
        self._by_payment_date: dict[date, list[str]] = {}  # payment_date -> event_ids
    
    def add_event(self, event: DividendEvent) -> None:
        """Add a dividend event."""
        self._events[event.event_id] = event
        
        # Index by symbol
        if event.symbol not in self._by_symbol:
            self._by_symbol[event.symbol] = []
        self._by_symbol[event.symbol].append(event.event_id)
        
        # Index by ex-date
        if event.ex_dividend_date:
            if event.ex_dividend_date not in self._by_ex_date:
                self._by_ex_date[event.ex_dividend_date] = []
            self._by_ex_date[event.ex_dividend_date].append(event.event_id)
        
        # Index by payment date
        if event.payment_date:
            if event.payment_date not in self._by_payment_date:
                self._by_payment_date[event.payment_date] = []
            self._by_payment_date[event.payment_date].append(event.event_id)
    
    def get_event(self, event_id: str) -> Optional[DividendEvent]:
        """Get event by ID."""
        return self._events.get(event_id)
    
    def get_events_for_symbol(self, symbol: str) -> list[DividendEvent]:
        """Get all events for a symbol."""
        event_ids = self._by_symbol.get(symbol, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]
    
    def get_next_ex_date(self, symbol: str) -> Optional[DividendEvent]:
        """Get the next upcoming ex-dividend date for a symbol."""
        events = self.get_events_for_symbol(symbol)
        today = date.today()
        
        future_events = [e for e in events if e.ex_dividend_date and e.ex_dividend_date >= today]
        if not future_events:
            return None
        
        return min(future_events, key=lambda e: e.ex_dividend_date)
    
    def get_upcoming_ex_dates(
        self,
        days: int = 30,
        symbols: Optional[list[str]] = None,
    ) -> list[DividendEvent]:
        """Get upcoming ex-dividend dates.
        
        Args:
            days: Number of days ahead to look.
            symbols: Optional filter to specific symbols.
            
        Returns:
            List of events sorted by ex-date.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = []
        for event in self._events.values():
            if not event.ex_dividend_date:
                continue
            
            if today <= event.ex_dividend_date <= end_date:
                if symbols is None or event.symbol in symbols:
                    events.append(event)
        
        return sorted(events, key=lambda e: e.ex_dividend_date)
    
    def get_upcoming_payments(
        self,
        days: int = 30,
        symbols: Optional[list[str]] = None,
    ) -> list[DividendEvent]:
        """Get upcoming payment dates.
        
        Args:
            days: Number of days ahead to look.
            symbols: Optional filter to specific symbols.
            
        Returns:
            List of events sorted by payment date.
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        events = []
        for event in self._events.values():
            if not event.payment_date:
                continue
            
            if today <= event.payment_date <= end_date:
                if symbols is None or event.symbol in symbols:
                    events.append(event)
        
        return sorted(events, key=lambda e: e.payment_date)
    
    def get_ex_dates_on(self, target_date: date) -> list[DividendEvent]:
        """Get all ex-dividend events for a specific date."""
        event_ids = self._by_ex_date.get(target_date, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]
    
    def get_payments_on(self, target_date: date) -> list[DividendEvent]:
        """Get all payment events for a specific date."""
        event_ids = self._by_payment_date.get(target_date, [])
        return [self._events[eid] for eid in event_ids if eid in self._events]
    
    def get_monthly_summary(
        self,
        year: int,
        month: int,
        symbols: Optional[list[str]] = None,
    ) -> dict:
        """Get monthly dividend summary.
        
        Returns:
            Dict with ex-dates count, payment count, total amount.
        """
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        
        ex_date_events = []
        payment_events = []
        
        for event in self._events.values():
            if symbols and event.symbol not in symbols:
                continue
            
            if event.ex_dividend_date and start <= event.ex_dividend_date < end:
                ex_date_events.append(event)
            
            if event.payment_date and start <= event.payment_date < end:
                payment_events.append(event)
        
        return {
            "year": year,
            "month": month,
            "ex_date_count": len(ex_date_events),
            "payment_count": len(payment_events),
            "ex_date_events": ex_date_events,
            "payment_events": payment_events,
        }
    
    def get_dividend_increases(
        self,
        days: int = 90,
    ) -> list[DividendEvent]:
        """Get recent dividend increases."""
        today = date.today()
        cutoff = today - timedelta(days=days)
        
        increases = []
        for event in self._events.values():
            if not event.declaration_date or event.declaration_date < cutoff:
                continue
            
            change = event.change_pct
            if change and change > 0:
                increases.append(event)
        
        return sorted(increases, key=lambda e: e.change_pct or 0, reverse=True)
    
    def get_dividend_cuts(
        self,
        days: int = 90,
    ) -> list[DividendEvent]:
        """Get recent dividend cuts."""
        today = date.today()
        cutoff = today - timedelta(days=days)
        
        cuts = []
        for event in self._events.values():
            if not event.declaration_date or event.declaration_date < cutoff:
                continue
            
            change = event.change_pct
            if change and change < 0:
                cuts.append(event)
        
        return sorted(cuts, key=lambda e: e.change_pct or 0)
    
    def get_special_dividends(
        self,
        days: int = 90,
    ) -> list[DividendEvent]:
        """Get recent special dividends."""
        today = date.today()
        cutoff = today - timedelta(days=days)
        
        specials = []
        for event in self._events.values():
            if event.dividend_type != DividendType.SPECIAL:
                continue
            
            if event.ex_dividend_date and event.ex_dividend_date >= cutoff:
                specials.append(event)
        
        return sorted(specials, key=lambda e: e.amount, reverse=True)
    
    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
        self._by_symbol.clear()
        self._by_ex_date.clear()
        self._by_payment_date.clear()


def generate_sample_calendar() -> DividendCalendar:
    """Generate a sample dividend calendar for testing."""
    calendar = DividendCalendar()
    today = date.today()
    
    # Sample dividend events
    sample_events = [
        ("AAPL", "Apple Inc.", 5, 12, 0.24, 0.23, DividendFrequency.QUARTERLY),
        ("MSFT", "Microsoft Corp.", 8, 15, 0.75, 0.68, DividendFrequency.QUARTERLY),
        ("JNJ", "Johnson & Johnson", 3, 10, 1.24, 1.19, DividendFrequency.QUARTERLY),
        ("PG", "Procter & Gamble", 10, 17, 1.0065, 0.9407, DividendFrequency.QUARTERLY),
        ("KO", "Coca-Cola Co.", 12, 19, 0.485, 0.46, DividendFrequency.QUARTERLY),
        ("PEP", "PepsiCo Inc.", 6, 13, 1.355, 1.265, DividendFrequency.QUARTERLY),
        ("VZ", "Verizon", 2, 9, 0.6650, 0.6525, DividendFrequency.QUARTERLY),
        ("T", "AT&T Inc.", 7, 14, 0.2775, 0.2775, DividendFrequency.QUARTERLY),
        ("O", "Realty Income", 1, 15, 0.2565, 0.2555, DividendFrequency.MONTHLY),
        ("XOM", "Exxon Mobil", 9, 16, 0.95, 0.91, DividendFrequency.QUARTERLY),
    ]
    
    for symbol, name, ex_offset, pay_offset, amount, prev_amount, freq in sample_events:
        event = DividendEvent(
            symbol=symbol,
            company_name=name,
            declaration_date=today - timedelta(days=10),
            ex_dividend_date=today + timedelta(days=ex_offset),
            record_date=today + timedelta(days=ex_offset + 1),
            payment_date=today + timedelta(days=pay_offset),
            amount=amount,
            previous_amount=prev_amount,
            frequency=freq,
            dividend_type=DividendType.REGULAR,
        )
        calendar.add_event(event)
    
    return calendar
