"""Secrets manager with encryption, rotation, and access auditing."""

import base64
import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:  # pragma: no cover
    _HAS_FERNET = False

logger = logging.getLogger(__name__)


@dataclass
class SecretAccess:
    """Record of a secret access event."""

    secret_name: str
    accessed_by: str
    accessed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    action: str = "read"


@dataclass
class Secret:
    """An encrypted secret entry."""

    name: str
    encrypted_value: str
    description: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rotation_count: int = 0
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the secret has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def masked_value(self) -> str:
        """Return a masked representation."""
        return "***ENCRYPTED***"


class SecretsManager:
    """Manages encrypted secrets with rotation and access auditing.

    Uses a simple XOR-based encryption for demonstration. In production,
    this would integrate with HashiCorp Vault or AWS Secrets Manager.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        self._key = encryption_key or os.environ.get(
            "AXION_SECRETS_KEY", "default-dev-key-change-in-production"
        )
        self._fernet = self._build_fernet(self._key)
        self._secrets: Dict[str, Secret] = {}
        self._access_log: List[SecretAccess] = []
        self._lock = threading.RLock()

    @staticmethod
    def _build_fernet(key: str) -> "Fernet | None":
        """Derive a Fernet instance from the passphrase, or None."""
        if not _HAS_FERNET:
            logger.warning(
                "cryptography not installed — using XOR fallback. "
                "Install 'cryptography' for production use."
            )
            return None
        derived = hashlib.sha256(key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(derived))

    def store(
        self,
        name: str,
        value: str,
        description: str = "",
        expires_at: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Secret:
        """Store a secret with encryption."""
        with self._lock:
            encrypted = self._encrypt(value)
            secret = Secret(
                name=name,
                encrypted_value=encrypted,
                description=description,
                expires_at=expires_at,
                tags=tags or {},
            )
            self._secrets[name] = secret
            logger.info("Secret stored: %s", name)
            return secret

    def retrieve(self, name: str, accessed_by: str = "system") -> Optional[str]:
        """Retrieve and decrypt a secret."""
        with self._lock:
            secret = self._secrets.get(name)
            if secret is None:
                return None

            self._access_log.append(SecretAccess(
                secret_name=name, accessed_by=accessed_by, action="read",
            ))

            if secret.is_expired:
                logger.warning("Secret '%s' is expired", name)

            return self._decrypt(secret.encrypted_value)

    def rotate(self, name: str, new_value: str,
               rotated_by: str = "system") -> bool:
        """Rotate a secret to a new value."""
        with self._lock:
            secret = self._secrets.get(name)
            if secret is None:
                return False

            secret.encrypted_value = self._encrypt(new_value)
            secret.rotated_at = datetime.now(timezone.utc)
            secret.rotation_count += 1

            self._access_log.append(SecretAccess(
                secret_name=name, accessed_by=rotated_by, action="rotate",
            ))

            logger.info("Secret rotated: %s (count: %d)",
                         name, secret.rotation_count)
            return True

    def delete(self, name: str) -> bool:
        """Delete a secret."""
        with self._lock:
            return self._secrets.pop(name, None) is not None

    def exists(self, name: str) -> bool:
        """Check if a secret exists."""
        with self._lock:
            return name in self._secrets

    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get secret metadata without decrypting the value."""
        with self._lock:
            secret = self._secrets.get(name)
            if secret is None:
                return None
            return {
                "name": secret.name,
                "description": secret.description,
                "created_at": secret.created_at.isoformat(),
                "rotated_at": secret.rotated_at.isoformat()
                if secret.rotated_at else None,
                "expires_at": secret.expires_at.isoformat()
                if secret.expires_at else None,
                "is_expired": secret.is_expired,
                "rotation_count": secret.rotation_count,
                "tags": secret.tags,
            }

    def list_secrets(self) -> List[str]:
        """List all secret names (not values)."""
        with self._lock:
            return sorted(self._secrets.keys())

    def get_expired(self) -> List[str]:
        """Get names of expired secrets."""
        with self._lock:
            return [
                name for name, secret in self._secrets.items()
                if secret.is_expired
            ]

    def get_access_log(self, secret_name: Optional[str] = None,
                       limit: int = 50) -> List[SecretAccess]:
        """Get access audit log."""
        with self._lock:
            log = self._access_log
            if secret_name:
                log = [a for a in log if a.secret_name == secret_name]
            return list(reversed(log[-limit:]))

    def clear(self) -> None:
        """Clear all secrets and access log."""
        with self._lock:
            self._secrets.clear()
            self._access_log.clear()

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt with Fernet (AES-128-CBC + HMAC) or XOR fallback."""
        if self._fernet is not None:
            return self._fernet.encrypt(plaintext.encode()).decode()
        # XOR fallback for dev/test without cryptography package
        key_bytes = hashlib.sha256(self._key.encode()).digest()
        plain_bytes = plaintext.encode()
        encrypted = bytes(
            b ^ key_bytes[i % len(key_bytes)]
            for i, b in enumerate(plain_bytes)
        )
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt with Fernet or XOR fallback."""
        if self._fernet is not None:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        key_bytes = hashlib.sha256(self._key.encode()).digest()
        encrypted = base64.b64decode(ciphertext.encode())
        decrypted = bytes(
            b ^ key_bytes[i % len(key_bytes)]
            for i, b in enumerate(encrypted)
        )
        return decrypted.decode()
