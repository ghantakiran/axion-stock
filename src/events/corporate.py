"""Corporate Action Tracker.

Tracks dividends, splits, buybacks, and spinoffs. Provides
upcoming event calendar and dividend analysis.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

import numpy as np

from src.events.config import (
    EventType,
    CorporateConfig,
    DEFAULT_EVENT_CONFIG,
)
from src.events.models import CorporateAction, DividendSummary

logger = logging.getLogger(__name__)


class CorporateActionTracker:
    """Tracks and analyzes corporate actions."""

    def __init__(self, config: Optional[CorporateConfig] = None) -> None:
        self.config = config or DEFAULT_EVENT_CONFIG.corporate
        self._actions: dict[str, list[CorporateAction]] = defaultdict(list)

    def add_action(self, action: CorporateAction) -> CorporateAction:
        """Add a corporate action."""
        self._actions[action.symbol].append(action)
        return action

    def add_actions(self, actions: list[CorporateAction]) -> list[CorporateAction]:
        """Add multiple corporate actions."""
        return [self.add_action(a) for a in actions]

    def get_upcoming(
        self, reference_date: Optional[date] = None, days: Optional[int] = None
    ) -> list[CorporateAction]:
        """Get upcoming corporate actions within window.

        Args:
            reference_date: Reference date (default: today).
            days: Window in days (default: config.upcoming_window_days).

        Returns:
            List of upcoming actions sorted by effective date.
        """
        ref = reference_date or date.today()
        window = days or self.config.upcoming_window_days
        cutoff = ref + timedelta(days=window)

        upcoming = []
        for actions in self._actions.values():
            for a in actions:
                if a.effective_date and ref <= a.effective_date <= cutoff:
                    upcoming.append(a)

        return sorted(upcoming, key=lambda a: a.effective_date)

    def analyze_dividends(
        self, symbol: str, current_price: float = 0.0
    ) -> DividendSummary:
        """Analyze dividend history for a symbol.

        Computes yield, growth rate, and consecutive increase streak.

        Args:
            symbol: Stock symbol.
            current_price: Current stock price for yield calculation.

        Returns:
            DividendSummary.
        """
        divs = [
            a for a in self._actions.get(symbol, [])
            if a.action_type == EventType.DIVIDEND
        ]

        if not divs:
            return DividendSummary(symbol=symbol)

        sorted_divs = sorted(divs, key=lambda d: d.announce_date)
        amounts = [d.amount for d in sorted_divs]
        ex_dates = [
            d.effective_date for d in sorted_divs
            if d.effective_date is not None
        ]

        # Annual dividend (sum of last 4 quarters or all if fewer)
        recent = amounts[-4:] if len(amounts) >= 4 else amounts
        annual = sum(recent) * (4 / len(recent)) if recent else 0.0

        # Yield
        current_yield = annual / current_price if current_price > 0 else 0.0

        # Growth rate (YoY if enough data)
        growth = 0.0
        if len(amounts) >= 8:
            recent_4 = sum(amounts[-4:])
            prior_4 = sum(amounts[-8:-4])
            if prior_4 > 0:
                growth = (recent_4 - prior_4) / prior_4

        # Consecutive increases
        consecutive = self._consecutive_increases(amounts)

        return DividendSummary(
            symbol=symbol,
            annual_dividend=round(annual, 4),
            current_yield=round(current_yield, 4),
            growth_rate=round(growth, 4),
            consecutive_increases=consecutive,
            ex_dates=ex_dates,
        )

    def analyze_buybacks(self, symbol: str, market_cap: float = 0.0) -> dict:
        """Analyze buyback activity for a symbol.

        Args:
            symbol: Stock symbol.
            market_cap: Current market cap for percentage calculation.

        Returns:
            Dict with total_amount, count, pct_of_market_cap, is_significant.
        """
        buybacks = [
            a for a in self._actions.get(symbol, [])
            if a.action_type == EventType.BUYBACK
        ]

        if not buybacks:
            return {
                "symbol": symbol,
                "total_amount": 0.0,
                "count": 0,
                "pct_of_market_cap": 0.0,
                "is_significant": False,
            }

        total = sum(b.amount for b in buybacks)
        pct = total / market_cap if market_cap > 0 else 0.0

        return {
            "symbol": symbol,
            "total_amount": total,
            "count": len(buybacks),
            "pct_of_market_cap": round(pct, 4),
            "is_significant": pct >= self.config.significant_buyback_pct,
        }

    def get_actions(
        self, symbol: str, action_type: Optional[EventType] = None
    ) -> list[CorporateAction]:
        """Get corporate actions for a symbol, optionally filtered by type."""
        actions = self._actions.get(symbol, [])
        if action_type:
            actions = [a for a in actions if a.action_type == action_type]
        return sorted(actions, key=lambda a: a.announce_date, reverse=True)

    def _consecutive_increases(self, amounts: list[float]) -> int:
        """Count consecutive dividend increases from most recent."""
        if len(amounts) < 2:
            return 0

        streak = 0
        for i in range(len(amounts) - 1, 0, -1):
            if amounts[i] > amounts[i - 1]:
                streak += 1
            else:
                break
        return streak

    def reset(self) -> None:
        """Clear all stored actions."""
        self._actions.clear()
