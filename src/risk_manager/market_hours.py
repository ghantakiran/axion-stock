"""Market Hours Enforcer — calendar and session awareness.

Enforces trading only during valid market sessions:
- NYSE/NASDAQ regular hours: 9:30 AM - 4:00 PM ET
- Pre-market: 4:00 AM - 9:30 AM ET
- After-hours: 4:00 PM - 8:00 PM ET
- Holiday calendar with early closes
- Configurable session restrictions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════
# Market Holidays (2025-2026)
# ═══════════════════════════════════════════════════════════════════════


MARKET_HOLIDAYS: set[date] = {
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}

# Early close days (1:00 PM ET)
EARLY_CLOSE_DAYS: set[date] = {
    date(2025, 7, 3),    # Day before Independence Day
    date(2025, 11, 28),  # Day after Thanksgiving
    date(2025, 12, 24),  # Christmas Eve
    date(2026, 11, 27),  # Day after Thanksgiving
    date(2026, 12, 24),  # Christmas Eve
}


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class MarketSession(str, Enum):
    """Current market session."""

    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"


@dataclass
class MarketCalendarConfig:
    """Configuration for market hours enforcement.

    Attributes:
        allow_premarket: Allow trades during pre-market (4:00-9:30 AM ET).
        allow_afterhours: Allow trades during after-hours (4:00-8:00 PM ET).
        allow_holidays: Allow trades on market holidays (crypto-only).
        regular_open: Regular session open time (ET).
        regular_close: Regular session close time (ET).
        premarket_open: Pre-market open time (ET).
        afterhours_close: After-hours close time (ET).
        early_close_time: Close time on early close days (ET).
        timezone_offset_hours: Hours offset from UTC (ET = -5, EDT = -4).
    """

    allow_premarket: bool = False
    allow_afterhours: bool = False
    allow_holidays: bool = False
    regular_open: time = field(default_factory=lambda: time(9, 30))
    regular_close: time = field(default_factory=lambda: time(16, 0))
    premarket_open: time = field(default_factory=lambda: time(4, 0))
    afterhours_close: time = field(default_factory=lambda: time(20, 0))
    early_close_time: time = field(default_factory=lambda: time(13, 0))
    timezone_offset_hours: int = -5  # Eastern Standard Time


# ═══════════════════════════════════════════════════════════════════════
# Market Hours Enforcer
# ═══════════════════════════════════════════════════════════════════════


class MarketHoursEnforcer:
    """Enforces market hours and calendar restrictions.

    Determines the current market session and whether trading
    is allowed based on the configuration. Supports crypto assets
    which trade 24/7.

    Args:
        config: MarketCalendarConfig with session rules.

    Example:
        enforcer = MarketHoursEnforcer()
        session = enforcer.get_session()
        if enforcer.is_trading_allowed():
            # Place order
        if enforcer.is_trading_allowed(asset_type="crypto"):
            # Always True for crypto
    """

    def __init__(self, config: MarketCalendarConfig | None = None) -> None:
        self.config = config or MarketCalendarConfig()

    def get_session(self, dt: Optional[datetime] = None) -> MarketSession:
        """Determine the current market session.

        Args:
            dt: Datetime to check (defaults to now UTC).

        Returns:
            MarketSession enum value.
        """
        et_dt = self._to_eastern(dt)
        current_date = et_dt.date()
        current_time = et_dt.time()

        # Weekend
        if current_date.weekday() >= 5:
            return MarketSession.CLOSED

        # Holiday
        if current_date in MARKET_HOLIDAYS:
            return MarketSession.CLOSED

        # Early close day
        close_time = self.config.regular_close
        if current_date in EARLY_CLOSE_DAYS:
            close_time = self.config.early_close_time

        # Pre-market
        if self.config.premarket_open <= current_time < self.config.regular_open:
            return MarketSession.PRE_MARKET

        # Regular
        if self.config.regular_open <= current_time < close_time:
            return MarketSession.REGULAR

        # After hours
        if close_time <= current_time < self.config.afterhours_close:
            return MarketSession.AFTER_HOURS

        return MarketSession.CLOSED

    def is_trading_allowed(
        self,
        dt: Optional[datetime] = None,
        asset_type: str = "stock",
    ) -> bool:
        """Check if trading is allowed right now.

        Args:
            dt: Datetime to check (defaults to now).
            asset_type: Asset type ('stock', 'options', 'crypto', etc).

        Returns:
            True if trading is allowed for this asset type.
        """
        # Crypto trades 24/7
        if asset_type == "crypto":
            return True

        session = self.get_session(dt)

        if session == MarketSession.REGULAR:
            return True
        elif session == MarketSession.PRE_MARKET:
            return self.config.allow_premarket
        elif session == MarketSession.AFTER_HOURS:
            return self.config.allow_afterhours
        elif session == MarketSession.CLOSED:
            return self.config.allow_holidays and self._is_holiday(dt)

        return False

    def is_holiday(self, dt: Optional[datetime] = None) -> bool:
        """Check if the given date is a market holiday."""
        return self._is_holiday(dt)

    def is_early_close(self, dt: Optional[datetime] = None) -> bool:
        """Check if the given date is an early close day."""
        et_dt = self._to_eastern(dt)
        return et_dt.date() in EARLY_CLOSE_DAYS

    def next_open(self, dt: Optional[datetime] = None) -> datetime:
        """Get the next market open time.

        Args:
            dt: Starting datetime (defaults to now).

        Returns:
            Next regular session open as UTC datetime.
        """
        et_dt = self._to_eastern(dt)
        current_date = et_dt.date()

        # Start from today
        check_date = current_date
        for _ in range(10):  # Max 10 days ahead
            if check_date.weekday() < 5 and check_date not in MARKET_HOLIDAYS:
                open_dt = datetime.combine(check_date, self.config.regular_open)
                # Convert back to UTC
                utc_dt = open_dt.replace(tzinfo=None) - timedelta(
                    hours=self.config.timezone_offset_hours
                )
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                if utc_dt > (dt or datetime.now(timezone.utc)):
                    return utc_dt
            check_date += timedelta(days=1)

        # Fallback: next Monday
        days_ahead = 7 - current_date.weekday()
        next_monday = current_date + timedelta(days=days_ahead)
        open_dt = datetime.combine(next_monday, self.config.regular_open)
        utc_dt = open_dt.replace(tzinfo=None) - timedelta(
            hours=self.config.timezone_offset_hours
        )
        return utc_dt.replace(tzinfo=timezone.utc)

    def time_until_close(self, dt: Optional[datetime] = None) -> Optional[float]:
        """Get minutes until market close. None if market is closed.

        Args:
            dt: Current datetime (defaults to now).

        Returns:
            Minutes until close, or None if closed.
        """
        session = self.get_session(dt)
        if session == MarketSession.CLOSED:
            return None

        et_dt = self._to_eastern(dt)
        current_date = et_dt.date()
        current_time = et_dt.time()

        close_time = self.config.regular_close
        if current_date in EARLY_CLOSE_DAYS:
            close_time = self.config.early_close_time

        if session == MarketSession.AFTER_HOURS:
            close_time = self.config.afterhours_close

        close_dt = datetime.combine(current_date, close_time)
        current_dt = datetime.combine(current_date, current_time)
        delta = (close_dt - current_dt).total_seconds() / 60.0
        return max(0.0, delta)

    def get_session_info(self, dt: Optional[datetime] = None) -> dict[str, Any]:
        """Get comprehensive session information.

        Returns:
            Dict with session, is_open, time_to_close, next_open, etc.
        """
        session = self.get_session(dt)
        return {
            "session": session.value,
            "is_open": session != MarketSession.CLOSED,
            "is_regular": session == MarketSession.REGULAR,
            "is_holiday": self.is_holiday(dt),
            "is_early_close": self.is_early_close(dt),
            "time_until_close_min": self.time_until_close(dt),
        }

    # ── Internals ───────────────────────────────────────────────────

    def _to_eastern(self, dt: Optional[datetime] = None) -> datetime:
        """Convert a datetime to Eastern Time (approximate)."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        offset = timedelta(hours=self.config.timezone_offset_hours)
        return dt + offset

    def _is_holiday(self, dt: Optional[datetime] = None) -> bool:
        et_dt = self._to_eastern(dt)
        return et_dt.date() in MARKET_HOLIDAYS
