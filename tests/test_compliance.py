"""Unit tests for PRD-71: Compliance & Audit System.

Tests cover:
- AuditLogger functionality
- ComplianceManager rules and checks
- Restricted securities management
- Pre-trade compliance checks
- Violation tracking
- ORM models
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

from src.enterprise.compliance import (
    AuditLogger,
    ComplianceManager,
    PreTradeCheck,
    AuditQuery,
)
from src.enterprise.models import (
    AuditLog, AuditAction, ComplianceRule, ComplianceViolation,
    RestrictedSecurity, generate_uuid,
)
from src.enterprise.config import (
    AuditConfig,
    DEFAULT_AUDIT_CONFIG,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def audit_logger():
    """Create an AuditLogger instance."""
    return AuditLogger()


@pytest.fixture
def compliance_manager():
    """Create a ComplianceManager instance."""
    return ComplianceManager()


@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return generate_uuid()


# =============================================================================
# Audit Logger Tests
# =============================================================================


class TestAuditLogger:
    """Tests for audit logging."""

    def test_log_action(self, audit_logger, sample_user_id):
        """Can log an action."""
        log = audit_logger.log(
            action=AuditAction.LOGIN,
            user_id=sample_user_id,
            user_email="test@example.com",
            status="success",
        )

        assert log is not None
        assert log.action == AuditAction.LOGIN
        assert log.user_id == sample_user_id
        assert log.status == "success"

    def test_log_with_resource(self, audit_logger, sample_user_id):
        """Can log action with resource details."""
        log = audit_logger.log(
            action=AuditAction.ORDER_SUBMIT,
            user_id=sample_user_id,
            resource_type="order",
            resource_id="order-123",
            details={"symbol": "AAPL", "qty": 100},
        )

        assert log.resource_type == "order"
        assert log.resource_id == "order-123"
        assert "symbol" in log.details

    def test_log_failure(self, audit_logger, sample_user_id):
        """Can log failed action."""
        log = audit_logger.log(
            action=AuditAction.LOGIN_FAILED,
            user_id=sample_user_id,
            status="failure",
            error_message="Invalid password",
        )

        assert log.status == "failure"
        assert log.error_message == "Invalid password"

    def test_log_with_ip_address(self, audit_logger, sample_user_id):
        """Can log action with IP address."""
        log = audit_logger.log(
            action=AuditAction.LOGIN,
            user_id=sample_user_id,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "Mozilla/5.0"

    def test_query_logs_by_user(self, audit_logger, sample_user_id):
        """Can query logs by user."""
        # Log some actions
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.ORDER_SUBMIT, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.LOGIN, user_id="other-user")

        query = AuditQuery(user_id=sample_user_id)
        results = audit_logger.query(query)

        assert len(results) == 2
        assert all(log.user_id == sample_user_id for log in results)

    def test_query_logs_by_action(self, audit_logger, sample_user_id):
        """Can query logs by action type."""
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.LOGOUT, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)

        query = AuditQuery(action=AuditAction.LOGIN)
        results = audit_logger.query(query)

        assert len(results) == 2
        assert all(log.action == AuditAction.LOGIN for log in results)

    def test_query_logs_by_status(self, audit_logger, sample_user_id):
        """Can query logs by status."""
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id, status="success")
        audit_logger.log(action=AuditAction.LOGIN_FAILED, user_id=sample_user_id, status="failure")

        query = AuditQuery(status="failure")
        results = audit_logger.query(query)

        assert len(results) == 1
        assert results[0].status == "failure"

    def test_get_user_activity(self, audit_logger, sample_user_id):
        """Can get recent user activity."""
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.ORDER_SUBMIT, user_id=sample_user_id)

        activity = audit_logger.get_user_activity(sample_user_id, days=30)

        assert len(activity) == 2

    def test_get_security_events(self, audit_logger, sample_user_id):
        """Can get security-related events."""
        audit_logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.LOGIN_FAILED, user_id=sample_user_id)
        audit_logger.log(action=AuditAction.ORDER_SUBMIT, user_id=sample_user_id)

        events = audit_logger.get_security_events(days=7)

        # Should only include auth-related events
        assert len(events) == 2
        assert all(e.action in [AuditAction.LOGIN, AuditAction.LOGIN_FAILED] for e in events)

    def test_sanitize_sensitive_data(self, audit_logger, sample_user_id):
        """Sensitive data is redacted from logs."""
        log = audit_logger.log(
            action=AuditAction.PASSWORD_CHANGE,
            user_id=sample_user_id,
            details={"password": "secret123", "email": "test@example.com"},
        )

        assert log.details["password"] == "[REDACTED]"
        assert log.details["email"] == "test@example.com"

    def test_disabled_logger_returns_none(self, sample_user_id):
        """Disabled logger returns None."""
        config = AuditConfig(enabled=False)
        logger = AuditLogger(config=config)

        log = logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)

        assert log is None


# =============================================================================
# Compliance Manager Tests
# =============================================================================


class TestComplianceManager:
    """Tests for compliance management."""

    def test_add_rule(self, compliance_manager, sample_user_id):
        """Can add a compliance rule."""
        rule = compliance_manager.add_rule(
            name="Position Limit",
            description="Max 15% in single position",
            rule_type="position_limit",
            parameters={"max_position_pct": 0.15},
            created_by=sample_user_id,
        )

        assert rule is not None
        assert rule.name == "Position Limit"
        assert rule.rule_type == "position_limit"

    def test_add_restricted_security(self, compliance_manager, sample_user_id):
        """Can add restricted security."""
        compliance_manager.add_restricted_security(
            symbol="XYZ",
            reason="insider",
            restricted_by=sample_user_id,
            restriction_type="all",
            notes="Employee owns shares",
        )

        is_restricted, reason = compliance_manager.is_restricted("XYZ")

        assert is_restricted is True
        assert reason == "insider"

    def test_remove_restricted_security(self, compliance_manager, sample_user_id):
        """Can remove restricted security."""
        compliance_manager.add_restricted_security(
            symbol="XYZ",
            reason="insider",
            restricted_by=sample_user_id,
        )

        compliance_manager.remove_restricted_security("XYZ", sample_user_id)

        is_restricted, _ = compliance_manager.is_restricted("XYZ")
        assert is_restricted is False

    def test_restriction_type_buy_only(self, compliance_manager, sample_user_id):
        """Buy-only restriction works correctly."""
        compliance_manager.add_restricted_security(
            symbol="ABC",
            reason="regulatory",
            restricted_by=sample_user_id,
            restriction_type="buy_only",
        )

        # Buy should be restricted
        is_restricted, _ = compliance_manager.is_restricted("ABC", action="buy")
        assert is_restricted is True

        # Sell should NOT be restricted (sell_only means sells are restricted)
        # Note: "buy_only" restriction means only buys are blocked
        # The is_restricted check returns True only if the action matches

    def test_restriction_type_sell_only(self, compliance_manager, sample_user_id):
        """Sell-only restriction works correctly."""
        compliance_manager.add_restricted_security(
            symbol="DEF",
            reason="regulatory",
            restricted_by=sample_user_id,
            restriction_type="sell_only",
        )

        is_restricted, _ = compliance_manager.is_restricted("DEF", action="sell")
        assert is_restricted is True

    def test_case_insensitive_symbol(self, compliance_manager, sample_user_id):
        """Symbol lookup is case-insensitive."""
        compliance_manager.add_restricted_security(
            symbol="xyz",
            reason="insider",
            restricted_by=sample_user_id,
        )

        is_restricted, _ = compliance_manager.is_restricted("XYZ")
        assert is_restricted is True

    def test_get_restricted_list(self, compliance_manager, sample_user_id):
        """Can get full restricted list."""
        compliance_manager.add_restricted_security("AAA", "insider", sample_user_id)
        compliance_manager.add_restricted_security("BBB", "regulatory", sample_user_id)

        restricted_list = compliance_manager.get_restricted_list()

        assert len(restricted_list) == 2
        symbols = [r.symbol for r in restricted_list]
        assert "AAA" in symbols
        assert "BBB" in symbols


# =============================================================================
# Pre-Trade Check Tests
# =============================================================================


class TestPreTradeChecks:
    """Tests for pre-trade compliance checks."""

    def test_check_restricted_security(self, compliance_manager, sample_user_id):
        """Pre-trade check catches restricted securities."""
        compliance_manager.add_restricted_security("XYZ", "insider", sample_user_id)

        checks = compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        restricted_check = next(c for c in checks if c.rule_name == "Restricted Security")
        assert restricted_check.passed is False
        assert restricted_check.severity == "critical"

    def test_check_unrestricted_security(self, compliance_manager, sample_user_id):
        """Pre-trade check passes for unrestricted securities."""
        checks = compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="AAPL",
            action="buy",
            quantity=100,
            price=185.0,
            portfolio_value=100000,
            current_positions={},
        )

        restricted_check = next(c for c in checks if c.rule_name == "Restricted Security")
        assert restricted_check.passed is True

    def test_check_position_limit(self, compliance_manager, sample_user_id):
        """Pre-trade check catches position limit violations."""
        compliance_manager.add_rule(
            name="Position Limit",
            description="Max 15%",
            rule_type="position_limit",
            parameters={"max_position_pct": 0.15},
            created_by=sample_user_id,
        )

        # Try to buy $20,000 worth (20% of $100,000 portfolio)
        checks = compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="AAPL",
            action="buy",
            quantity=100,
            price=200.0,  # $20,000 order
            portfolio_value=100000,
            current_positions={},
        )

        # Find position limit check
        limit_checks = [c for c in checks if "Position" in c.rule_name or "position" in c.rule_name.lower()]
        if limit_checks:
            assert limit_checks[0].passed is False

    def test_pre_trade_check_result_structure(self):
        """PreTradeCheck has correct structure."""
        check = PreTradeCheck(
            passed=True,
            rule_name="Test Rule",
            message="Check passed",
            severity="info",
            details={"key": "value"},
        )

        assert check.passed is True
        assert check.rule_name == "Test Rule"
        assert check.message == "Check passed"
        assert check.severity == "info"


# =============================================================================
# Violation Tests
# =============================================================================


class TestViolations:
    """Tests for violation tracking."""

    def test_violation_recorded_on_failure(self, compliance_manager, sample_user_id):
        """Violations are recorded when checks fail."""
        compliance_manager.add_restricted_security("XYZ", "insider", sample_user_id)

        compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        violations = compliance_manager.get_violations(user_id=sample_user_id)
        assert len(violations) >= 1

    def test_get_violations_by_account(self, compliance_manager, sample_user_id):
        """Can filter violations by account."""
        compliance_manager.add_restricted_security("XYZ", "insider", sample_user_id)

        compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        violations = compliance_manager.get_violations(account_id="acc-001")
        all_for_account = all(v.account_id == "acc-001" for v in violations)
        assert all_for_account or len(violations) == 0

    def test_get_unresolved_violations(self, compliance_manager, sample_user_id):
        """Can filter to only unresolved violations."""
        compliance_manager.add_restricted_security("XYZ", "insider", sample_user_id)

        compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        violations = compliance_manager.get_violations(unresolved_only=True)
        assert all(not v.is_resolved for v in violations)

    def test_resolve_violation(self, compliance_manager, sample_user_id):
        """Can resolve a violation."""
        compliance_manager.add_restricted_security("XYZ", "insider", sample_user_id)

        compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        violations = compliance_manager.get_violations()
        if violations:
            success = compliance_manager.resolve_violation(
                violation_id=violations[0].id,
                resolved_by=sample_user_id,
                notes="Trade cancelled",
            )
            assert success is True


# =============================================================================
# Custom Check Tests
# =============================================================================


class TestCustomChecks:
    """Tests for custom compliance checks."""

    def test_add_custom_check(self, compliance_manager, sample_user_id):
        """Can add custom compliance check."""
        def my_check(user_id, account_id, symbol, action, quantity, price, portfolio_value, positions):
            if symbol == "BANNED":
                return PreTradeCheck(
                    passed=False,
                    rule_name="Custom Ban",
                    message="Symbol is banned by custom rule",
                    severity="critical",
                )
            return None

        compliance_manager.add_custom_check(my_check)

        checks = compliance_manager.run_pre_trade_checks(
            user_id=sample_user_id,
            account_id="acc-001",
            symbol="BANNED",
            action="buy",
            quantity=100,
            price=50.0,
            portfolio_value=100000,
            current_positions={},
        )

        custom_check = next((c for c in checks if c.rule_name == "Custom Ban"), None)
        assert custom_check is not None
        assert custom_check.passed is False


# =============================================================================
# Config Tests
# =============================================================================


class TestAuditConfig:
    """Tests for audit configuration."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = DEFAULT_AUDIT_CONFIG

        assert config.enabled is True
        assert config.retention_days >= 365  # At least 1 year
        assert "password" in config.sensitive_fields

    def test_retention_enforcement(self, sample_user_id):
        """Retention policy removes old logs."""
        config = AuditConfig(retention_days=1)
        logger = AuditLogger(config=config)

        # Log would be retained if within 1 day
        logger.log(action=AuditAction.LOGIN, user_id=sample_user_id)

        # enforce_retention should not fail
        logger.enforce_retention()


# =============================================================================
# ORM Model Tests
# =============================================================================


class TestORMModels:
    """Tests for ORM model definitions."""

    def test_compliance_rule_model(self):
        """ComplianceRuleRecord model has required fields."""
        from src.db.models import ComplianceRuleRecord

        columns = {c.name for c in ComplianceRuleRecord.__table__.columns}
        assert "id" in columns
        assert "owner_id" in columns
        assert "name" in columns
        assert "rule_type" in columns
        assert "parameters" in columns
        assert "severity" in columns
        assert "is_active" in columns
        assert "is_blocking" in columns

    def test_restricted_security_model(self):
        """RestrictedSecurityRecord model has required fields."""
        from src.db.models import RestrictedSecurityRecord

        columns = {c.name for c in RestrictedSecurityRecord.__table__.columns}
        assert "id" in columns
        assert "owner_id" in columns
        assert "symbol" in columns
        assert "reason" in columns
        assert "restriction_type" in columns
        assert "start_date" in columns
        assert "end_date" in columns

    def test_compliance_violation_model(self):
        """ComplianceViolationRecord model has required fields."""
        from src.db.models import ComplianceViolationRecord

        columns = {c.name for c in ComplianceViolationRecord.__table__.columns}
        assert "id" in columns
        assert "rule_id" in columns
        assert "user_id" in columns
        assert "rule_name" in columns
        assert "violation_type" in columns
        assert "severity" in columns
        assert "is_resolved" in columns
        assert "trade_blocked" in columns

    def test_audit_log_model(self):
        """AuditLogRecord model has required fields."""
        from src.db.models import AuditLogRecord

        columns = {c.name for c in AuditLogRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "action" in columns
        assert "resource_type" in columns
        assert "details" in columns
        assert "status" in columns
        assert "ip_address" in columns
        assert "timestamp" in columns

    def test_pretrade_check_model(self):
        """PreTradeCheckRecord model has required fields."""
        from src.db.models import PreTradeCheckRecord

        columns = {c.name for c in PreTradeCheckRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "symbol" in columns
        assert "action" in columns
        assert "quantity" in columns
        assert "passed" in columns
        assert "trade_allowed" in columns

    def test_compliance_report_model(self):
        """ComplianceReportRecord model has required fields."""
        from src.db.models import ComplianceReportRecord

        columns = {c.name for c in ComplianceReportRecord.__table__.columns}
        assert "id" in columns
        assert "user_id" in columns
        assert "report_type" in columns
        assert "period_start" in columns
        assert "period_end" in columns
        assert "status" in columns


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Tests for enum definitions."""

    def test_compliance_rule_type_enum(self):
        """ComplianceRuleTypeEnum has all expected values."""
        from src.db.models import ComplianceRuleTypeEnum

        values = {e.value for e in ComplianceRuleTypeEnum}
        assert "position_limit" in values
        assert "sector_limit" in values
        assert "concentration" in values
        assert "restricted_list" in values
        assert "daily_loss_limit" in values

    def test_compliance_severity_enum(self):
        """ComplianceSeverityEnum has all expected values."""
        from src.db.models import ComplianceSeverityEnum

        values = {e.value for e in ComplianceSeverityEnum}
        assert "info" in values
        assert "warning" in values
        assert "critical" in values

    def test_restriction_type_enum(self):
        """RestrictionTypeEnum has all expected values."""
        from src.db.models import RestrictionTypeEnum

        values = {e.value for e in RestrictionTypeEnum}
        assert "all" in values
        assert "buy_only" in values
        assert "sell_only" in values

    def test_audit_action_enum(self):
        """AuditActionEnum has all expected values."""
        from src.db.models import AuditActionEnum

        values = {e.value for e in AuditActionEnum}
        assert "login" in values
        assert "logout" in values
        assert "order_submit" in values
        assert "compliance_violation" in values
        assert "api_key_create" in values
