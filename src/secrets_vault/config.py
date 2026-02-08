"""PRD-124: Secrets Management & API Credential Vaulting - Configuration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class SecretType(Enum):
    """Types of secrets that can be stored in the vault."""

    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"
    OAUTH_TOKEN = "oauth_token"
    CERTIFICATE = "certificate"
    GENERIC = "generic"


class RotationStrategy(Enum):
    """Strategies for rotating credentials."""

    CREATE_THEN_DELETE = "create_then_delete"
    SWAP = "swap"
    MANUAL = "manual"


class AccessAction(Enum):
    """Actions that can be performed on secrets."""

    READ = "read"
    WRITE = "write"
    ROTATE = "rotate"
    DELETE = "delete"
    LIST = "list"


@dataclass
class VaultConfig:
    """Configuration for the secrets vault."""

    encryption_algorithm: str = "AES-256-GCM"
    default_ttl_seconds: int = 3600
    max_versions: int = 10
    rotation_check_interval: int = 3600
    cache_ttl_seconds: int = 300
    audit_retention_days: int = 90
    enable_env_fallback: bool = True
    allowed_secret_types: List[str] = field(
        default_factory=lambda: [t.value for t in SecretType]
    )
