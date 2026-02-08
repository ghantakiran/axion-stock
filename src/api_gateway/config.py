"""Configuration for API Gateway & Advanced Rate Limiting."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


class RateLimitTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    INTERNAL = "internal"


class VersionStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


@dataclass
class GatewayConfig:
    """Top-level gateway configuration."""

    enable_rate_limiting: bool = True
    enable_analytics: bool = True
    enable_versioning: bool = True
    enable_validation: bool = True
    default_rate_limit: int = 60  # per minute
    burst_allowance: float = 1.5
    max_payload_bytes: int = 10_000_000
    default_version: str = "v1"


@dataclass
class TierConfig:
    """Rate-limit configuration for a specific tier."""

    tier: RateLimitTier = RateLimitTier.FREE
    requests_per_minute: int = 10
    requests_per_day: int = 1000
    burst_multiplier: float = 1.5


# Default tier configurations
DEFAULT_TIERS: Dict[RateLimitTier, TierConfig] = {
    RateLimitTier.FREE: TierConfig(
        tier=RateLimitTier.FREE,
        requests_per_minute=10,
        requests_per_day=1000,
        burst_multiplier=1.5,
    ),
    RateLimitTier.PRO: TierConfig(
        tier=RateLimitTier.PRO,
        requests_per_minute=60,
        requests_per_day=10000,
        burst_multiplier=1.5,
    ),
    RateLimitTier.ENTERPRISE: TierConfig(
        tier=RateLimitTier.ENTERPRISE,
        requests_per_minute=600,
        requests_per_day=100000,
        burst_multiplier=1.5,
    ),
    RateLimitTier.INTERNAL: TierConfig(
        tier=RateLimitTier.INTERNAL,
        requests_per_minute=6000,
        requests_per_day=1000000,
        burst_multiplier=1.5,
    ),
}
