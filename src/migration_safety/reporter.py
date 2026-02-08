"""Validation report generation for migration safety."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import MigrationSafetyConfig, Severity
from .linter import LintReport
from .validator import MigrationValidator, ValidationResult

logger = logging.getLogger(__name__)


class ValidationReporter:
    """Generate human-readable and machine-readable validation reports."""

    def __init__(self, config: Optional[MigrationSafetyConfig] = None):
        self.config = config or MigrationSafetyConfig()

    def generate_text_report(
        self,
        results: Dict[str, ValidationResult],
        lint_report: Optional[LintReport] = None,
    ) -> str:
        """Generate a human-readable text report.

        Args:
            results: Mapping of file paths to validation results.
            lint_report: Optional lint report to include.

        Returns:
            Formatted text report.
        """
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("Migration Safety Report")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        total = len(results)
        safe = sum(1 for r in results.values() if r.is_safe)
        avg_score = (
            sum(r.safety_score for r in results.values()) / total
            if total > 0
            else 0.0
        )
        lines.append(f"Total Migrations: {total}")
        lines.append(f"Safe: {safe} | Unsafe: {total - safe}")
        lines.append(f"Average Safety Score: {avg_score:.1%}")
        lines.append("")

        # Per-file details
        for fpath, result in sorted(results.items()):
            status = "SAFE" if result.is_safe else "UNSAFE"
            lines.append(f"--- {os.path.basename(fpath)} [{status}] (score: {result.safety_score:.0%})")
            if result.revision:
                lines.append(f"    Revision: {result.revision}")
            if not result.has_downgrade:
                lines.append("    WARNING: No downgrade implementation")
            if result.has_destructive_ops:
                lines.append(f"    CRITICAL: Destructive ops: {result.destructive_ops}")
            if result.has_data_migration:
                lines.append(f"    WARNING: Data migration ops: {result.data_migration_ops}")
            if result.missing_indexes:
                lines.append(f"    WARNING: Missing indexes: {result.missing_indexes}")
            for err in result.errors:
                lines.append(f"    ERROR: {err}")
            lines.append("")

        # Lint report
        if lint_report and lint_report.total_issues > 0:
            lines.append("-" * 60)
            lines.append(f"Lint Issues: {lint_report.total_issues}")
            for issue in lint_report.issues:
                lines.append(f"  [{issue.severity.value.upper()}] {issue.rule_id}: {issue.message}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_json_report(
        self,
        results: Dict[str, ValidationResult],
        lint_report: Optional[LintReport] = None,
    ) -> str:
        """Generate a JSON report.

        Args:
            results: Mapping of file paths to validation results.
            lint_report: Optional lint report to include.

        Returns:
            JSON string.
        """
        total = len(results)
        safe = sum(1 for r in results.values() if r.is_safe)

        report: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_migrations": total,
                "safe_migrations": safe,
                "unsafe_migrations": total - safe,
                "average_safety_score": round(
                    sum(r.safety_score for r in results.values()) / total
                    if total > 0
                    else 0.0,
                    3,
                ),
            },
            "migrations": {},
        }

        for fpath, result in sorted(results.items()):
            report["migrations"][fpath] = {
                "revision": result.revision,
                "down_revision": result.down_revision,
                "is_safe": result.is_safe,
                "safety_score": round(result.safety_score, 3),
                "has_downgrade": result.has_downgrade,
                "has_destructive_ops": result.has_destructive_ops,
                "destructive_ops": result.destructive_ops,
                "has_data_migration": result.has_data_migration,
                "missing_indexes": result.missing_indexes,
                "errors": result.errors,
                "warnings": result.warnings,
            }

        if lint_report:
            report["lint"] = {
                "total_issues": lint_report.total_issues,
                "files_checked": lint_report.files_checked,
                "files_with_issues": lint_report.files_with_issues,
                "issues": [
                    {
                        "file_path": i.file_path,
                        "severity": i.severity.value,
                        "rule_id": i.rule_id,
                        "message": i.message,
                    }
                    for i in lint_report.issues
                ],
            }

        return json.dumps(report, indent=2, default=str)


# Import here to avoid circular import in text report
import os
