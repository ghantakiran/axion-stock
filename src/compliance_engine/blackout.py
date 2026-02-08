"""Insider trading blackout window management."""

import uuid
from datetime import date, timedelta
from typing import Dict, List, Optional

from .config import BlackoutConfig
from .models import BlackoutWindow, PreClearanceRequest


class BlackoutManager:
    """Manages insider trading blackout windows and pre-clearance."""

    def __init__(self, config: Optional[BlackoutConfig] = None):
        self.config = config or BlackoutConfig()
        self._windows: List[BlackoutWindow] = []
        self._requests: List[PreClearanceRequest] = []

    def create_blackout(
        self,
        symbol: str,
        reason: str,
        start_date: date,
        end_date: date,
        created_by: str = "",
        affected_persons: Optional[List[str]] = None,
    ) -> BlackoutWindow:
        window = BlackoutWindow(
            window_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            reason=reason,
            start_date=start_date,
            end_date=end_date,
            created_by=created_by,
            affected_persons=affected_persons or [],
        )
        self._windows.append(window)
        return window

    def create_earnings_blackout(
        self,
        symbol: str,
        earnings_date: date,
        affected_persons: Optional[List[str]] = None,
    ) -> BlackoutWindow:
        """Create standard earnings blackout window."""
        start = earnings_date - timedelta(days=self.config.default_blackout_days_before)
        end = earnings_date + timedelta(days=self.config.default_blackout_days_after)

        return self.create_blackout(
            symbol=symbol,
            reason=f"Earnings blackout ({earnings_date.isoformat()})",
            start_date=start,
            end_date=end,
            created_by="system",
            affected_persons=affected_persons,
        )

    def check_blackout(
        self, symbol: str, check_date: Optional[date] = None, person_id: Optional[str] = None
    ) -> bool:
        """Check if a symbol is in a blackout window."""
        d = check_date or date.today()
        for w in self._windows:
            if w.symbol == symbol and w.is_in_blackout(d):
                if person_id and w.affected_persons:
                    if person_id in w.affected_persons:
                        return True
                else:
                    return True
        return False

    def get_active_blackouts(self, check_date: Optional[date] = None) -> List[BlackoutWindow]:
        d = check_date or date.today()
        return [w for w in self._windows if w.is_in_blackout(d)]

    def deactivate_blackout(self, window_id: str) -> bool:
        for w in self._windows:
            if w.window_id == window_id:
                w.is_active = False
                return True
        return False

    def submit_pre_clearance(
        self,
        requester_id: str,
        symbol: str,
        side: str,
        quantity: int,
        estimated_value: float = 0.0,
        reason: str = "",
    ) -> PreClearanceRequest:
        request = PreClearanceRequest(
            request_id=str(uuid.uuid4())[:8],
            requester_id=requester_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            estimated_value=estimated_value,
            reason=reason,
        )
        self._requests.append(request)
        return request

    def approve_pre_clearance(
        self, request_id: str, approved_by: str
    ) -> bool:
        for r in self._requests:
            if r.request_id == request_id and r.is_pending:
                r.approved = True
                r.approved_by = approved_by
                r.valid_until = date.today() + timedelta(days=self.config.pre_clearance_valid_days)
                return True
        return False

    def deny_pre_clearance(self, request_id: str, denied_by: str) -> bool:
        for r in self._requests:
            if r.request_id == request_id and r.is_pending:
                r.approved = False
                r.approved_by = denied_by
                return True
        return False

    def get_pending_requests(self) -> List[PreClearanceRequest]:
        return [r for r in self._requests if r.is_pending]

    def can_trade(
        self, symbol: str, person_id: str, trade_value: float = 0.0
    ) -> Dict[str, any]:
        """Check if a person can trade a symbol, considering blackouts and pre-clearance."""
        # Check blackout
        in_blackout = self.check_blackout(symbol, person_id=person_id)

        if not in_blackout:
            return {"allowed": True, "reason": "No blackout restrictions"}

        # Below threshold doesn't need pre-clearance
        if trade_value <= self.config.max_trade_value_without_clearance:
            return {"allowed": True, "reason": "Below pre-clearance threshold"}

        if not self.config.require_pre_clearance:
            return {"allowed": False, "reason": "In blackout window, pre-clearance not available"}

        # Check for valid pre-clearance
        valid = [
            r for r in self._requests
            if r.requester_id == person_id
               and r.symbol == symbol
               and r.is_valid
        ]

        if valid:
            return {"allowed": True, "reason": "Pre-clearance approved"}

        return {"allowed": False, "reason": "In blackout window, pre-clearance required"}

    def list_all_windows(self) -> List[BlackoutWindow]:
        return self._windows
