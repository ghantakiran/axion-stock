"""Migration linter with configurable rules."""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import MigrationSafetyConfig, RuleConfig, Severity
from .validator import MigrationValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class LintIssue:
    """A single linting issue found in a migration file."""

    file_path: str
    line_number: int = 0
    severity: Severity = Severity.WARNING
    rule_id: str = ""
    message: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.rule_id}: {self.file_path}:{self.line_number} - {self.message}"


@dataclass
class LintReport:
    """Aggregate report of all lint issues."""

    issues: List[LintIssue] = field(default_factory=list)
    files_checked: int = 0
    files_with_issues: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity in (Severity.ERROR, Severity.CRITICAL))

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def get_issues_by_severity(self, severity: Severity) -> List[LintIssue]:
        return [i for i in self.issues if i.severity == severity]

    def summary(self) -> Dict[str, int]:
        return {
            "files_checked": self.files_checked,
            "files_with_issues": self.files_with_issues,
            "total_issues": self.total_issues,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "info": self.info_count,
        }


class MigrationLinter:
    """Lint migration files against configurable rules.

    Uses MigrationValidator for AST analysis and maps validation
    results to lint issues based on configured rules.
    """

    def __init__(self, config: Optional[MigrationSafetyConfig] = None):
        self.config = config or MigrationSafetyConfig()
        self._validator = MigrationValidator(self.config)

    def lint_file(self, file_path: str) -> List[LintIssue]:
        """Lint a single migration file.

        Returns list of LintIssue objects.
        """
        result = self._validator.validate_file(file_path)
        return self._result_to_issues(result)

    def lint_directory(self, directory: str) -> LintReport:
        """Lint all migration files in a directory.

        Returns a LintReport with all issues.
        """
        report = LintReport()

        if not os.path.isdir(directory):
            logger.error("Directory not found: %s", directory)
            return report

        files_with_issues = set()
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(directory, filename)
                issues = self.lint_file(file_path)
                report.files_checked += 1
                if issues:
                    files_with_issues.add(file_path)
                    report.issues.extend(issues)

        report.files_with_issues = len(files_with_issues)
        logger.info(
            "Linted %d files: %d issues found",
            report.files_checked,
            report.total_issues,
        )
        return report

    def _result_to_issues(self, result: ValidationResult) -> List[LintIssue]:
        """Convert a ValidationResult into a list of LintIssues."""
        issues: List[LintIssue] = []
        rules = self.config.get_enabled_rules()

        # MS001: Missing downgrade
        if "MS001" in rules and not result.has_downgrade:
            issues.append(LintIssue(
                file_path=result.file_path,
                severity=rules["MS001"].severity,
                rule_id="MS001",
                message="Migration has no downgrade implementation",
            ))

        # MS002: Destructive operations
        if "MS002" in rules and result.has_destructive_ops:
            for op in result.destructive_ops:
                issues.append(LintIssue(
                    file_path=result.file_path,
                    severity=rules["MS002"].severity,
                    rule_id="MS002",
                    message=f"Destructive operation: {op}",
                ))

        # MS003: Data migration in schema change
        if "MS003" in rules and result.has_data_migration:
            for op in result.data_migration_ops:
                issues.append(LintIssue(
                    file_path=result.file_path,
                    severity=rules["MS003"].severity,
                    rule_id="MS003",
                    message=f"Data migration operation: {op}",
                ))

        # MS004: Missing indexes
        if "MS004" in rules and result.missing_indexes:
            for col in result.missing_indexes:
                issues.append(LintIssue(
                    file_path=result.file_path,
                    severity=rules["MS004"].severity,
                    rule_id="MS004",
                    message=f"FK column '{col}' lacks an index",
                ))

        # MS005: Empty migration
        if "MS005" in rules and result.is_empty_upgrade:
            issues.append(LintIssue(
                file_path=result.file_path,
                severity=rules["MS005"].severity,
                rule_id="MS005",
                message="Migration has empty upgrade function",
            ))

        # MS006: No revision
        if "MS006" in rules and result.revision is None:
            issues.append(LintIssue(
                file_path=result.file_path,
                severity=rules["MS006"].severity,
                rule_id="MS006",
                message="Migration lacks revision identifier",
            ))

        # Append any validation errors
        for err in result.errors:
            issues.append(LintIssue(
                file_path=result.file_path,
                severity=Severity.ERROR,
                rule_id="VALIDATION",
                message=err,
            ))

        return issues
