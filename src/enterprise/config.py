"""Enterprise Configuration.

Configuration for authentication, subscriptions, and enterprise features.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""
    VIEWER = "viewer"  # View portfolios, reports, dashboards
    TRADER = "trader"  # Viewer + execute trades, rebalance
    MANAGER = "manager"  # Trader + create strategies, manage accounts
    ADMIN = "admin"  # Manager + manage users, billing, compliance
    API = "api"  # Programmatic access with scoped tokens


class SubscriptionTier(str, Enum):
    """Subscription tiers with feature gates."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AccountType(str, Enum):
    """Supported account types."""
    INDIVIDUAL = "individual"
    IRA_TRADITIONAL = "ira_traditional"
    IRA_ROTH = "ira_roth"
    JOINT = "joint"
    TRUST = "trust"
    CORPORATE = "corporate"
    PAPER = "paper"


class TaxStatus(str, Enum):
    """Account tax treatment."""
    TAXABLE = "taxable"
    TAX_DEFERRED = "tax_deferred"
    TAX_FREE = "tax_free"


class BrokerType(str, Enum):
    """Supported brokers."""
    ALPACA = "alpaca"
    IBKR = "ibkr"
    PAPER = "paper"


# Role permissions mapping
ROLE_PERMISSIONS = {
    UserRole.VIEWER: {
        "view_portfolios",
        "view_reports",
        "view_dashboards",
        "view_strategies",
    },
    UserRole.TRADER: {
        "view_portfolios",
        "view_reports",
        "view_dashboards",
        "view_strategies",
        "execute_trades",
        "rebalance_portfolio",
        "manage_orders",
    },
    UserRole.MANAGER: {
        "view_portfolios",
        "view_reports",
        "view_dashboards",
        "view_strategies",
        "execute_trades",
        "rebalance_portfolio",
        "manage_orders",
        "create_strategies",
        "manage_accounts",
        "invite_users",
    },
    UserRole.ADMIN: {
        "view_portfolios",
        "view_reports",
        "view_dashboards",
        "view_strategies",
        "execute_trades",
        "rebalance_portfolio",
        "manage_orders",
        "create_strategies",
        "manage_accounts",
        "invite_users",
        "manage_users",
        "manage_billing",
        "manage_compliance",
        "view_audit_logs",
        "manage_workspace",
    },
    UserRole.API: {
        "api_read",
        "api_write",
        "api_execute",
    },
}


# Subscription feature limits
SUBSCRIPTION_LIMITS = {
    SubscriptionTier.FREE: {
        "live_trading": False,
        "max_accounts": 1,
        "account_types": [AccountType.PAPER],
        "max_strategies": 2,
        "backtest_years": 1,
        "ml_predictions": False,
        "options_analytics": "basic",
        "sentiment_data": False,
        "api_requests_daily": 0,
        "team_workspace": False,
        "team_seats": 0,
        "custom_reports": False,
        "white_label": False,
        "priority_support": False,
    },
    SubscriptionTier.PRO: {
        "live_trading": True,
        "max_accounts": 3,
        "account_types": list(AccountType),
        "max_strategies": 999,  # Unlimited
        "backtest_years": 10,
        "ml_predictions": True,
        "options_analytics": "full",
        "sentiment_data": True,
        "api_requests_daily": 1000,
        "team_workspace": False,
        "team_seats": 0,
        "custom_reports": "basic",
        "white_label": False,
        "priority_support": "email",
    },
    SubscriptionTier.ENTERPRISE: {
        "live_trading": True,
        "max_accounts": 999,  # Unlimited
        "account_types": list(AccountType),
        "max_strategies": 999,
        "backtest_years": 20,
        "ml_predictions": True,
        "options_analytics": "full",
        "sentiment_data": True,
        "api_requests_daily": 999999,  # Unlimited
        "team_workspace": True,
        "team_seats": 10,
        "custom_reports": "full",
        "white_label": True,
        "priority_support": "dedicated",
    },
}


@dataclass
class AuthConfig:
    """Authentication configuration."""

    # JWT settings
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire: timedelta = field(default_factory=lambda: timedelta(hours=1))
    refresh_token_expire: timedelta = field(default_factory=lambda: timedelta(days=30))

    # Password settings
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = False
    bcrypt_rounds: int = 12

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: timedelta = field(default_factory=lambda: timedelta(minutes=1))

    # Session settings
    max_concurrent_sessions: int = 5

    # OAuth providers (configure in .env)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None


@dataclass
class AuditConfig:
    """Audit logging configuration."""

    enabled: bool = True
    log_level: str = "INFO"
    retention_days: int = 2555  # 7 years for compliance
    sensitive_fields: list = field(default_factory=lambda: [
        "password", "token", "secret", "api_key"
    ])


@dataclass
class ReportConfig:
    """Report generation configuration."""

    output_dir: str = "./reports"
    logo_path: Optional[str] = None
    company_name: str = "Axion"
    default_format: str = "pdf"  # pdf, excel, html
    max_generation_time: int = 30  # seconds


@dataclass
class EnterpriseConfig:
    """Main enterprise configuration."""

    auth: AuthConfig = field(default_factory=AuthConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    report: ReportConfig = field(default_factory=ReportConfig)

    # Email settings
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str = "noreply@axion.ai"

    # Stripe settings
    stripe_api_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None


# Default configuration
DEFAULT_AUTH_CONFIG = AuthConfig()
DEFAULT_AUDIT_CONFIG = AuditConfig()
DEFAULT_REPORT_CONFIG = ReportConfig()
DEFAULT_ENTERPRISE_CONFIG = EnterpriseConfig()
