"""PRD-126: Trade Reconciliation — Settlement Tracker."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import SettlementStatus


@dataclass
class SettlementEvent:
    """Tracks the settlement lifecycle of a trade."""

    event_id: str
    trade_id: str
    status: SettlementStatus
    expected_date: datetime
    actual_date: Optional[datetime] = None
    counterparty: str = ""
    currency: str = "USD"
    amount: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class SettlementTracker:
    """Tracks settlement status for matched trades."""

    def __init__(self, settlement_days: int = 2) -> None:
        self.settlement_days = settlement_days
        self._events: dict[str, SettlementEvent] = {}
        self._by_trade: dict[str, str] = {}  # trade_id -> event_id

    def track_settlement(
        self,
        trade_id: str,
        trade_date: datetime,
        amount: float = 0.0,
        counterparty: str = "",
        currency: str = "USD",
    ) -> SettlementEvent:
        """Start tracking settlement for a trade."""
        event_id = uuid.uuid4().hex[:16]
        expected = trade_date + timedelta(days=self.settlement_days)
        # Skip weekends for settlement date
        while expected.weekday() >= 5:
            expected += timedelta(days=1)

        event = SettlementEvent(
            event_id=event_id,
            trade_id=trade_id,
            status=SettlementStatus.PENDING,
            expected_date=expected,
            amount=amount,
            counterparty=counterparty,
            currency=currency,
        )
        self._events[event_id] = event
        self._by_trade[trade_id] = event_id
        return event

    def update_status(
        self,
        event_id: str,
        status: SettlementStatus,
        notes: str = "",
    ) -> Optional[SettlementEvent]:
        """Update the settlement status of an event."""
        event = self._events.get(event_id)
        if not event:
            return None
        event.status = status
        event.updated_at = datetime.now(timezone.utc)
        event.notes = notes
        if status == SettlementStatus.SETTLED:
            event.actual_date = datetime.now(timezone.utc)
        return event

    def get_event(self, event_id: str) -> Optional[SettlementEvent]:
        """Get a settlement event by ID."""
        return self._events.get(event_id)

    def get_by_trade(self, trade_id: str) -> Optional[SettlementEvent]:
        """Get settlement event for a trade."""
        event_id = self._by_trade.get(trade_id)
        if event_id:
            return self._events.get(event_id)
        return None

    def get_pending_settlements(
        self, as_of: Optional[datetime] = None
    ) -> list[SettlementEvent]:
        """Get all pending settlements, optionally due by a specific date."""
        pending = [
            e
            for e in self._events.values()
            if e.status in (SettlementStatus.PENDING, SettlementStatus.IN_PROGRESS)
        ]
        if as_of:
            pending = [e for e in pending if e.expected_date <= as_of]
        return sorted(pending, key=lambda e: e.expected_date)

    def check_overdue(
        self, as_of: Optional[datetime] = None
    ) -> list[SettlementEvent]:
        """Find overdue settlements."""
        now = as_of or datetime.now(timezone.utc)
        return [
            e
            for e in self._events.values()
            if e.status in (SettlementStatus.PENDING, SettlementStatus.IN_PROGRESS)
            and e.expected_date < now
        ]

    def settlement_summary(self) -> dict:
        """Get summary statistics for all settlements."""
        events = list(self._events.values())
        if not events:
            return {
                "total": 0,
                "pending": 0,
                "in_progress": 0,
                "settled": 0,
                "failed": 0,
                "cancelled": 0,
                "overdue": 0,
                "settlement_rate": 0.0,
            }

        now = datetime.now(timezone.utc)
        by_status = {}
        for s in SettlementStatus:
            by_status[s.value] = len([e for e in events if e.status == s])

        overdue = len(self.check_overdue(now))
        settled = by_status.get("settled", 0)
        total = len(events)

        return {
            "total": total,
            "pending": by_status.get("pending", 0),
            "in_progress": by_status.get("in_progress", 0),
            "settled": settled,
            "failed": by_status.get("failed", 0),
            "cancelled": by_status.get("cancelled", 0),
            "overdue": overdue,
            "settlement_rate": settled / total if total > 0 else 0.0,
        }

    def average_settlement_time(self) -> Optional[float]:
        """Calculate average time to settle in hours."""
        settled = [
            e
            for e in self._events.values()
            if e.status == SettlementStatus.SETTLED and e.actual_date
        ]
        if not settled:
            return None
        total_hours = sum(
            (e.actual_date - e.created_at).total_seconds() / 3600  # type: ignore[operator]
            for e in settled
        )
        return total_hours / len(settled)
