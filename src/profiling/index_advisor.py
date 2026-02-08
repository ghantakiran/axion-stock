"""Index recommendation engine for query optimization."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.profiling.config import IndexStatus
from src.profiling.query_profiler import QueryProfiler

logger = logging.getLogger(__name__)


@dataclass
class IndexRecommendation:
    """A recommended database index with lifecycle tracking."""

    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str = ""
    columns: List[str] = field(default_factory=list)
    index_type: str = "btree"
    rationale: str = ""
    estimated_impact: str = "medium"
    status: IndexStatus = IndexStatus.RECOMMENDED
    created_at: datetime = field(default_factory=datetime.now)
    query_fingerprints: List[str] = field(default_factory=list)


class IndexAdvisor:
    """Analyzes query patterns and recommends database indexes."""

    def __init__(self):
        self._recommendations: Dict[str, IndexRecommendation] = {}
        self._unused_indexes: List[Dict] = []
        self._lock = threading.Lock()

    def analyze_query_patterns(
        self, profiler: QueryProfiler
    ) -> List[IndexRecommendation]:
        """Analyze queries from a profiler and generate index recommendations.

        Heuristic: looks for frequently executed queries with WHERE/JOIN clauses
        and suggests indexes on commonly referenced columns.
        """
        recommendations = []
        top_queries = profiler.get_top_queries(n=20, sort_by="total_duration")

        for fp in top_queries:
            template = fp.query_template.upper()

            # Extract table and column references from WHERE clauses
            table_name = self._extract_table(template)
            columns = self._extract_where_columns(template)

            if table_name and columns and fp.call_count >= 5:
                impact = "high" if fp.avg_duration_ms > 500 else "medium"
                rec = self.add_recommendation(
                    table=table_name.lower(),
                    columns=[c.lower() for c in columns],
                    rationale=(
                        f"Query executed {fp.call_count} times with avg "
                        f"{fp.avg_duration_ms:.1f}ms. Index may improve WHERE clause."
                    ),
                    index_type="btree",
                    impact=impact,
                )
                rec.query_fingerprints.append(fp.fingerprint)
                recommendations.append(rec)

        if recommendations:
            logger.info(
                "Generated %d index recommendations from query analysis",
                len(recommendations),
            )

        return recommendations

    def add_recommendation(
        self,
        table: str,
        columns: List[str],
        rationale: str,
        index_type: str = "btree",
        impact: str = "medium",
    ) -> IndexRecommendation:
        """Manually add an index recommendation."""
        rec = IndexRecommendation(
            table_name=table,
            columns=columns,
            index_type=index_type,
            rationale=rationale,
            estimated_impact=impact,
        )
        with self._lock:
            self._recommendations[rec.recommendation_id] = rec
        logger.info(
            "Index recommendation added: %s on %s(%s)",
            rec.recommendation_id,
            table,
            ", ".join(columns),
        )
        return rec

    def approve(self, rec_id: str) -> bool:
        """Approve an index recommendation for application."""
        with self._lock:
            rec = self._recommendations.get(rec_id)
            if rec and rec.status == IndexStatus.RECOMMENDED:
                rec.status = IndexStatus.APPROVED
                logger.info("Index recommendation %s approved", rec_id)
                return True
        return False

    def reject(self, rec_id: str) -> bool:
        """Reject an index recommendation."""
        with self._lock:
            rec = self._recommendations.get(rec_id)
            if rec and rec.status in (IndexStatus.RECOMMENDED, IndexStatus.APPROVED):
                rec.status = IndexStatus.REJECTED
                logger.info("Index recommendation %s rejected", rec_id)
                return True
        return False

    def mark_applied(self, rec_id: str) -> bool:
        """Mark an approved recommendation as applied."""
        with self._lock:
            rec = self._recommendations.get(rec_id)
            if rec and rec.status == IndexStatus.APPROVED:
                rec.status = IndexStatus.APPLIED
                logger.info("Index recommendation %s marked as applied", rec_id)
                return True
        return False

    def report_unused_index(
        self, index_name: str, table_name: str, reason: str
    ) -> dict:
        """Report an unused index that may be a candidate for removal."""
        entry = {
            "index_name": index_name,
            "table_name": table_name,
            "reason": reason,
            "reported_at": datetime.now().isoformat(),
        }
        with self._lock:
            self._unused_indexes.append(entry)
        logger.info("Unused index reported: %s on %s", index_name, table_name)
        return entry

    def get_recommendations(
        self, status: Optional[IndexStatus] = None
    ) -> List[IndexRecommendation]:
        """Get recommendations filtered by status."""
        with self._lock:
            recs = list(self._recommendations.values())
        if status is not None:
            recs = [r for r in recs if r.status == status]
        return recs

    def get_unused_indexes(self) -> List[Dict]:
        """Get all reported unused indexes."""
        with self._lock:
            return list(self._unused_indexes)

    def get_summary(self) -> dict:
        """Summary of index advisory state."""
        with self._lock:
            recs = list(self._recommendations.values())
            status_counts = {}
            for r in recs:
                status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1

            return {
                "total_recommendations": len(recs),
                "by_status": status_counts,
                "unused_indexes": len(self._unused_indexes),
            }

    def reset(self) -> None:
        """Clear all recommendations and unused index reports."""
        with self._lock:
            self._recommendations.clear()
            self._unused_indexes.clear()

    @staticmethod
    def _extract_table(query: str) -> Optional[str]:
        """Extract primary table name from a query template."""
        import re

        # FROM table_name
        match = re.search(r"\bFROM\s+(\w+)", query)
        if match:
            return match.group(1)
        # UPDATE table_name
        match = re.search(r"\bUPDATE\s+(\w+)", query)
        if match:
            return match.group(1)
        # INSERT INTO table_name
        match = re.search(r"\bINTO\s+(\w+)", query)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_where_columns(query: str) -> List[str]:
        """Extract column names from WHERE clause conditions."""
        import re

        columns = []
        # Match patterns like: column_name = ?, column_name > ?, column_name IN (...)
        matches = re.findall(r"\bWHERE\b(.+?)(?:\bORDER\b|\bGROUP\b|\bLIMIT\b|$)", query)
        if matches:
            where_clause = matches[0]
            col_matches = re.findall(r"(\w+)\s*(?:=|>|<|>=|<=|!=|IN|LIKE|BETWEEN)", where_clause)
            columns = [c for c in col_matches if c not in ("AND", "OR", "NOT")]
        return columns
