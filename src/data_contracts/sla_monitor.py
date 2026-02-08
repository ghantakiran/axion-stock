"""SLA monitoring for data contracts - freshness, completeness, and uptime tracking."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class SLADefinition:
    """SLA thresholds for a data contract."""
    freshness_seconds: float = 300.0  # 5 minutes default
    completeness_threshold: float = 0.95  # 95% completeness
    max_violations_per_day: int = 10
    uptime_target: float = 0.999  # 99.9% uptime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "freshness_seconds": self.freshness_seconds,
            "completeness_threshold": self.completeness_threshold,
            "max_violations_per_day": self.max_violations_per_day,
            "uptime_target": self.uptime_target,
        }


@dataclass
class DeliveryRecord:
    """Record of a data delivery event."""
    delivery_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    contract_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_count: int = 0
    completeness: float = 1.0
    violations: int = 0
    is_fresh: bool = True


@dataclass
class SLAReport:
    """SLA compliance report for a contract over a period."""
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    contract_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    freshness_met: bool = True
    completeness_met: bool = True
    violations_count: int = 0
    violations_within_limit: bool = True
    compliance_pct: float = 100.0
    total_deliveries: int = 0
    total_records: int = 0
    avg_completeness: float = 1.0
    uptime_pct: float = 100.0

    @property
    def is_compliant(self) -> bool:
        """Overall SLA compliance check."""
        return self.freshness_met and self.completeness_met and self.violations_within_limit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "contract_id": self.contract_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "freshness_met": self.freshness_met,
            "completeness_met": self.completeness_met,
            "violations_count": self.violations_count,
            "violations_within_limit": self.violations_within_limit,
            "compliance_pct": self.compliance_pct,
            "total_deliveries": self.total_deliveries,
            "total_records": self.total_records,
            "avg_completeness": self.avg_completeness,
            "is_compliant": self.is_compliant,
        }


class SLAMonitor:
    """Monitors SLA compliance for data contracts.

    Tracks delivery freshness, data completeness, violation counts,
    and generates compliance reports.
    """

    def __init__(self):
        self._sla_definitions: Dict[str, SLADefinition] = {}
        self._deliveries: Dict[str, List[DeliveryRecord]] = {}
        self._violation_counts: Dict[str, List[datetime]] = {}
        self._reports: Dict[str, List[SLAReport]] = {}

    def set_sla(self, contract_id: str, sla: SLADefinition) -> None:
        """Set or update the SLA definition for a contract."""
        self._sla_definitions[contract_id] = sla
        if contract_id not in self._deliveries:
            self._deliveries[contract_id] = []
        if contract_id not in self._violation_counts:
            self._violation_counts[contract_id] = []
        if contract_id not in self._reports:
            self._reports[contract_id] = []

    def get_sla(self, contract_id: str) -> Optional[SLADefinition]:
        """Get SLA definition for a contract."""
        return self._sla_definitions.get(contract_id)

    def record_delivery(
        self,
        contract_id: str,
        timestamp: Optional[datetime] = None,
        record_count: int = 0,
        completeness: float = 1.0,
    ) -> DeliveryRecord:
        """Record a data delivery event."""
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        sla = self._sla_definitions.get(contract_id)
        is_fresh = True
        if sla:
            now = datetime.now(timezone.utc)
            age = (now - ts).total_seconds()
            is_fresh = age <= sla.freshness_seconds

        delivery = DeliveryRecord(
            contract_id=contract_id,
            timestamp=ts,
            record_count=record_count,
            completeness=completeness,
            is_fresh=is_fresh,
        )

        if contract_id not in self._deliveries:
            self._deliveries[contract_id] = []
        self._deliveries[contract_id].append(delivery)

        return delivery

    def record_violation(self, contract_id: str) -> None:
        """Record a violation occurrence for a contract."""
        if contract_id not in self._violation_counts:
            self._violation_counts[contract_id] = []
        self._violation_counts[contract_id].append(datetime.now(timezone.utc))

    def check_sla(self, contract_id: str, period_hours: int = 24) -> SLAReport:
        """Check SLA compliance for a contract over a period.

        Evaluates freshness, completeness, and violation limits.
        """
        sla = self._sla_definitions.get(contract_id)
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=period_hours)

        report = SLAReport(
            contract_id=contract_id,
            period_start=period_start,
            period_end=now,
        )

        if not sla:
            return report

        # Get deliveries in period
        deliveries = [
            d for d in self._deliveries.get(contract_id, [])
            if d.timestamp >= period_start
        ]

        report.total_deliveries = len(deliveries)
        report.total_records = sum(d.record_count for d in deliveries)

        # Freshness check
        if deliveries:
            latest = max(deliveries, key=lambda d: d.timestamp)
            age = (now - latest.timestamp).total_seconds()
            report.freshness_met = age <= sla.freshness_seconds
        else:
            report.freshness_met = False

        # Completeness check
        if deliveries:
            report.avg_completeness = sum(d.completeness for d in deliveries) / len(deliveries)
            report.completeness_met = report.avg_completeness >= sla.completeness_threshold
        else:
            report.avg_completeness = 0.0
            report.completeness_met = False

        # Violation count check
        violations_in_period = [
            v for v in self._violation_counts.get(contract_id, [])
            if v >= period_start
        ]
        report.violations_count = len(violations_in_period)
        report.violations_within_limit = report.violations_count <= sla.max_violations_per_day

        # Compute compliance percentage
        checks = [
            report.freshness_met,
            report.completeness_met,
            report.violations_within_limit,
        ]
        report.compliance_pct = (sum(1 for c in checks if c) / len(checks)) * 100.0

        # Store report
        if contract_id not in self._reports:
            self._reports[contract_id] = []
        self._reports[contract_id].append(report)

        return report

    def get_compliance_history(
        self,
        contract_id: str,
        days: int = 7,
    ) -> List[SLAReport]:
        """Get historical SLA compliance reports for a contract."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            r for r in self._reports.get(contract_id, [])
            if r.period_end >= cutoff
        ]

    def overall_compliance(self) -> Dict[str, Any]:
        """Get overall compliance summary across all monitored contracts."""
        total_contracts = len(self._sla_definitions)
        if total_contracts == 0:
            return {
                "total_contracts": 0,
                "compliant": 0,
                "non_compliant": 0,
                "compliance_rate": 100.0,
                "contracts": {},
            }

        contract_status: Dict[str, Dict[str, Any]] = {}
        compliant_count = 0

        for contract_id in self._sla_definitions:
            report = self.check_sla(contract_id)
            is_compliant = report.is_compliant
            if is_compliant:
                compliant_count += 1
            contract_status[contract_id] = {
                "compliant": is_compliant,
                "compliance_pct": report.compliance_pct,
                "freshness_met": report.freshness_met,
                "completeness_met": report.completeness_met,
                "violations_count": report.violations_count,
            }

        return {
            "total_contracts": total_contracts,
            "compliant": compliant_count,
            "non_compliant": total_contracts - compliant_count,
            "compliance_rate": (compliant_count / total_contracts) * 100.0,
            "contracts": contract_status,
        }

    def get_delivery_history(
        self,
        contract_id: str,
        hours: int = 24,
    ) -> List[DeliveryRecord]:
        """Get delivery history for a contract."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            d for d in self._deliveries.get(contract_id, [])
            if d.timestamp >= cutoff
        ]
