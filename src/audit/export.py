"""Audit event export in JSON Lines and CSV formats."""

import csv
import io
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import EventCategory
from .events import AuditEvent

logger = logging.getLogger(__name__)


class AuditExporter:
    """Export audit events in compliance-ready formats.

    Supports JSON Lines, CSV, and structured compliance reports.
    """

    def __init__(self, events: Optional[List[AuditEvent]] = None) -> None:
        """Initialize exporter with events.

        Args:
            events: List of AuditEvent objects to export.
        """
        self._events = events or []

    @property
    def events(self) -> List[AuditEvent]:
        return self._events

    @events.setter
    def events(self, value: List[AuditEvent]) -> None:
        self._events = value

    def export_json(self, pretty: bool = False) -> str:
        """Export events as JSON Lines format (one JSON object per line).

        Args:
            pretty: If True, use indented JSON (one object per line still).

        Returns:
            JSON Lines string.
        """
        lines = []
        for event in self._events:
            d = event.to_dict()
            if pretty:
                lines.append(json.dumps(d, indent=2, default=str))
            else:
                lines.append(json.dumps(d, default=str))
        return "\n".join(lines)

    def export_csv(self) -> str:
        """Export events as CSV format.

        Returns:
            CSV string with header row.
        """
        if not self._events:
            return ""

        output = io.StringIO()
        fieldnames = [
            "event_id",
            "timestamp",
            "actor_id",
            "actor_type",
            "action",
            "resource_type",
            "resource_id",
            "category",
            "outcome",
            "details",
            "event_hash",
            "previous_hash",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for event in self._events:
            row = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "actor_id": event.actor.actor_id if event.actor else "",
                "actor_type": event.actor.actor_type if event.actor else "",
                "action": event.action,
                "resource_type": (
                    event.resource.resource_type if event.resource else ""
                ),
                "resource_id": (
                    event.resource.resource_id if event.resource else ""
                ),
                "category": event.category.value,
                "outcome": event.outcome.value,
                "details": json.dumps(event.details, default=str),
                "event_hash": event.event_hash,
                "previous_hash": event.previous_hash,
            }
            writer.writerow(row)

        return output.getvalue()

    def generate_compliance_report(
        self,
        title: str = "Audit Compliance Report",
        report_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a structured compliance report.

        Args:
            title: Title for the report.
            report_period: Human-readable period description.

        Returns:
            Dictionary containing the compliance report.
        """
        now = datetime.now(timezone.utc)
        events = self._events

        # Category breakdown
        category_counts: Counter = Counter()
        for e in events:
            category_counts[e.category.value] += 1

        # Outcome breakdown
        outcome_counts: Counter = Counter()
        for e in events:
            outcome_counts[e.outcome.value] += 1

        # Actor summary
        actor_counts: Counter = Counter()
        for e in events:
            if e.actor:
                actor_counts[e.actor.actor_id] += 1

        # Action summary
        action_counts: Counter = Counter()
        for e in events:
            action_counts[e.action] += 1

        # Time range
        timestamps = [e.timestamp for e in events]
        earliest = min(timestamps).isoformat() if timestamps else None
        latest = max(timestamps).isoformat() if timestamps else None

        # Top actors
        top_actors = [
            {"actor_id": aid, "event_count": cnt}
            for aid, cnt in actor_counts.most_common(10)
        ]

        # Top actions
        top_actions = [
            {"action": act, "count": cnt}
            for act, cnt in action_counts.most_common(10)
        ]

        # Failure summary
        failure_count = outcome_counts.get("failure", 0) + outcome_counts.get(
            "error", 0
        )
        denied_count = outcome_counts.get("denied", 0)

        report = {
            "title": title,
            "generated_at": now.isoformat(),
            "report_period": report_period,
            "summary": {
                "total_events": len(events),
                "earliest_event": earliest,
                "latest_event": latest,
                "unique_actors": len(actor_counts),
                "unique_actions": len(action_counts),
                "failure_count": failure_count,
                "denied_count": denied_count,
            },
            "categories": dict(category_counts),
            "outcomes": dict(outcome_counts),
            "top_actors": top_actors,
            "top_actions": top_actions,
        }

        logger.info(
            "Generated compliance report: %d events, %d actors",
            len(events),
            len(actor_counts),
        )
        return report

    def export_report_json(
        self,
        title: str = "Audit Compliance Report",
        report_period: Optional[str] = None,
    ) -> str:
        """Generate and serialize compliance report as JSON.

        Args:
            title: Title for the report.
            report_period: Human-readable period description.

        Returns:
            JSON string of the compliance report.
        """
        report = self.generate_compliance_report(title, report_period)
        return json.dumps(report, indent=2, default=str)
