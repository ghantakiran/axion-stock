"""PRD-126: Trade Reconciliation — Reporting."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import ReconciliationStatus
from .matcher import MatchResult


@dataclass
class ReconciliationReport:
    """Summary report for a reconciliation period."""

    report_id: str
    period_start: datetime
    period_end: datetime
    total_internal: int
    total_broker: int
    matched: int
    broken: int
    resolved: int
    match_rate: float
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    break_details: list[dict] = field(default_factory=list)


@dataclass
class DailyReconciliation:
    """Daily reconciliation summary."""

    date: datetime
    statistics: dict
    breaks: list[dict]
    settlements: list[dict]
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


class ReconciliationReporter:
    """Generates reconciliation reports and analytics."""

    def __init__(self) -> None:
        self._reports: list[ReconciliationReport] = []
        self._daily_records: dict[str, DailyReconciliation] = {}

    def generate_report(
        self,
        results: list[MatchResult],
        period_start: datetime,
        period_end: datetime,
    ) -> ReconciliationReport:
        """Generate a reconciliation report from match results."""
        matched = [r for r in results if r.status == ReconciliationStatus.MATCHED]
        broken = [r for r in results if r.status == ReconciliationStatus.BROKEN]
        resolved = [r for r in results if r.status == ReconciliationStatus.RESOLVED]

        internal_count = len(
            [r for r in results if r.internal_trade is not None]
        )
        broker_count = len([r for r in results if r.broker_trade is not None])

        report = ReconciliationReport(
            report_id=uuid.uuid4().hex[:16],
            period_start=period_start,
            period_end=period_end,
            total_internal=internal_count,
            total_broker=broker_count,
            matched=len(matched),
            broken=len(broken),
            resolved=len(resolved),
            match_rate=len(matched) / max(internal_count, 1),
            break_details=[
                {
                    "match_id": r.match_id,
                    "break_type": r.break_type.value if r.break_type else None,
                    "confidence": r.confidence,
                }
                for r in broken
            ],
        )
        self._reports.append(report)
        return report

    def record_daily(
        self,
        date: datetime,
        statistics: dict,
        breaks: Optional[list[dict]] = None,
        settlements: Optional[list[dict]] = None,
    ) -> DailyReconciliation:
        """Record daily reconciliation data."""
        daily = DailyReconciliation(
            date=date,
            statistics=statistics,
            breaks=breaks or [],
            settlements=settlements or [],
        )
        date_key = date.strftime("%Y-%m-%d")
        self._daily_records[date_key] = daily
        return daily

    def aging_report(self, breaks: list[dict]) -> dict:
        """Generate an aging report for open breaks."""
        now = datetime.now(timezone.utc)
        aging: dict[str, int] = {
            "0-1_days": 0,
            "1-3_days": 0,
            "3-7_days": 0,
            "7-14_days": 0,
            "14+_days": 0,
        }
        for brk in breaks:
            created = brk.get("created_at", now)
            if isinstance(created, str):
                continue
            age_days = (now - created).days
            if age_days < 1:
                aging["0-1_days"] += 1
            elif age_days < 3:
                aging["1-3_days"] += 1
            elif age_days < 7:
                aging["3-7_days"] += 1
            elif age_days < 14:
                aging["7-14_days"] += 1
            else:
                aging["14+_days"] += 1
        return aging

    def trend_analysis(self, days: int = 30) -> dict:
        """Analyze matching trends over a period."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        relevant_reports = [
            r for r in self._reports if r.generated_at >= cutoff
        ]

        if not relevant_reports:
            return {
                "period_days": days,
                "reports_count": 0,
                "avg_match_rate": 0.0,
                "trend": "no_data",
            }

        match_rates = [r.match_rate for r in relevant_reports]
        avg_rate = sum(match_rates) / len(match_rates)

        # Simple trend: compare first half vs second half
        mid = len(match_rates) // 2
        if mid > 0:
            first_half = sum(match_rates[:mid]) / mid
            second_half = sum(match_rates[mid:]) / len(match_rates[mid:])
            if second_half > first_half + 0.01:
                trend = "improving"
            elif second_half < first_half - 0.01:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "period_days": days,
            "reports_count": len(relevant_reports),
            "avg_match_rate": avg_rate,
            "min_match_rate": min(match_rates),
            "max_match_rate": max(match_rates),
            "trend": trend,
        }

    def get_reports(self) -> list[ReconciliationReport]:
        """Get all generated reports."""
        return list(self._reports)

    def get_daily_records(self) -> dict[str, DailyReconciliation]:
        """Get all daily reconciliation records."""
        return dict(self._daily_records)
