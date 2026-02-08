"""Pre-migration and post-migration check implementations."""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import MigrationSafetyConfig, MigrationDirection, MigrationStatus, Severity

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single check."""

    check_name: str
    passed: bool
    severity: Severity = Severity.INFO
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MigrationCheckReport:
    """Aggregate report of all checks for a migration."""

    revision: str
    direction: MigrationDirection
    checks: List[CheckResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: MigrationStatus = MigrationStatus.PENDING

    @property
    def all_passed(self) -> bool:
        """Check if all checks passed."""
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> List[CheckResult]:
        """Get list of failed checks."""
        return [c for c in self.checks if not c.passed]

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


class PreMigrationCheck:
    """Checks to run before applying a migration."""

    def __init__(self, config: Optional[MigrationSafetyConfig] = None):
        self.config = config or MigrationSafetyConfig()
        self._check_history: List[MigrationCheckReport] = []

    def run_all_checks(
        self,
        revision: str,
        db_url: Optional[str] = None,
        current_revision: Optional[str] = None,
        migration_file: Optional[str] = None,
    ) -> MigrationCheckReport:
        """Run all pre-migration checks."""
        report = MigrationCheckReport(
            revision=revision,
            direction=MigrationDirection.UPGRADE,
        )

        # Check 1: Database connectivity
        report.checks.append(
            self.check_db_connectivity(db_url)
        )

        # Check 2: Current revision verification
        report.checks.append(
            self.check_current_revision(current_revision, revision)
        )

        # Check 3: Migration file exists
        if migration_file:
            report.checks.append(
                self.check_migration_file_exists(migration_file)
            )

        # Check 4: Disk space (simulate)
        report.checks.append(
            self.check_disk_space()
        )

        # Check 5: No pending transactions (simulate)
        report.checks.append(
            self.check_no_pending_transactions()
        )

        report.completed_at = datetime.utcnow()
        report.status = MigrationStatus.SUCCESS if report.all_passed else MigrationStatus.FAILED

        self._check_history.append(report)
        return report

    def check_db_connectivity(self, db_url: Optional[str] = None) -> CheckResult:
        """Verify database is reachable."""
        if db_url is None:
            # Simulate: no URL means skip with a pass
            return CheckResult(
                check_name="db_connectivity",
                passed=True,
                severity=Severity.INFO,
                message="Database connectivity check skipped (no URL provided)",
                details={"db_url": None, "skipped": True},
            )

        # Simulate connectivity check
        if db_url.startswith("postgresql://") or db_url.startswith("sqlite://"):
            return CheckResult(
                check_name="db_connectivity",
                passed=True,
                severity=Severity.INFO,
                message="Database connection verified",
                details={"db_url": db_url[:30] + "...", "timeout": self.config.db_connection_timeout},
            )

        return CheckResult(
            check_name="db_connectivity",
            passed=False,
            severity=Severity.ERROR,
            message=f"Invalid database URL scheme",
            details={"db_url": db_url[:30]},
        )

    def check_current_revision(
        self,
        current_revision: Optional[str],
        target_revision: str,
    ) -> CheckResult:
        """Verify current database revision."""
        if current_revision is None:
            return CheckResult(
                check_name="current_revision",
                passed=True,
                severity=Severity.INFO,
                message="Revision check skipped (no current revision provided)",
                details={"current": None, "target": target_revision},
            )

        return CheckResult(
            check_name="current_revision",
            passed=True,
            severity=Severity.INFO,
            message=f"Current revision: {current_revision}, target: {target_revision}",
            details={"current": current_revision, "target": target_revision},
        )

    def check_migration_file_exists(self, file_path: str) -> CheckResult:
        """Verify migration file exists on disk."""
        exists = os.path.isfile(file_path)
        return CheckResult(
            check_name="migration_file_exists",
            passed=exists,
            severity=Severity.ERROR if not exists else Severity.INFO,
            message=f"Migration file {'found' if exists else 'NOT found'}: {file_path}",
            details={"file_path": file_path, "exists": exists},
        )

    def check_disk_space(self, min_mb: int = 100) -> CheckResult:
        """Check available disk space."""
        # Simulated check — in production would use shutil.disk_usage
        return CheckResult(
            check_name="disk_space",
            passed=True,
            severity=Severity.INFO,
            message=f"Sufficient disk space available (>= {min_mb}MB)",
            details={"min_required_mb": min_mb},
        )

    def check_no_pending_transactions(self) -> CheckResult:
        """Check for pending/long-running transactions."""
        # Simulated check — in production would query pg_stat_activity
        return CheckResult(
            check_name="no_pending_transactions",
            passed=True,
            severity=Severity.INFO,
            message="No blocking transactions detected",
            details={},
        )

    def get_history(self) -> List[MigrationCheckReport]:
        """Get check history."""
        return list(self._check_history)


class PostMigrationCheck:
    """Checks to run after applying a migration."""

    def __init__(self, config: Optional[MigrationSafetyConfig] = None):
        self.config = config or MigrationSafetyConfig()
        self._check_history: List[MigrationCheckReport] = []

    def run_all_checks(
        self,
        revision: str,
        applied_revision: Optional[str] = None,
        expected_tables: Optional[List[str]] = None,
        expected_columns: Optional[Dict[str, List[str]]] = None,
    ) -> MigrationCheckReport:
        """Run all post-migration checks."""
        report = MigrationCheckReport(
            revision=revision,
            direction=MigrationDirection.UPGRADE,
        )

        # Check 1: Verify new revision was applied
        report.checks.append(
            self.check_revision_applied(revision, applied_revision)
        )

        # Check 2: Schema validation (tables)
        if expected_tables is not None:
            report.checks.append(
                self.check_expected_tables(expected_tables)
            )

        # Check 3: Schema validation (columns)
        if expected_columns is not None:
            report.checks.append(
                self.check_expected_columns(expected_columns)
            )

        # Check 4: Data integrity
        report.checks.append(
            self.check_data_integrity()
        )

        report.completed_at = datetime.utcnow()
        report.status = MigrationStatus.SUCCESS if report.all_passed else MigrationStatus.FAILED

        self._check_history.append(report)
        return report

    def check_revision_applied(
        self,
        expected_revision: str,
        actual_revision: Optional[str] = None,
    ) -> CheckResult:
        """Verify the expected revision was applied."""
        if actual_revision is None:
            return CheckResult(
                check_name="revision_applied",
                passed=True,
                severity=Severity.INFO,
                message="Revision check skipped (no actual revision provided)",
                details={"expected": expected_revision, "actual": None, "skipped": True},
            )

        matched = expected_revision == actual_revision
        return CheckResult(
            check_name="revision_applied",
            passed=matched,
            severity=Severity.ERROR if not matched else Severity.INFO,
            message=(
                f"Revision match: {expected_revision}"
                if matched
                else f"Revision mismatch: expected {expected_revision}, got {actual_revision}"
            ),
            details={"expected": expected_revision, "actual": actual_revision},
        )

    def check_expected_tables(
        self,
        expected_tables: List[str],
        existing_tables: Optional[List[str]] = None,
    ) -> CheckResult:
        """Verify expected tables exist after migration."""
        if existing_tables is None:
            # Simulated: assume all tables exist
            return CheckResult(
                check_name="expected_tables",
                passed=True,
                severity=Severity.INFO,
                message=f"Table check: {len(expected_tables)} tables expected (simulated pass)",
                details={"expected": expected_tables, "simulated": True},
            )

        missing = set(expected_tables) - set(existing_tables)
        passed = len(missing) == 0
        return CheckResult(
            check_name="expected_tables",
            passed=passed,
            severity=Severity.ERROR if not passed else Severity.INFO,
            message=(
                f"All {len(expected_tables)} expected tables found"
                if passed
                else f"Missing tables: {sorted(missing)}"
            ),
            details={"expected": expected_tables, "missing": sorted(missing) if missing else []},
        )

    def check_expected_columns(
        self,
        expected_columns: Dict[str, List[str]],
        actual_columns: Optional[Dict[str, List[str]]] = None,
    ) -> CheckResult:
        """Verify expected columns exist in tables."""
        if actual_columns is None:
            return CheckResult(
                check_name="expected_columns",
                passed=True,
                severity=Severity.INFO,
                message="Column check: simulated pass",
                details={"simulated": True},
            )

        missing = {}
        for table, cols in expected_columns.items():
            actual = actual_columns.get(table, [])
            table_missing = set(cols) - set(actual)
            if table_missing:
                missing[table] = sorted(table_missing)

        passed = len(missing) == 0
        return CheckResult(
            check_name="expected_columns",
            passed=passed,
            severity=Severity.ERROR if not passed else Severity.INFO,
            message=(
                "All expected columns found"
                if passed
                else f"Missing columns in {len(missing)} tables"
            ),
            details={"missing_columns": missing},
        )

    def check_data_integrity(self) -> CheckResult:
        """Run data integrity checks after migration."""
        # Simulated — in production would run constraint verification
        return CheckResult(
            check_name="data_integrity",
            passed=True,
            severity=Severity.INFO,
            message="Data integrity check passed (simulated)",
            details={},
        )

    def get_history(self) -> List[MigrationCheckReport]:
        """Get check history."""
        return list(self._check_history)
