"""Enterprise Data Models.

Core data structures for users, accounts, workspaces, and audit logs.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Any
from enum import Enum
import uuid

from src.enterprise.config import (
    UserRole, SubscriptionTier, AccountType, TaxStatus, BrokerType,
)


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# =============================================================================
# User Models
# =============================================================================


@dataclass
class User:
    """User account."""

    id: str = field(default_factory=generate_uuid)
    email: str = ""
    password_hash: Optional[str] = None
    name: str = ""
    role: UserRole = UserRole.TRADER
    subscription: SubscriptionTier = SubscriptionTier.FREE

    # Profile
    avatar_url: Optional[str] = None
    timezone: str = "UTC"
    preferences: dict = field(default_factory=dict)

    # OAuth
    google_id: Optional[str] = None
    github_id: Optional[str] = None
    apple_id: Optional[str] = None

    # 2FA
    totp_secret: Optional[str] = None
    totp_enabled: bool = False

    # Status
    is_active: bool = True
    is_verified: bool = False
    email_verified_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary."""
        data = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "subscription": self.subscription.value,
            "avatar_url": self.avatar_url,
            "timezone": self.timezone,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "totp_enabled": self.totp_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_sensitive:
            data["totp_secret"] = self.totp_secret
        return data


@dataclass
class Session:
    """User session."""

    id: str = field(default_factory=generate_uuid)
    user_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_activity_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class APIKey:
    """API key for programmatic access."""

    id: str = field(default_factory=generate_uuid)
    user_id: str = ""
    name: str = ""
    key_hash: str = ""  # Hashed key (only stored hashed)
    key_prefix: str = ""  # First 8 chars for identification
    scopes: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    request_count: int = 0


# =============================================================================
# Account Models
# =============================================================================


@dataclass
class Account:
    """Trading account."""

    id: str = field(default_factory=generate_uuid)
    owner_id: str = ""  # User ID
    name: str = ""
    account_type: AccountType = AccountType.INDIVIDUAL
    broker: BrokerType = BrokerType.PAPER
    broker_account_id: Optional[str] = None  # External broker account ID

    # Strategy
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    target_allocation: dict[str, float] = field(default_factory=dict)

    # Financials
    cash_balance: float = 0.0
    total_value: float = 0.0
    cost_basis: float = 0.0

    # Tax
    tax_status: TaxStatus = TaxStatus.TAXABLE

    # Benchmark
    benchmark: str = "SPY"

    # Dates
    inception_date: date = field(default_factory=date.today)

    # Status
    is_active: bool = True
    is_primary: bool = False

    # Permissions (user IDs who can access)
    permissions: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "account_type": self.account_type.value,
            "broker": self.broker.value,
            "strategy_name": self.strategy_name,
            "cash_balance": self.cash_balance,
            "total_value": self.total_value,
            "tax_status": self.tax_status.value,
            "benchmark": self.benchmark,
            "inception_date": self.inception_date.isoformat(),
            "is_active": self.is_active,
            "is_primary": self.is_primary,
        }


@dataclass
class AccountSnapshot:
    """Point-in-time account state."""

    id: str = field(default_factory=generate_uuid)
    account_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_value: float = 0.0
    cash_balance: float = 0.0
    positions_value: float = 0.0
    day_pnl: float = 0.0
    total_pnl: float = 0.0
    positions: dict = field(default_factory=dict)  # Symbol -> quantity, value


# =============================================================================
# Workspace Models
# =============================================================================


class WorkspaceRole(str, Enum):
    """Workspace member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


@dataclass
class Workspace:
    """Team workspace for collaboration."""

    id: str = field(default_factory=generate_uuid)
    name: str = ""
    description: str = ""
    owner_id: str = ""

    # Settings
    settings: dict = field(default_factory=dict)
    logo_url: Optional[str] = None

    # Stats (cached)
    member_count: int = 0
    strategy_count: int = 0
    total_aum: float = 0.0

    # Status
    is_active: bool = True

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "member_count": self.member_count,
            "strategy_count": self.strategy_count,
            "total_aum": self.total_aum,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class WorkspaceMember:
    """Workspace membership."""

    workspace_id: str = ""
    user_id: str = ""
    role: WorkspaceRole = WorkspaceRole.MEMBER
    joined_at: datetime = field(default_factory=datetime.utcnow)
    invited_by: Optional[str] = None


@dataclass
class SharedStrategy:
    """Strategy shared within a workspace."""

    id: str = field(default_factory=generate_uuid)
    workspace_id: str = ""
    creator_id: str = ""
    name: str = ""
    description: str = ""
    config: dict = field(default_factory=dict)

    # Performance (cached)
    ytd_return: float = 0.0
    sharpe_ratio: float = 0.0
    total_return: float = 0.0

    # Usage
    use_count: int = 0
    fork_count: int = 0

    # Status
    is_public: bool = False  # Visible to all workspace members

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ActivityItem:
    """Activity feed item."""

    id: str = field(default_factory=generate_uuid)
    workspace_id: str = ""
    user_id: str = ""
    user_name: str = ""
    action: str = ""  # created_strategy, executed_trade, shared_research, etc.
    resource_type: str = ""
    resource_id: str = ""
    resource_name: str = ""
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Audit Models
# =============================================================================


class AuditAction(str, Enum):
    """Audit log action types."""
    # Auth
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    TOTP_ENABLE = "totp_enable"
    TOTP_DISABLE = "totp_disable"

    # User
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    ROLE_CHANGE = "role_change"

    # Account
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_UPDATE = "account_update"
    ACCOUNT_DELETE = "account_delete"

    # Trading
    ORDER_SUBMIT = "order_submit"
    ORDER_CANCEL = "order_cancel"
    ORDER_FILL = "order_fill"
    REBALANCE = "rebalance"

    # Strategy
    STRATEGY_CREATE = "strategy_create"
    STRATEGY_UPDATE = "strategy_update"
    STRATEGY_DELETE = "strategy_delete"
    STRATEGY_ACTIVATE = "strategy_activate"

    # Workspace
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_UPDATE = "workspace_update"
    MEMBER_INVITE = "member_invite"
    MEMBER_REMOVE = "member_remove"

    # Compliance
    COMPLIANCE_VIOLATION = "compliance_violation"
    RESTRICTED_TRADE = "restricted_trade"

    # System
    SETTING_CHANGE = "setting_change"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    REPORT_GENERATE = "report_generate"
    EXPORT_DATA = "export_data"


@dataclass
class AuditLog:
    """Audit log entry."""

    id: str = field(default_factory=generate_uuid)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: AuditAction = AuditAction.LOGIN
    resource_type: str = ""  # user, account, order, strategy, etc.
    resource_id: Optional[str] = None
    details: dict = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"  # success, failure, warning
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "user_email": self.user_email,
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "status": self.status,
        }


# =============================================================================
# Compliance Models
# =============================================================================


@dataclass
class RestrictedSecurity:
    """Security on restricted trading list."""

    symbol: str = ""
    reason: str = ""  # insider, regulatory, risk_limit, etc.
    restricted_by: str = ""  # User ID who added
    restriction_type: str = "all"  # all, buy_only, sell_only
    start_date: date = field(default_factory=date.today)
    end_date: Optional[date] = None
    notes: str = ""


@dataclass
class ComplianceRule:
    """Compliance rule definition."""

    id: str = field(default_factory=generate_uuid)
    name: str = ""
    description: str = ""
    rule_type: str = ""  # position_limit, sector_limit, restricted_list, etc.
    parameters: dict = field(default_factory=dict)
    is_active: bool = True
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ComplianceViolation:
    """Compliance violation record."""

    id: str = field(default_factory=generate_uuid)
    rule_id: str = ""
    rule_name: str = ""
    account_id: str = ""
    user_id: str = ""
    violation_type: str = ""
    details: dict = field(default_factory=dict)
    severity: str = "warning"  # info, warning, critical
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
