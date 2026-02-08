"""PRD-124: Secrets Management & API Credential Vaulting."""

from .config import (
    SecretType,
    RotationStrategy,
    AccessAction,
    VaultConfig,
)
from .vault import (
    SecretEntry,
    SecretsVault,
)
from .rotation import (
    RotationPolicy,
    RotationResult,
    CredentialRotation,
)
from .access import (
    AccessPolicy,
    AccessAuditEntry,
    AccessControl,
)
from .client import (
    CacheEntry,
    SecretsClient,
)

__all__ = [
    # Config
    "SecretType",
    "RotationStrategy",
    "AccessAction",
    "VaultConfig",
    # Vault
    "SecretEntry",
    "SecretsVault",
    # Rotation
    "RotationPolicy",
    "RotationResult",
    "CredentialRotation",
    # Access
    "AccessPolicy",
    "AccessAuditEntry",
    "AccessControl",
    # Client
    "CacheEntry",
    "SecretsClient",
]
