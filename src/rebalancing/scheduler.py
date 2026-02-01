"""Rebalance Scheduler.

Determines when to trigger rebalancing based on calendar schedules,
drift thresholds, or combined triggers.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from src.rebalancing.config import (
    RebalanceTrigger,
    RebalanceFrequency,
    CalendarConfig,
    DriftConfig,
    DEFAULT_CALENDAR_CONFIG,
    DEFAULT_DRIFT_CONFIG,
)
from src.rebalancing.models import PortfolioDrift, ScheduleState

logger = logging.getLogger(__name__)


class RebalanceScheduler:
    """Determines when to trigger portfolio rebalancing."""

    def __init__(
        self,
        trigger: RebalanceTrigger = RebalanceTrigger.COMBINED,
        calendar_config: Optional[CalendarConfig] = None,
        drift_config: Optional[DriftConfig] = None,
    ) -> None:
        self.trigger = trigger
        self.calendar_config = calendar_config or DEFAULT_CALENDAR_CONFIG
        self.drift_config = drift_config or DEFAULT_DRIFT_CONFIG
        self._last_rebalance: Optional[date] = None

    def should_rebalance(
        self,
        drift: Optional[PortfolioDrift] = None,
        as_of_date: Optional[date] = None,
    ) -> bool:
        """Check if rebalancing should be triggered.

        Args:
            drift: Current portfolio drift (needed for threshold trigger).
            as_of_date: Date to check against.

        Returns:
            True if rebalance should be triggered.
        """
        check_date = as_of_date or date.today()

        if self.trigger == RebalanceTrigger.CALENDAR:
            return self._calendar_trigger(check_date)
        elif self.trigger == RebalanceTrigger.THRESHOLD:
            return self._threshold_trigger(drift)
        elif self.trigger == RebalanceTrigger.COMBINED:
            return self._calendar_trigger(check_date) or self._threshold_trigger(drift)
        else:  # MANUAL
            return False

    def next_rebalance_date(
        self,
        from_date: Optional[date] = None,
    ) -> date:
        """Calculate next scheduled rebalance date.

        Args:
            from_date: Start date for calculation.

        Returns:
            Next rebalance date.
        """
        start = from_date or self._last_rebalance or date.today()
        freq = self.calendar_config.frequency

        if freq == RebalanceFrequency.WEEKLY:
            days_ahead = self.calendar_config.day_of_week - start.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return start + timedelta(days=days_ahead)

        elif freq == RebalanceFrequency.MONTHLY:
            # Next month, specific day
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1, day=self.calendar_config.day_of_month)
            else:
                day = min(self.calendar_config.day_of_month, 28)
                next_month = start.replace(month=start.month + 1, day=day)
            if next_month <= start:
                if next_month.month == 12:
                    next_month = next_month.replace(year=next_month.year + 1, month=1)
                else:
                    next_month = next_month.replace(month=next_month.month + 1)
            return next_month

        elif freq == RebalanceFrequency.QUARTERLY:
            # Next quarter start
            current_q = (start.month - 1) // 3
            next_q_month = (current_q + 1) * 3 + self.calendar_config.month_of_quarter
            next_q_year = start.year
            if next_q_month > 12:
                next_q_month -= 12
                next_q_year += 1
            day = min(self.calendar_config.day_of_month, 28)
            next_date = date(next_q_year, next_q_month, day)
            if next_date <= start:
                next_q_month += 3
                if next_q_month > 12:
                    next_q_month -= 12
                    next_q_year += 1
                next_date = date(next_q_year, next_q_month, day)
            return next_date

        else:  # ANNUAL
            next_year = date(start.year + 1, 1, self.calendar_config.day_of_month)
            return next_year

    def get_state(
        self,
        drift: Optional[PortfolioDrift] = None,
        as_of_date: Optional[date] = None,
    ) -> ScheduleState:
        """Get current scheduler state.

        Args:
            drift: Current portfolio drift.
            as_of_date: Current date.

        Returns:
            ScheduleState with timing info.
        """
        check_date = as_of_date or date.today()
        next_date = self.next_rebalance_date(check_date)
        days_until = (next_date - check_date).days
        threshold_breached = drift.needs_rebalance if drift else False
        trigger_active = self.should_rebalance(drift, check_date)

        return ScheduleState(
            last_rebalance=self._last_rebalance,
            next_scheduled=next_date,
            trigger_active=trigger_active,
            days_until_next=max(0, days_until),
            threshold_breached=threshold_breached,
        )

    def record_rebalance(self, rebalance_date: Optional[date] = None) -> None:
        """Record that a rebalance was executed."""
        self._last_rebalance = rebalance_date or date.today()

    def _calendar_trigger(self, check_date: date) -> bool:
        """Check if calendar trigger fires."""
        if self._last_rebalance is None:
            return True

        next_date = self.next_rebalance_date(self._last_rebalance)
        return check_date >= next_date

    def _threshold_trigger(self, drift: Optional[PortfolioDrift]) -> bool:
        """Check if threshold trigger fires."""
        if drift is None:
            return False
        return drift.needs_rebalance
