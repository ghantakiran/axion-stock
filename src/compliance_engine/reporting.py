"""Regulatory reporting for compliance engine."""

import uuid
from datetime import date, datetime
from typing import Dict, List, Optional

from .config import ReportType
from .models import (
    BestExecutionReport,
    ComplianceSummary,
    RegulatoryFiling,
    SurveillanceAlert,
)


class RegulatoryReporter:
    """Generates compliance and regulatory reports."""

    def __init__(self):
        self._filings: List[RegulatoryFiling] = []

    def generate_daily_compliance(
        self,
        report_date: date,
        alerts: List[SurveillanceAlert],
        blackout_violations: int = 0,
        pre_clearance_pending: int = 0,
        best_exec: Optional[BestExecutionReport] = None,
    ) -> RegulatoryFiling:
        """Generate daily compliance summary report."""
        unresolved = len([a for a in alerts if not a.is_resolved])
        critical = len([a for a in alerts if a.severity == "critical" and not a.is_resolved])

        alert_breakdown = {}
        for a in alerts:
            alert_breakdown[a.alert_type] = alert_breakdown.get(a.alert_type, 0) + 1

        content = {
            "total_alerts": len(alerts),
            "unresolved_alerts": unresolved,
            "critical_alerts": critical,
            "alert_breakdown": alert_breakdown,
            "blackout_violations": blackout_violations,
            "pre_clearance_pending": pre_clearance_pending,
            "best_execution": {
                "avg_slippage_bps": best_exec.avg_slippage_bps if best_exec else 0,
                "overall_quality": best_exec.overall_quality if best_exec else "N/A",
                "total_orders": best_exec.total_orders if best_exec else 0,
            } if best_exec else {},
        }

        status = "compliant"
        if critical > 0 or blackout_violations > 0:
            status = "non_compliant"
        elif unresolved > 5:
            status = "review_required"

        filing = RegulatoryFiling(
            filing_id=str(uuid.uuid4())[:8],
            report_type=ReportType.DAILY_COMPLIANCE.value,
            title=f"Daily Compliance Report - {report_date.isoformat()}",
            period_start=report_date,
            period_end=report_date,
            content={**content, "status": status},
        )
        self._filings.append(filing)
        return filing

    def generate_surveillance_summary(
        self,
        period_start: date,
        period_end: date,
        alerts: List[SurveillanceAlert],
    ) -> RegulatoryFiling:
        """Generate surveillance summary for a period."""
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        resolved = 0
        unresolved = 0

        for a in alerts:
            by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            if a.is_resolved:
                resolved += 1
            else:
                unresolved += 1

        filing = RegulatoryFiling(
            filing_id=str(uuid.uuid4())[:8],
            report_type=ReportType.SURVEILLANCE_SUMMARY.value,
            title=f"Surveillance Summary {period_start} to {period_end}",
            period_start=period_start,
            period_end=period_end,
            content={
                "total_alerts": len(alerts),
                "resolved": resolved,
                "unresolved": unresolved,
                "by_type": by_type,
                "by_severity": by_severity,
                "resolution_rate": resolved / max(len(alerts), 1),
            },
        )
        self._filings.append(filing)
        return filing

    def generate_best_execution_filing(
        self,
        report: BestExecutionReport,
    ) -> RegulatoryFiling:
        """Generate best execution regulatory filing."""
        filing = RegulatoryFiling(
            filing_id=str(uuid.uuid4())[:8],
            report_type=ReportType.BEST_EXECUTION.value,
            title=f"Best Execution Report {report.period_start} to {report.period_end}",
            period_start=report.period_start,
            period_end=report.period_end,
            content={
                "total_orders": report.total_orders,
                "avg_slippage_bps": report.avg_slippage_bps,
                "avg_price_improvement_bps": report.avg_price_improvement_bps,
                "quality_distribution": {
                    "excellent": report.excellent_pct,
                    "good": report.good_pct,
                    "poor": report.poor_pct,
                    "failed": report.failed_pct,
                },
                "total_cost_saved": report.total_cost_saved,
                "overall_quality": report.overall_quality,
                "by_venue": report.by_venue,
            },
        )
        self._filings.append(filing)
        return filing

    def generate_compliance_summary(
        self,
        period: str,
        alerts: List[SurveillanceAlert],
        blackout_violations: int = 0,
        best_exec: Optional[BestExecutionReport] = None,
        pre_clearance_pending: int = 0,
        filings_due: int = 0,
    ) -> ComplianceSummary:
        """Generate overall compliance health summary."""
        unresolved = len([a for a in alerts if not a.is_resolved])
        critical = len([a for a in alerts if a.severity == "critical" and not a.is_resolved])

        status = "compliant"
        if critical > 0 or blackout_violations > 0:
            status = "non_compliant"
        elif unresolved > 3:
            status = "review_required"

        return ComplianceSummary(
            period=period,
            surveillance_alerts=len(alerts),
            unresolved_alerts=unresolved,
            blackout_violations=blackout_violations,
            best_execution_score=100 - (best_exec.avg_slippage_bps if best_exec else 0),
            pre_clearance_pending=pre_clearance_pending,
            filings_due=filings_due,
            overall_status=status,
        )

    def mark_filed(self, filing_id: str) -> bool:
        for f in self._filings:
            if f.filing_id == filing_id and not f.filed:
                f.filed = True
                f.filed_at = datetime.now()
                return True
        return False

    def get_filings(
        self, report_type: Optional[str] = None, unfiled_only: bool = False
    ) -> List[RegulatoryFiling]:
        filings = self._filings
        if report_type:
            filings = [f for f in filings if f.report_type == report_type]
        if unfiled_only:
            filings = [f for f in filings if not f.filed]
        return filings
