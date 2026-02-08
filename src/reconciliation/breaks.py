"""PRD-126: Trade Reconciliation — Break Management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import BreakSeverity, BreakType, ReconciliationConfig, ReconciliationStatus
from .matcher import MatchResult


@dataclass
class ReconciliationBreak:
    """A reconciliation break requiring investigation."""

    break_id: str
    match_result: MatchResult
    break_type: BreakType
    severity: BreakSeverity
    status: str = "open"  # open, investigating, resolved, dismissed
    assigned_to: Optional[str] = None
    resolution: Optional["BreakResolution"] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BreakResolution:
    """Resolution details for a reconciliation break."""

    resolution_id: str
    break_id: str
    action: str  # "adjusted", "accepted", "cancelled", "rebooking"
    resolved_by: str
    notes: str = ""
    adjustment_amount: float = 0.0
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BreakManager:
    """Manages reconciliation breaks and their resolution."""

    def __init__(self, config: Optional[ReconciliationConfig] = None) -> None:
        self.config = config or ReconciliationConfig()
        self._breaks: dict[str, ReconciliationBreak] = {}
        self._resolutions: dict[str, BreakResolution] = {}

    def create_break(self, match_result: MatchResult) -> ReconciliationBreak:
        """Create a break from a match result."""
        break_id = uuid.uuid4().hex[:16]
        break_type = match_result.break_type or BreakType.MISSING_BROKER
        severity = self._classify_severity(match_result, break_type)

        brk = ReconciliationBreak(
            break_id=break_id,
            match_result=match_result,
            break_type=break_type,
            severity=severity,
        )
        self._breaks[break_id] = brk
        return brk

    def classify_break(self, match_result: MatchResult) -> BreakType:
        """Classify the type of break from a match result."""
        if match_result.break_type:
            return match_result.break_type
        if match_result.internal_trade is None:
            return BreakType.MISSING_INTERNAL
        if match_result.broker_trade is None:
            return BreakType.MISSING_BROKER
        internal = match_result.internal_trade
        broker = match_result.broker_trade
        if internal.side != broker.side:
            return BreakType.SIDE_MISMATCH
        if internal.price != broker.price:
            return BreakType.PRICE_MISMATCH
        if internal.quantity != broker.quantity:
            return BreakType.QUANTITY_MISMATCH
        return BreakType.TIMING

    def resolve_break(
        self,
        break_id: str,
        action: str,
        resolved_by: str,
        notes: str = "",
        adjustment_amount: float = 0.0,
    ) -> Optional[BreakResolution]:
        """Resolve a break with an action."""
        brk = self._breaks.get(break_id)
        if not brk:
            return None

        resolution_id = uuid.uuid4().hex[:16]
        resolution = BreakResolution(
            resolution_id=resolution_id,
            break_id=break_id,
            action=action,
            resolved_by=resolved_by,
            notes=notes,
            adjustment_amount=adjustment_amount,
        )
        brk.resolution = resolution
        brk.status = "resolved"
        brk.updated_at = datetime.now(timezone.utc)
        self._resolutions[resolution_id] = resolution
        return resolution

    def auto_resolve(self, brk: ReconciliationBreak) -> Optional[BreakResolution]:
        """Attempt to auto-resolve a break based on confidence."""
        if brk.match_result.confidence >= self.config.auto_resolve_threshold:
            return self.resolve_break(
                brk.break_id,
                action="accepted",
                resolved_by="auto_resolver",
                notes=f"Auto-resolved with confidence {brk.match_result.confidence:.2%}",
            )
        return None

    def assign_break(self, break_id: str, assigned_to: str) -> Optional[ReconciliationBreak]:
        """Assign a break to an investigator."""
        brk = self._breaks.get(break_id)
        if brk:
            brk.assigned_to = assigned_to
            brk.status = "investigating"
            brk.updated_at = datetime.now(timezone.utc)
        return brk

    def dismiss_break(
        self, break_id: str, reason: str
    ) -> Optional[ReconciliationBreak]:
        """Dismiss a break as not requiring resolution."""
        brk = self._breaks.get(break_id)
        if brk:
            brk.status = "dismissed"
            brk.updated_at = datetime.now(timezone.utc)
        return brk

    def get_break(self, break_id: str) -> Optional[ReconciliationBreak]:
        """Get a break by ID."""
        return self._breaks.get(break_id)

    def get_open_breaks(self) -> list[ReconciliationBreak]:
        """Get all open (unresolved) breaks."""
        return [
            b for b in self._breaks.values() if b.status in ("open", "investigating")
        ]

    def get_breaks_by_type(self, break_type: BreakType) -> list[ReconciliationBreak]:
        """Get all breaks of a specific type."""
        return [b for b in self._breaks.values() if b.break_type == break_type]

    def break_statistics(self) -> dict:
        """Generate break statistics."""
        breaks = list(self._breaks.values())
        if not breaks:
            return {
                "total": 0,
                "open": 0,
                "resolved": 0,
                "dismissed": 0,
                "by_type": {},
                "by_severity": {},
                "resolution_rate": 0.0,
            }

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for b in breaks:
            by_type[b.break_type.value] = by_type.get(b.break_type.value, 0) + 1
            by_severity[b.severity.value] = by_severity.get(b.severity.value, 0) + 1

        open_count = len([b for b in breaks if b.status in ("open", "investigating")])
        resolved = len([b for b in breaks if b.status == "resolved"])
        dismissed = len([b for b in breaks if b.status == "dismissed"])

        return {
            "total": len(breaks),
            "open": open_count,
            "resolved": resolved,
            "dismissed": dismissed,
            "by_type": by_type,
            "by_severity": by_severity,
            "resolution_rate": (resolved + dismissed) / len(breaks) if breaks else 0.0,
        }

    def _classify_severity(
        self, match_result: MatchResult, break_type: BreakType
    ) -> BreakSeverity:
        """Determine break severity based on type and trade details."""
        if break_type in (BreakType.MISSING_BROKER, BreakType.MISSING_INTERNAL):
            return BreakSeverity.HIGH
        if break_type == BreakType.SIDE_MISMATCH:
            return BreakSeverity.CRITICAL
        if break_type == BreakType.DUPLICATE:
            return BreakSeverity.MEDIUM

        # For price/quantity mismatches, check magnitude
        if match_result.internal_trade and match_result.broker_trade:
            notional_diff = abs(
                match_result.internal_trade.notional
                - match_result.broker_trade.notional
            )
            if notional_diff > 10000:
                return BreakSeverity.HIGH
            if notional_diff > 1000:
                return BreakSeverity.MEDIUM
        return BreakSeverity.LOW
