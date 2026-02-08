"""Configuration for multi-tenancy data isolation & row-level security."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class AccessLevel(str, Enum):
    """Access level for resource permissions."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class ResourceType(str, Enum):
    """Types of resources that can be access-controlled."""
    PORTFOLIO = "portfolio"
    TRADE = "trade"
    ORDER = "order"
    WATCHLIST = "watchlist"
    MODEL = "model"
    REPORT = "report"


class PolicyAction(str, Enum):
    """Action result from a policy evaluation."""
    ALLOW = "allow"
    DENY = "deny"


# Role hierarchy: higher value = more permissions
ROLE_HIERARCHY: Dict[str, int] = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
}

# Tables that are shared across all workspaces (no tenant filtering)
SHARED_RESOURCE_TABLES: Set[str] = {
    "market_data",
    "market_data_daily",
    "exchange_info",
    "symbols",
    "indices",
    "sectors",
    "economic_indicators",
    "benchmark_returns",
    "risk_free_rates",
    "dividends_calendar",
    "earnings_calendar",
}

# Default rate limits per workspace (requests per minute)
DEFAULT_RATE_LIMIT = 600
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

# Maximum allowed workspaces per IP
MAX_WORKSPACES_PER_IP = 5

# Cache TTL for policy evaluations (seconds)
POLICY_CACHE_TTL_SECONDS = 300

# Audit log retention days
AUDIT_LOG_RETENTION_DAYS = 90


@dataclass
class TenancyConfig:
    """Configuration for multi-tenancy data isolation."""

    enabled: bool = True
    enforce_rls: bool = True
    audit_logging: bool = True
    rate_limit_per_workspace: int = DEFAULT_RATE_LIMIT
    rate_limit_window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS
    max_workspaces_per_ip: int = MAX_WORKSPACES_PER_IP
    policy_cache_ttl: int = POLICY_CACHE_TTL_SECONDS
    shared_tables: Set[str] = field(default_factory=lambda: set(SHARED_RESOURCE_TABLES))
    allowed_cross_workspace_roles: List[str] = field(default_factory=lambda: ["admin"])
    audit_retention_days: int = AUDIT_LOG_RETENTION_DAYS
    ip_restriction_enabled: bool = False
    block_cross_tenant_requests: bool = True
