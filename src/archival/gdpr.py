"""GDPR compliance manager for data subject requests."""

import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from .config import GDPRRequestStatus, GDPRRequestType

logger = logging.getLogger(__name__)

# Default tables that may contain personal data
DEFAULT_PERSONAL_DATA_TABLES = [
    "users",
    "trade_orders",
    "trade_executions",
    "portfolio_snapshots",
    "watchlists",
    "alerts",
    "journal_entries",
    "api_usage_records",
]


@dataclass
class GDPRRequest:
    """Represents a GDPR data subject request."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    request_type: GDPRRequestType = GDPRRequestType.ACCESS
    status: GDPRRequestStatus = GDPRRequestStatus.PENDING
    tables_affected: List[str] = field(default_factory=list)
    records_affected: int = 0
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    notes: str = ""
    audit_proof: Optional[str] = None


class GDPRManager:
    """Manages GDPR data subject requests and compliance."""

    def __init__(self):
        self._requests: Dict[str, GDPRRequest] = {}
        self._deletion_log: List[dict] = []
        self._lock = threading.Lock()

    def submit_request(
        self,
        user_id: str,
        request_type: GDPRRequestType,
        tables: Optional[List[str]] = None,
        notes: str = "",
    ) -> GDPRRequest:
        """Submit a new GDPR request for a data subject."""
        with self._lock:
            affected_tables = tables if tables else list(DEFAULT_PERSONAL_DATA_TABLES)
            request = GDPRRequest(
                user_id=user_id,
                request_type=request_type,
                tables_affected=affected_tables,
                notes=notes,
            )
            self._requests[request.request_id] = request
            logger.info(
                "GDPR %s request submitted for user %s (id=%s)",
                request_type.value, user_id, request.request_id,
            )
            return request

    def process_request(self, request_id: str) -> GDPRRequest:
        """Process a pending GDPR request (simulated)."""
        with self._lock:
            request = self._requests.get(request_id)
            if not request:
                raise ValueError(f"GDPR request {request_id} not found")
            if request.status != GDPRRequestStatus.PENDING:
                raise ValueError(
                    f"Request {request_id} cannot be processed (status={request.status.value})"
                )

            request.status = GDPRRequestStatus.PROCESSING

            try:
                # Simulate processing based on request type
                total_records = 0
                for table in request.tables_affected:
                    count = random.randint(10, 500)
                    total_records += count

                request.records_affected = total_records
                request.status = GDPRRequestStatus.COMPLETED
                request.completed_at = datetime.utcnow()
                request.audit_proof = f"AUDIT-{request.request_id[:8].upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                # Log deletions
                if request.request_type == GDPRRequestType.DELETION:
                    self._deletion_log.append({
                        "request_id": request.request_id,
                        "user_id": request.user_id,
                        "tables": request.tables_affected,
                        "records_deleted": total_records,
                        "audit_proof": request.audit_proof,
                        "deleted_at": request.completed_at.isoformat(),
                    })

                logger.info(
                    "GDPR request %s completed: %d records across %d tables",
                    request_id, total_records, len(request.tables_affected),
                )
            except Exception as e:
                request.status = GDPRRequestStatus.FAILED
                request.completed_at = datetime.utcnow()
                request.notes += f" | Processing failed: {e}"
                logger.error("GDPR request %s failed: %s", request_id, e)

            return request

    def get_request(self, request_id: str) -> Optional[GDPRRequest]:
        """Retrieve a GDPR request by ID."""
        return self._requests.get(request_id)

    def list_requests(
        self,
        user_id: Optional[str] = None,
        status: Optional[GDPRRequestStatus] = None,
        request_type: Optional[GDPRRequestType] = None,
    ) -> List[GDPRRequest]:
        """List GDPR requests with optional filtering."""
        requests = list(self._requests.values())
        if user_id:
            requests = [r for r in requests if r.user_id == user_id]
        if status:
            requests = [r for r in requests if r.status == status]
        if request_type:
            requests = [r for r in requests if r.request_type == request_type]
        return requests

    def generate_export(self, user_id: str) -> dict:
        """Generate a simulated data export for a user."""
        export_data = {}
        total_records = 0
        for table in DEFAULT_PERSONAL_DATA_TABLES:
            count = random.randint(5, 200)
            export_data[table] = count
            total_records += count

        logger.info("Generated export for user %s: %d records", user_id, total_records)
        return {
            "user_id": user_id,
            "export_id": str(uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "tables": export_data,
            "total_records": total_records,
            "format": "json",
        }

    def generate_compliance_report(self) -> dict:
        """Generate a compliance summary report across all GDPR requests."""
        requests = list(self._requests.values())
        total = len(requests)

        by_type = {}
        for rt in GDPRRequestType:
            typed = [r for r in requests if r.request_type == rt]
            by_type[rt.value] = len(typed)

        by_status = {}
        for st in GDPRRequestStatus:
            statused = [r for r in requests if r.status == st]
            by_status[st.value] = len(statused)

        # Calculate average processing time for completed requests
        completed = [r for r in requests if r.status == GDPRRequestStatus.COMPLETED and r.completed_at]
        avg_processing_seconds = 0.0
        if completed:
            durations = []
            for r in completed:
                delta = (r.completed_at - r.submitted_at).total_seconds()
                durations.append(delta)
            avg_processing_seconds = sum(durations) / len(durations)

        return {
            "total_requests": total,
            "by_type": by_type,
            "by_status": by_status,
            "avg_processing_seconds": avg_processing_seconds,
            "total_records_affected": sum(r.records_affected for r in requests),
            "deletion_count": len(self._deletion_log),
            "report_generated_at": datetime.utcnow().isoformat(),
        }

    def get_deletion_log(self, user_id: Optional[str] = None) -> List[dict]:
        """Return the deletion audit log, optionally filtered by user."""
        if user_id:
            return [entry for entry in self._deletion_log if entry["user_id"] == user_id]
        return list(self._deletion_log)

    def reject_request(self, request_id: str, reason: str) -> bool:
        """Reject a pending GDPR request with a reason."""
        with self._lock:
            request = self._requests.get(request_id)
            if not request:
                return False
            if request.status != GDPRRequestStatus.PENDING:
                return False
            request.status = GDPRRequestStatus.REJECTED
            request.notes += f" | Rejected: {reason}"
            request.completed_at = datetime.utcnow()
            logger.info("GDPR request %s rejected: %s", request_id, reason)
            return True

    def reset(self) -> None:
        """Reset all manager state."""
        with self._lock:
            self._requests.clear()
            self._deletion_log.clear()
