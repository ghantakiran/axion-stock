"""Enterprise & Multi-Account Platform.

Comprehensive enterprise features including:
- User authentication with role-based access control
- Multi-account management (personal, IRA, trust, etc.)
- Team workspaces with shared strategies
- Professional reporting (PDF/Excel)
- Compliance and audit logging
- Subscription tier management

Example:
    from src.enterprise import AuthService, AccountManager

    # Authentication
    auth = AuthService()
    user, error = auth.register("user@example.com", "SecurePass123", "John Doe")
    session, error = auth.login("user@example.com", "SecurePass123")

    # Multi-account
    accounts = AccountManager()
    account, error = accounts.create_account(
        user=user,
        name="Personal Taxable",
        account_type=AccountType.INDIVIDUAL,
    )
"""

from src.enterprise.config import (
    UserRole,
    SubscriptionTier,
    AccountType,
    TaxStatus,
    BrokerType,
    ROLE_PERMISSIONS,
    SUBSCRIPTION_LIMITS,
    AuthConfig,
    AuditConfig,
    ReportConfig,
    EnterpriseConfig,
    DEFAULT_AUTH_CONFIG,
    DEFAULT_AUDIT_CONFIG,
    DEFAULT_REPORT_CONFIG,
    DEFAULT_ENTERPRISE_CONFIG,
)

from src.enterprise.models import (
    User,
    Session,
    APIKey,
    Account,
    AccountSnapshot,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    SharedStrategy,
    ActivityItem,
    AuditLog,
    AuditAction,
    ComplianceRule,
    ComplianceViolation,
    RestrictedSecurity,
)

from src.enterprise.auth import (
    PasswordHasher,
    TokenManager,
    TOTPManager,
    AuthService,
)

from src.enterprise.accounts import (
    AccountManager,
    AccountSummary,
    HouseholdSummary,
)

from src.enterprise.workspaces import (
    WorkspaceManager,
    LeaderboardEntry,
    WorkspaceStats,
)

from src.enterprise.reporting import (
    ReportGenerator,
    ReportScheduler,
    ReportData,
    ReportSection,
    PerformanceMetrics,
    AttributionData,
)

from src.enterprise.compliance import (
    AuditLogger,
    AuditQuery,
    ComplianceManager,
    PreTradeCheck,
)

__all__ = [
    # Config
    "UserRole",
    "SubscriptionTier",
    "AccountType",
    "TaxStatus",
    "BrokerType",
    "ROLE_PERMISSIONS",
    "SUBSCRIPTION_LIMITS",
    "AuthConfig",
    "AuditConfig",
    "ReportConfig",
    "EnterpriseConfig",
    "DEFAULT_AUTH_CONFIG",
    "DEFAULT_AUDIT_CONFIG",
    "DEFAULT_REPORT_CONFIG",
    "DEFAULT_ENTERPRISE_CONFIG",
    # Models
    "User",
    "Session",
    "APIKey",
    "Account",
    "AccountSnapshot",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceRole",
    "SharedStrategy",
    "ActivityItem",
    "AuditLog",
    "AuditAction",
    "ComplianceRule",
    "ComplianceViolation",
    "RestrictedSecurity",
    # Auth
    "PasswordHasher",
    "TokenManager",
    "TOTPManager",
    "AuthService",
    # Accounts
    "AccountManager",
    "AccountSummary",
    "HouseholdSummary",
    # Workspaces
    "WorkspaceManager",
    "LeaderboardEntry",
    "WorkspaceStats",
    # Reporting
    "ReportGenerator",
    "ReportScheduler",
    "ReportData",
    "ReportSection",
    "PerformanceMetrics",
    "AttributionData",
    # Compliance
    "AuditLogger",
    "AuditQuery",
    "ComplianceManager",
    "PreTradeCheck",
]
