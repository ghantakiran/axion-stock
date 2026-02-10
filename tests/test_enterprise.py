"""Tests for Enterprise & Multi-Account Platform.

Comprehensive test suite covering:
- Authentication and authorization
- Multi-account management
- Team workspaces
- Reporting
- Compliance and audit logging
"""

import pytest
from datetime import datetime, date, timedelta

from src.enterprise.config import (
    UserRole, SubscriptionTier, AccountType, TaxStatus, BrokerType,
    ROLE_PERMISSIONS, SUBSCRIPTION_LIMITS, AuthConfig,
)
from src.enterprise.models import User, Account, Workspace, AuditAction
from src.enterprise.auth import (
    PasswordHasher, TokenManager, TOTPManager, AuthService,
)
from src.enterprise.accounts import AccountManager, AccountSummary
from src.enterprise.workspaces import WorkspaceManager, WorkspaceRole
from src.enterprise.reporting import ReportGenerator, ReportData, PerformanceMetrics
from src.enterprise.compliance import AuditLogger, AuditQuery, ComplianceManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def auth_service():
    """Create an AuthService instance."""
    return AuthService()


@pytest.fixture
def account_manager():
    """Create an AccountManager instance."""
    return AccountManager()


@pytest.fixture
def workspace_manager():
    """Create a WorkspaceManager instance."""
    return WorkspaceManager()


@pytest.fixture
def report_generator():
    """Create a ReportGenerator instance."""
    return ReportGenerator()


@pytest.fixture
def audit_logger():
    """Create an AuditLogger instance."""
    return AuditLogger()


@pytest.fixture
def compliance_manager():
    """Create a ComplianceManager instance."""
    return ComplianceManager()


@pytest.fixture
def sample_user(auth_service):
    """Create a sample user."""
    user, error = auth_service.register(
        email="test@example.com",
        password="SecurePass123",
        name="Test User",
    )
    return user


@pytest.fixture
def enterprise_user(auth_service):
    """Create an enterprise-tier user."""
    user, error = auth_service.register(
        email="enterprise@example.com",
        password="SecurePass123",
        name="Enterprise User",
    )
    user.subscription = SubscriptionTier.ENTERPRISE
    return user


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test configuration and role permissions."""

    def test_role_permissions(self):
        """Test role permissions are defined correctly."""
        assert "view_portfolios" in ROLE_PERMISSIONS[UserRole.VIEWER]
        assert "execute_trades" in ROLE_PERMISSIONS[UserRole.TRADER]
        assert "create_strategies" in ROLE_PERMISSIONS[UserRole.MANAGER]
        assert "manage_users" in ROLE_PERMISSIONS[UserRole.ADMIN]

    def test_subscription_limits(self):
        """Test subscription limits are defined correctly."""
        free = SUBSCRIPTION_LIMITS[SubscriptionTier.FREE]
        pro = SUBSCRIPTION_LIMITS[SubscriptionTier.PRO]
        enterprise = SUBSCRIPTION_LIMITS[SubscriptionTier.ENTERPRISE]

        assert free["max_accounts"] == 1
        assert pro["max_accounts"] == 3
        assert enterprise["max_accounts"] == 999

        assert free["live_trading"] is False
        assert pro["live_trading"] is True

        assert enterprise["team_workspace"] is True
        assert free["team_workspace"] is False


# =============================================================================
# Authentication Tests
# =============================================================================


class TestPasswordHasher:
    """Test password hashing."""

    def test_hash_password(self):
        """Test password hashing creates unique hash."""
        hasher = PasswordHasher()
        hash1 = hasher.hash("password123")
        hash2 = hasher.hash("password123")

        # Hashes should be different due to salt
        assert hash1 != hash2
        assert "$" in hash1  # Contains separator

    def test_verify_password_correct(self):
        """Test correct password verification."""
        hasher = PasswordHasher()
        password = "SecurePass123!"
        hash_str = hasher.hash(password)

        assert hasher.verify(password, hash_str) is True

    def test_verify_password_incorrect(self):
        """Test incorrect password verification."""
        hasher = PasswordHasher()
        hash_str = hasher.hash("password123")

        assert hasher.verify("wrongpassword", hash_str) is False


class TestEnterpriseTokenManager:
    """Test JWT token management."""

    def test_create_access_token(self):
        """Test access token creation."""
        manager = TokenManager()
        token = manager.create_access_token("user123", UserRole.TRADER)

        assert token is not None
        assert "." in token  # Has payload and signature

    def test_decode_valid_token(self):
        """Test decoding valid token."""
        manager = TokenManager()
        token = manager.create_access_token("user123", UserRole.TRADER)

        payload = manager.decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["role"] == "trader"
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        manager = TokenManager()
        payload = manager.decode_token("invalid.token")

        assert payload is None

    def test_refresh_token(self):
        """Test refresh token creation and decoding."""
        manager = TokenManager()
        token = manager.create_refresh_token("user123")

        payload = manager.decode_token(token)

        assert payload is not None
        assert payload["type"] == "refresh"


class TestTOTPManager:
    """Test 2FA TOTP functionality."""

    def test_generate_secret(self):
        """Test TOTP secret generation."""
        manager = TOTPManager()
        secret = manager.generate_secret()

        assert secret is not None
        assert len(secret) == 32  # Base32 encoded 20 bytes

    def test_generate_code(self):
        """Test TOTP code generation."""
        manager = TOTPManager()
        secret = manager.generate_secret()
        code = manager.generate_code(secret)

        assert code is not None
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_code(self):
        """Test TOTP code verification."""
        manager = TOTPManager()
        secret = manager.generate_secret()
        code = manager.generate_code(secret)

        assert manager.verify_code(secret, code) is True
        assert manager.verify_code(secret, "000000") is False


class TestAuthService:
    """Test authentication service."""

    def test_register_user(self, auth_service):
        """Test user registration."""
        user, error = auth_service.register(
            email="newuser@example.com",
            password="SecurePass123",
            name="New User",
        )

        assert user is not None
        assert error is None
        assert user.email == "newuser@example.com"
        assert user.name == "New User"
        assert user.role == UserRole.TRADER

    def test_register_duplicate_email(self, auth_service, sample_user):
        """Test registration with duplicate email fails."""
        user, error = auth_service.register(
            email="test@example.com",
            password="AnotherPass123",
            name="Another User",
        )

        assert user is None
        assert "already registered" in error

    def test_register_weak_password(self, auth_service):
        """Test registration with weak password fails."""
        user, error = auth_service.register(
            email="weak@example.com",
            password="weak",
        )

        assert user is None
        assert "Password must be" in error

    def test_login_success(self, auth_service, sample_user):
        """Test successful login."""
        session, error = auth_service.login(
            email="test@example.com",
            password="SecurePass123",
        )

        assert session is not None
        assert error is None
        assert session.access_token is not None
        assert session.refresh_token is not None

    def test_login_wrong_password(self, auth_service, sample_user):
        """Test login with wrong password."""
        session, error = auth_service.login(
            email="test@example.com",
            password="WrongPassword",
        )

        assert session is None
        assert "Invalid credentials" in error

    def test_verify_token(self, auth_service, sample_user):
        """Test token verification."""
        session, _ = auth_service.login("test@example.com", "SecurePass123")
        user, error = auth_service.verify_token(session.access_token)

        assert user is not None
        assert user.email == sample_user.email

    def test_has_permission(self, auth_service, sample_user):
        """Test permission checking."""
        assert auth_service.has_permission(sample_user, "view_portfolios") is True
        assert auth_service.has_permission(sample_user, "execute_trades") is True
        assert auth_service.has_permission(sample_user, "manage_users") is False


# =============================================================================
# Account Management Tests
# =============================================================================


class TestAccountManager:
    """Test multi-account management."""

    def test_create_account(self, account_manager, sample_user):
        """Test account creation."""
        account, error = account_manager.create_account(
            user=sample_user,
            name="Personal Account",
            account_type=AccountType.PAPER,
            initial_value=100000,
        )

        assert account is not None
        assert error is None
        assert account.name == "Personal Account"
        assert account.total_value == 100000

    def test_account_limit_free_tier(self, account_manager, sample_user):
        """Test free tier account limit."""
        # Create first account (should succeed)
        account1, _ = account_manager.create_account(
            user=sample_user,
            name="First Account",
            account_type=AccountType.PAPER,
        )
        assert account1 is not None

        # Create second account (should fail - free tier limit)
        account2, error = account_manager.create_account(
            user=sample_user,
            name="Second Account",
            account_type=AccountType.PAPER,
        )

        assert account2 is None
        assert "limit reached" in error

    def test_create_multiple_accounts_enterprise(self, account_manager, enterprise_user):
        """Test enterprise can create multiple accounts."""
        for i in range(5):
            account, error = account_manager.create_account(
                user=enterprise_user,
                name=f"Account {i}",
                account_type=AccountType.INDIVIDUAL,
            )
            assert account is not None

        accounts = account_manager.get_user_accounts(enterprise_user.id)
        assert len(accounts) == 5

    def test_household_summary(self, account_manager, enterprise_user):
        """Test household summary aggregation."""
        # Create multiple accounts
        account_manager.create_account(
            user=enterprise_user,
            name="Taxable",
            account_type=AccountType.INDIVIDUAL,
            initial_value=100000,
            tax_status=TaxStatus.TAXABLE,
        )
        account_manager.create_account(
            user=enterprise_user,
            name="Roth IRA",
            account_type=AccountType.IRA_ROTH,
            initial_value=50000,
            tax_status=TaxStatus.TAX_FREE,
        )

        summary = account_manager.get_household_summary(enterprise_user.id)

        assert summary.total_value == 150000
        assert summary.taxable_value == 100000
        assert summary.tax_free_value == 50000


# =============================================================================
# Workspace Tests
# =============================================================================


class TestWorkspaceManager:
    """Test team workspace management."""

    def test_create_workspace_requires_enterprise(self, workspace_manager, sample_user):
        """Test workspace creation requires enterprise tier."""
        workspace, error = workspace_manager.create_workspace(
            owner=sample_user,
            name="My Team",
        )

        assert workspace is None
        assert "Upgrade to Enterprise" in error

    def test_create_workspace_enterprise(self, workspace_manager, enterprise_user):
        """Test enterprise can create workspace."""
        workspace, error = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Alpha Team",
            description="Our trading team",
        )

        assert workspace is not None
        assert workspace.name == "Alpha Team"
        assert workspace.owner_id == enterprise_user.id

    def test_invite_member(self, workspace_manager, enterprise_user, auth_service):
        """Test inviting members to workspace."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Team",
        )

        # Create another user
        new_user, _ = auth_service.register("member@example.com", "SecurePass123")

        member, error = workspace_manager.invite_member(
            workspace_id=workspace.id,
            inviter_id=enterprise_user.id,
            user_id=new_user.id,
            user_name=new_user.name,
        )

        assert member is not None
        assert member.role == WorkspaceRole.MEMBER

    def test_share_strategy(self, workspace_manager, enterprise_user):
        """Test sharing strategy in workspace."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Team",
        )

        strategy, error = workspace_manager.share_strategy(
            workspace_id=workspace.id,
            user_id=enterprise_user.id,
            user_name=enterprise_user.name,
            name="Momentum Strategy",
            description="12-month momentum factor",
            config={"lookback": 252},
            ytd_return=0.12,
            sharpe_ratio=1.5,
        )

        assert strategy is not None
        assert strategy.name == "Momentum Strategy"

    def test_leaderboard(self, workspace_manager, enterprise_user):
        """Test strategy leaderboard."""
        workspace, _ = workspace_manager.create_workspace(
            owner=enterprise_user,
            name="Test Team",
        )

        # Share multiple strategies
        for i, (ytd, sharpe) in enumerate([(0.10, 1.2), (0.15, 1.5), (0.08, 0.9)]):
            workspace_manager.share_strategy(
                workspace_id=workspace.id,
                user_id=enterprise_user.id,
                user_name=enterprise_user.name,
                name=f"Strategy {i}",
                description="",
                config={},
                ytd_return=ytd,
                sharpe_ratio=sharpe,
            )

        leaderboard = workspace_manager.get_leaderboard(workspace.id, "ytd_return")

        assert len(leaderboard) == 3
        assert leaderboard[0].ytd_return == 0.15  # Highest YTD first


# =============================================================================
# Reporting Tests
# =============================================================================


class TestReportGenerator:
    """Test professional report generation."""

    def test_generate_pdf_report(self, report_generator):
        """Test PDF report generation."""
        data = ReportData(
            report_title="Q4 2025 Performance Report",
            client_name="John Smith",
            account_name="Personal Taxable",
            period_start=date(2025, 10, 1),
            period_end=date(2025, 12, 31),
            metrics=PerformanceMetrics(
                period_return=0.042,
                benchmark_return=0.031,
                alpha=0.011,
                sharpe_ratio=1.67,
                max_drawdown=-0.038,
            ),
        )

        report = report_generator.generate_quarterly_report(data, "pdf")

        assert report is not None
        assert b"PERFORMANCE REPORT" in report
        assert b"John Smith" in report

    def test_generate_excel_report(self, report_generator):
        """Test Excel report generation."""
        data = ReportData(
            client_name="Jane Doe",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            metrics=PerformanceMetrics(period_return=0.12),
        )

        report = report_generator.generate_quarterly_report(data, "excel")

        assert report is not None
        assert b"Jane Doe" in report

    def test_generate_html_report(self, report_generator):
        """Test HTML report generation."""
        data = ReportData(
            report_title="Annual Report",
            client_name="Client",
            metrics=PerformanceMetrics(sharpe_ratio=1.5),
        )

        report = report_generator.generate_quarterly_report(data, "html")

        assert report is not None
        assert b"<html>" in report
        assert b"Annual Report" in report


# =============================================================================
# Compliance Tests
# =============================================================================


class TestAuditLogger:
    """Test audit logging."""

    def test_log_action(self, audit_logger):
        """Test logging an action."""
        log = audit_logger.log(
            action=AuditAction.LOGIN,
            user_id="user123",
            user_email="user@example.com",
            ip_address="192.168.1.1",
        )

        assert log is not None
        assert log.action == AuditAction.LOGIN
        assert log.user_id == "user123"

    def test_query_logs(self, audit_logger):
        """Test querying audit logs."""
        # Log multiple actions
        for action in [AuditAction.LOGIN, AuditAction.ORDER_SUBMIT, AuditAction.LOGIN]:
            audit_logger.log(
                action=action,
                user_id="user123",
            )

        # Query for login actions
        query = AuditQuery(action=AuditAction.LOGIN)
        results = audit_logger.query(query)

        assert len(results) == 2

    def test_sensitive_data_sanitization(self, audit_logger):
        """Test sensitive data is sanitized."""
        log = audit_logger.log(
            action=AuditAction.LOGIN,
            details={"password": "secret123", "username": "john"},
        )

        assert log.details["password"] == "[REDACTED]"
        assert log.details["username"] == "john"


class TestComplianceManager:
    """Test compliance management."""

    def test_add_restricted_security(self, compliance_manager):
        """Test adding restricted security."""
        compliance_manager.add_restricted_security(
            symbol="AAPL",
            reason="Insider trading window",
            restricted_by="admin123",
        )

        is_restricted, reason = compliance_manager.is_restricted("AAPL")

        assert is_restricted is True
        assert "Insider" in reason

    def test_pre_trade_compliance_check(self, compliance_manager):
        """Test pre-trade compliance checks."""
        # Add position limit rule
        compliance_manager.add_rule(
            name="Position Limit",
            description="Max 15% per position",
            rule_type="position_limit",
            parameters={"max_position_pct": 0.15},
            created_by="admin123",
        )

        checks = compliance_manager.run_pre_trade_checks(
            user_id="user123",
            account_id="account123",
            symbol="MSFT",
            action="buy",
            quantity=30,
            price=400,
            portfolio_value=100000,
            current_positions={},
        )

        assert len(checks) >= 2  # At least restricted + position limit
        assert all(c.passed for c in checks)  # All should pass

    def test_restricted_trade_blocked(self, compliance_manager):
        """Test restricted trade is blocked."""
        compliance_manager.add_restricted_security(
            symbol="XYZ",
            reason="Regulatory hold",
            restricted_by="admin123",
        )

        checks = compliance_manager.run_pre_trade_checks(
            user_id="user123",
            account_id="account123",
            symbol="XYZ",
            action="buy",
            quantity=100,
            price=50,
            portfolio_value=100000,
            current_positions={},
        )

        restricted_check = next(c for c in checks if c.rule_name == "Restricted Security")
        assert restricted_check.passed is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestEnterpriseIntegration:
    """Integration tests for full enterprise workflow."""

    def test_full_user_workflow(self, auth_service, account_manager):
        """Test complete user registration to trading workflow."""
        # 1. Register
        user, _ = auth_service.register(
            "integration@test.com", "SecurePass123", "Integration Test"
        )
        assert user is not None

        # 2. Login
        session, _ = auth_service.login("integration@test.com", "SecurePass123")
        assert session is not None

        # 3. Verify token
        verified_user, _ = auth_service.verify_token(session.access_token)
        assert verified_user.id == user.id

        # 4. Create account
        account, _ = account_manager.create_account(
            user=user,
            name="Test Account",
            account_type=AccountType.PAPER,
            initial_value=100000,
        )
        assert account is not None

        # 5. Get summary
        summary = account_manager.get_account_summary(account.id)
        assert summary.total_value == 100000

    def test_team_collaboration_workflow(self, auth_service, workspace_manager):
        """Test team workspace collaboration workflow."""
        # Create owner
        owner, _ = auth_service.register("owner@team.com", "SecurePass123")
        owner.subscription = SubscriptionTier.ENTERPRISE

        # Create workspace
        workspace, _ = workspace_manager.create_workspace(owner, "Trading Team")

        # Create and invite members
        members = []
        for i in range(3):
            user, _ = auth_service.register(f"member{i}@team.com", "SecurePass123")
            workspace_manager.invite_member(
                workspace.id, owner.id, user.id, user.name
            )
            members.append(user)

        # Share strategies
        workspace_manager.share_strategy(
            workspace.id, owner.id, owner.name,
            "Alpha Strategy", "High alpha factor model",
            {"factors": ["momentum", "value"]},
            ytd_return=0.18, sharpe_ratio=1.8,
        )

        # Check stats
        stats = workspace_manager.get_workspace_stats(workspace.id)
        assert stats.member_count == 4  # Owner + 3 members
        assert stats.strategy_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
