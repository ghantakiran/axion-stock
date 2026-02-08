"""Tests for PRD-110: Migration Safety & Reversibility."""

import json
import os
import tempfile

import pytest

from src.migration_safety.config import (
    DEFAULT_RULES,
    MigrationDirection,
    MigrationSafetyConfig,
    MigrationStatus,
    RuleCategory,
    RuleConfig,
    Severity,
)
from src.migration_safety.validator import MigrationValidator, ValidationResult
from src.migration_safety.checks import (
    CheckResult,
    MigrationCheckReport,
    PostMigrationCheck,
    PreMigrationCheck,
)
from src.migration_safety.linter import LintIssue, LintReport, MigrationLinter
from src.migration_safety.reporter import ValidationReporter


def _write_temp_migration(content: str) -> str:
    """Write migration content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


GOOD_MIGRATION = '''
"""Test migration."""
revision = "001"
down_revision = "000"

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("users")
'''

NO_DOWNGRADE_MIGRATION = '''
"""Missing downgrade."""
revision = "002"
down_revision = "001"

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
    )

def downgrade() -> None:
    pass
'''

DESTRUCTIVE_MIGRATION = '''
"""Destructive migration."""
revision = "003"
down_revision = "002"

from alembic import op

def upgrade() -> None:
    op.drop_table("old_table")
    op.drop_column("users", "legacy_field")

def downgrade() -> None:
    pass
'''

EMPTY_MIGRATION = '''
"""Empty migration."""
revision = "004"
down_revision = "003"

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
'''

NO_REVISION_MIGRATION = '''
"""No revision."""

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table("test", sa.Column("id", sa.Integer, primary_key=True))

def downgrade() -> None:
    op.drop_table("test")
'''

FK_MISSING_INDEX_MIGRATION = '''
"""FK without index."""
revision = "005"
down_revision = "004"

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("product_id", sa.Integer, nullable=False),
    )

def downgrade() -> None:
    op.drop_table("orders")
'''


class TestMigrationSafetyConfig:
    """Tests for migration safety configuration."""

    def test_default_config(self):
        config = MigrationSafetyConfig()
        assert config.require_downgrade is True
        assert len(config.rules) == len(DEFAULT_RULES)

    def test_severity_enum(self):
        assert Severity.INFO.value == "info"
        assert Severity.CRITICAL.value == "critical"

    def test_rule_category_enum(self):
        assert RuleCategory.SAFETY.value == "safety"
        assert RuleCategory.REVERSIBILITY.value == "reversibility"

    def test_migration_direction_enum(self):
        assert MigrationDirection.UPGRADE.value == "upgrade"
        assert MigrationDirection.DOWNGRADE.value == "downgrade"

    def test_migration_status_enum(self):
        assert MigrationStatus.SUCCESS.value == "success"
        assert MigrationStatus.FAILED.value == "failed"

    def test_default_rules(self):
        assert "MS001" in DEFAULT_RULES
        assert "MS002" in DEFAULT_RULES

    def test_get_rule(self):
        config = MigrationSafetyConfig()
        rule = config.get_rule("MS001")
        assert rule is not None
        assert rule.name == "missing_downgrade"

    def test_enable_disable_rule(self):
        config = MigrationSafetyConfig()
        config.disable_rule("MS001")
        assert not config.rules["MS001"].enabled
        config.enable_rule("MS001")
        assert config.rules["MS001"].enabled

    def test_get_enabled_rules(self):
        config = MigrationSafetyConfig()
        config.disable_rule("MS001")
        enabled = config.get_enabled_rules()
        assert "MS001" not in enabled

    def test_add_custom_rule(self):
        config = MigrationSafetyConfig()
        rule = RuleConfig(rule_id="CUSTOM001", name="custom", description="Custom rule")
        config.add_rule(rule)
        assert "CUSTOM001" in config.rules

    def test_get_rules_by_severity(self):
        config = MigrationSafetyConfig()
        critical = config.get_rules_by_severity(Severity.CRITICAL)
        assert len(critical) >= 1

    def test_get_rules_by_category(self):
        config = MigrationSafetyConfig()
        safety = config.get_rules_by_category(RuleCategory.SAFETY)
        assert len(safety) >= 1


class TestMigrationValidator:
    """Tests for AST-based migration validator."""

    def test_validate_good_migration(self):
        path = _write_temp_migration(GOOD_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.has_upgrade is True
            assert result.has_downgrade is True
            assert result.revision == "001"
            assert result.is_safe is True
        finally:
            os.unlink(path)

    def test_validate_no_downgrade(self):
        path = _write_temp_migration(NO_DOWNGRADE_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.has_downgrade is False
            assert result.is_safe is False
        finally:
            os.unlink(path)

    def test_validate_destructive(self):
        path = _write_temp_migration(DESTRUCTIVE_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.has_destructive_ops is True
            assert len(result.destructive_ops) >= 1
            assert result.is_safe is False
        finally:
            os.unlink(path)

    def test_validate_empty_migration(self):
        path = _write_temp_migration(EMPTY_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.is_empty_upgrade is True
        finally:
            os.unlink(path)

    def test_validate_missing_file(self):
        validator = MigrationValidator()
        result = validator.validate_file("/nonexistent/file.py")
        assert len(result.errors) > 0

    def test_safety_score_good(self):
        path = _write_temp_migration(GOOD_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.safety_score >= 0.8
        finally:
            os.unlink(path)

    def test_safety_score_bad(self):
        path = _write_temp_migration(DESTRUCTIVE_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.safety_score < 0.5
        finally:
            os.unlink(path)

    def test_validate_directory(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path1 = os.path.join(tmpdir, "001_first.py")
            path2 = os.path.join(tmpdir, "002_second.py")
            with open(path1, "w") as f:
                f.write(GOOD_MIGRATION)
            with open(path2, "w") as f:
                f.write(NO_DOWNGRADE_MIGRATION)
            validator = MigrationValidator()
            results = validator.validate_directory(tmpdir)
            assert len(results) == 2
        finally:
            for f in os.listdir(tmpdir):
                os.unlink(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)

    def test_get_summary(self):
        path = _write_temp_migration(GOOD_MIGRATION)
        try:
            validator = MigrationValidator()
            validator.validate_file(path)
            summary = validator.get_summary()
            assert summary["total_migrations"] == 1
            assert "average_safety_score" in summary
        finally:
            os.unlink(path)

    def test_get_unsafe_migrations(self):
        path = _write_temp_migration(NO_DOWNGRADE_MIGRATION)
        try:
            validator = MigrationValidator()
            validator.validate_file(path)
            unsafe = validator.get_unsafe_migrations()
            assert len(unsafe) == 1
        finally:
            os.unlink(path)

    def test_fk_missing_index(self):
        path = _write_temp_migration(FK_MISSING_INDEX_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert len(result.missing_indexes) >= 1
        finally:
            os.unlink(path)

    def test_no_revision_detected(self):
        path = _write_temp_migration(NO_REVISION_MIGRATION)
        try:
            validator = MigrationValidator()
            result = validator.validate_file(path)
            assert result.revision is None
        finally:
            os.unlink(path)


class TestPreMigrationChecks:
    """Tests for pre-migration checks."""

    def test_run_all_checks(self):
        checker = PreMigrationCheck()
        report = checker.run_all_checks("101")
        assert report.all_passed
        assert report.status == MigrationStatus.SUCCESS

    def test_check_db_connectivity_valid(self):
        checker = PreMigrationCheck()
        result = checker.check_db_connectivity("postgresql://localhost/test")
        assert result.passed

    def test_check_db_connectivity_invalid(self):
        checker = PreMigrationCheck()
        result = checker.check_db_connectivity("invalid://bad")
        assert not result.passed

    def test_check_db_connectivity_none(self):
        checker = PreMigrationCheck()
        result = checker.check_db_connectivity(None)
        assert result.passed

    def test_check_migration_file_exists(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            checker = PreMigrationCheck()
            result = checker.check_migration_file_exists(path)
            assert result.passed
        finally:
            os.unlink(path)

    def test_check_migration_file_missing(self):
        checker = PreMigrationCheck()
        result = checker.check_migration_file_exists("/nonexistent/file.py")
        assert not result.passed

    def test_check_history(self):
        checker = PreMigrationCheck()
        checker.run_all_checks("101")
        checker.run_all_checks("102")
        history = checker.get_history()
        assert len(history) == 2

    def test_check_report_properties(self):
        report = MigrationCheckReport(revision="101", direction=MigrationDirection.UPGRADE)
        assert report.check_count == 0
        assert report.pass_count == 0
        assert report.fail_count == 0
        assert report.all_passed


class TestPostMigrationChecks:
    """Tests for post-migration checks."""

    def test_run_all_checks(self):
        checker = PostMigrationCheck()
        report = checker.run_all_checks("101", applied_revision="101")
        assert report.all_passed

    def test_revision_mismatch(self):
        checker = PostMigrationCheck()
        result = checker.check_revision_applied("101", actual_revision="100")
        assert not result.passed

    def test_revision_match(self):
        checker = PostMigrationCheck()
        result = checker.check_revision_applied("101", actual_revision="101")
        assert result.passed

    def test_expected_tables_missing(self):
        checker = PostMigrationCheck()
        result = checker.check_expected_tables(
            expected_tables=["users", "orders"],
            existing_tables=["users"],
        )
        assert not result.passed

    def test_expected_columns_missing(self):
        checker = PostMigrationCheck()
        result = checker.check_expected_columns(
            expected_columns={"users": ["id", "name", "email"]},
            actual_columns={"users": ["id", "name"]},
        )
        assert not result.passed


class TestMigrationLinter:
    """Tests for migration linter."""

    def test_lint_good_file(self):
        path = _write_temp_migration(GOOD_MIGRATION)
        try:
            linter = MigrationLinter()
            issues = linter.lint_file(path)
            # Good migration: might have warnings but no errors for MS001/MS002
            error_issues = [i for i in issues if i.severity in (Severity.ERROR, Severity.CRITICAL)]
            assert len(error_issues) == 0
        finally:
            os.unlink(path)

    def test_lint_no_downgrade(self):
        path = _write_temp_migration(NO_DOWNGRADE_MIGRATION)
        try:
            linter = MigrationLinter()
            issues = linter.lint_file(path)
            ms001 = [i for i in issues if i.rule_id == "MS001"]
            assert len(ms001) == 1
        finally:
            os.unlink(path)

    def test_lint_destructive(self):
        path = _write_temp_migration(DESTRUCTIVE_MIGRATION)
        try:
            linter = MigrationLinter()
            issues = linter.lint_file(path)
            ms002 = [i for i in issues if i.rule_id == "MS002"]
            assert len(ms002) >= 1
        finally:
            os.unlink(path)

    def test_lint_directory(self):
        tmpdir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpdir, "001_good.py"), "w") as f:
                f.write(GOOD_MIGRATION)
            with open(os.path.join(tmpdir, "002_bad.py"), "w") as f:
                f.write(NO_DOWNGRADE_MIGRATION)
            linter = MigrationLinter()
            report = linter.lint_directory(tmpdir)
            assert report.files_checked == 2
            assert report.total_issues > 0
        finally:
            for f in os.listdir(tmpdir):
                os.unlink(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)

    def test_lint_report_summary(self):
        report = LintReport(files_checked=5, files_with_issues=2)
        s = report.summary()
        assert s["files_checked"] == 5

    def test_lint_issue_str(self):
        issue = LintIssue(
            file_path="test.py",
            severity=Severity.ERROR,
            rule_id="MS001",
            message="No downgrade",
        )
        s = str(issue)
        assert "ERROR" in s
        assert "MS001" in s

    def test_lint_disabled_rule(self):
        config = MigrationSafetyConfig()
        config.disable_rule("MS001")
        path = _write_temp_migration(NO_DOWNGRADE_MIGRATION)
        try:
            linter = MigrationLinter(config)
            issues = linter.lint_file(path)
            ms001 = [i for i in issues if i.rule_id == "MS001"]
            assert len(ms001) == 0
        finally:
            os.unlink(path)


class TestValidationReporter:
    """Tests for validation report generation."""

    def _get_results(self):
        validator = MigrationValidator()
        path1 = _write_temp_migration(GOOD_MIGRATION)
        path2 = _write_temp_migration(NO_DOWNGRADE_MIGRATION)
        try:
            validator.validate_file(path1)
            validator.validate_file(path2)
            return validator.get_results(), [path1, path2]
        except Exception:
            os.unlink(path1)
            os.unlink(path2)
            raise

    def test_text_report(self):
        results, paths = self._get_results()
        try:
            reporter = ValidationReporter()
            text = reporter.generate_text_report(results)
            assert "Migration Safety Report" in text
            assert "Total Migrations: 2" in text
        finally:
            for p in paths:
                os.unlink(p)

    def test_json_report(self):
        results, paths = self._get_results()
        try:
            reporter = ValidationReporter()
            json_str = reporter.generate_json_report(results)
            parsed = json.loads(json_str)
            assert parsed["summary"]["total_migrations"] == 2
        finally:
            for p in paths:
                os.unlink(p)

    def test_json_report_with_lint(self):
        results, paths = self._get_results()
        try:
            lint_report = LintReport(
                files_checked=2,
                files_with_issues=1,
                issues=[
                    LintIssue(file_path="test.py", severity=Severity.ERROR, rule_id="MS001", message="test"),
                ],
            )
            reporter = ValidationReporter()
            json_str = reporter.generate_json_report(results, lint_report)
            parsed = json.loads(json_str)
            assert "lint" in parsed
            assert parsed["lint"]["total_issues"] == 1
        finally:
            for p in paths:
                os.unlink(p)
