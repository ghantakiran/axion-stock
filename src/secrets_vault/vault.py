"""PRD-124: Secrets Management & API Credential Vaulting - Vault Core."""

import base64
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .config import SecretType, VaultConfig

try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:  # pragma: no cover
    _HAS_FERNET = False


@dataclass
class SecretEntry:
    """A single versioned secret stored in the vault."""

    secret_id: str
    key_path: str
    encrypted_value: str
    secret_type: SecretType
    version: int
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rotated_at: Optional[datetime] = None
    owner_service: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SecretsVault:
    """Encrypted secrets vault with versioning and expiration.

    Uses Fernet (AES-128-CBC + HMAC-SHA256) when the ``cryptography``
    package is installed. Falls back to XOR for environments without
    the dependency (dev/test only — logs a warning).
    Production deployments should install ``cryptography`` or integrate
    with HSM / KMS.
    """

    def __init__(self, config: Optional[VaultConfig] = None, encryption_key: str = "axion-vault-key"):
        self.config = config or VaultConfig()
        self._encryption_key = encryption_key
        self._fernet = self._build_fernet(encryption_key)
        # key_path -> list of SecretEntry (ordered by version, latest last)
        self._store: Dict[str, List[SecretEntry]] = {}
        self._deleted: Dict[str, List[SecretEntry]] = {}

    @staticmethod
    def _build_fernet(key: str) -> "Fernet | None":
        """Derive a Fernet key from the user-supplied passphrase."""
        if not _HAS_FERNET:
            import logging
            logging.getLogger(__name__).warning(
                "cryptography not installed — falling back to XOR encryption. "
                "Install 'cryptography' for production use."
            )
            return None
        # Derive a URL-safe 32-byte key via SHA-256
        derived = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)

    # ── Encryption ────────────────────────────────────────────────────

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt using Fernet (preferred) or XOR fallback."""
        if self._fernet is not None:
            token = self._fernet.encrypt(plaintext.encode())
            return token.decode()
        return self._xor_encrypt(plaintext)

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt using Fernet (preferred) or XOR fallback."""
        if self._fernet is not None:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        return self._xor_decrypt(ciphertext)

    def _xor_encrypt(self, plaintext: str) -> str:
        """XOR-based fallback encryption (dev/test only)."""
        key = self._encryption_key
        result = []
        for i, ch in enumerate(plaintext):
            xor_val = ord(ch) ^ ord(key[i % len(key)])
            result.append(format(xor_val, "02x"))
        return "".join(result)

    def _xor_decrypt(self, ciphertext: str) -> str:
        """XOR-based fallback decryption (dev/test only)."""
        key = self._encryption_key
        result = []
        chunks = [ciphertext[i : i + 2] for i in range(0, len(ciphertext), 2)]
        for i, chunk in enumerate(chunks):
            xor_val = int(chunk, 16) ^ ord(key[i % len(key)])
            result.append(chr(xor_val))
        return "".join(result)

    # ── CRUD ──────────────────────────────────────────────────────────

    def put(
        self,
        key_path: str,
        value: str,
        secret_type: SecretType = SecretType.GENERIC,
        owner_service: str = "",
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SecretEntry:
        """Store or update a secret, creating a new version."""
        encrypted = self._encrypt(value)
        ttl = ttl_seconds if ttl_seconds is not None else self.config.default_ttl_seconds
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl > 0 else None

        # Determine version
        existing = self._store.get(key_path, [])
        version = existing[-1].version + 1 if existing else 1

        entry = SecretEntry(
            secret_id=uuid.uuid4().hex[:16],
            key_path=key_path,
            encrypted_value=encrypted,
            secret_type=secret_type,
            version=version,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            rotated_at=None,
            owner_service=owner_service,
            metadata=metadata or {},
        )

        if key_path not in self._store:
            self._store[key_path] = []
        self._store[key_path].append(entry)

        # Enforce max versions
        while len(self._store[key_path]) > self.config.max_versions:
            self._store[key_path].pop(0)

        return entry

    def get(self, key_path: str, version: Optional[int] = None) -> Optional[SecretEntry]:
        """Retrieve a secret entry. Returns latest version by default."""
        entries = self._store.get(key_path)
        if not entries:
            return None

        if version is not None:
            for entry in entries:
                if entry.version == version:
                    return entry
            return None

        return entries[-1]

    def get_value(self, key_path: str, version: Optional[int] = None) -> Optional[str]:
        """Retrieve and decrypt a secret value."""
        entry = self.get(key_path, version)
        if entry is None:
            return None
        return self._decrypt(entry.encrypted_value)

    def delete(self, key_path: str) -> bool:
        """Delete all versions of a secret."""
        if key_path not in self._store:
            return False
        self._deleted[key_path] = self._store.pop(key_path)
        return True

    def list_secrets(self, prefix: Optional[str] = None) -> List[SecretEntry]:
        """List latest version of all secrets, optionally filtered by prefix."""
        results = []
        for key_path, entries in self._store.items():
            if prefix and not key_path.startswith(prefix):
                continue
            if entries:
                results.append(entries[-1])
        return results

    def get_versions(self, key_path: str) -> List[SecretEntry]:
        """Get all versions of a secret."""
        return list(self._store.get(key_path, []))

    def rollback_version(self, key_path: str, target_version: int) -> Optional[SecretEntry]:
        """Rollback to a previous version by creating a new version with old value."""
        entries = self._store.get(key_path)
        if not entries:
            return None

        target = None
        for entry in entries:
            if entry.version == target_version:
                target = entry
                break

        if target is None:
            return None

        # Create new version with the old encrypted value
        new_version = entries[-1].version + 1
        rolled_back = SecretEntry(
            secret_id=uuid.uuid4().hex[:16],
            key_path=key_path,
            encrypted_value=target.encrypted_value,
            secret_type=target.secret_type,
            version=new_version,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.config.default_ttl_seconds),
            created_at=datetime.now(timezone.utc),
            rotated_at=None,
            owner_service=target.owner_service,
            metadata={**target.metadata, "rolled_back_from": target_version},
        )

        self._store[key_path].append(rolled_back)

        # Enforce max versions
        while len(self._store[key_path]) > self.config.max_versions:
            self._store[key_path].pop(0)

        return rolled_back

    def search(self, query: str) -> List[SecretEntry]:
        """Search secrets by key path substring or metadata."""
        results = []
        query_lower = query.lower()
        for key_path, entries in self._store.items():
            if not entries:
                continue
            latest = entries[-1]
            if query_lower in key_path.lower():
                results.append(latest)
                continue
            if latest.owner_service and query_lower in latest.owner_service.lower():
                results.append(latest)
                continue
            for k, v in latest.metadata.items():
                if query_lower in str(v).lower():
                    results.append(latest)
                    break
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get vault statistics."""
        total_secrets = len(self._store)
        total_versions = sum(len(v) for v in self._store.values())
        now = datetime.now(timezone.utc)

        expired = 0
        by_type: Dict[str, int] = {}
        by_owner: Dict[str, int] = {}

        for entries in self._store.values():
            if not entries:
                continue
            latest = entries[-1]
            if latest.expires_at and latest.expires_at < now:
                expired += 1
            type_key = latest.secret_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            if latest.owner_service:
                by_owner[latest.owner_service] = by_owner.get(latest.owner_service, 0) + 1

        return {
            "total_secrets": total_secrets,
            "total_versions": total_versions,
            "expired_secrets": expired,
            "deleted_secrets": len(self._deleted),
            "by_type": by_type,
            "by_owner": by_owner,
            "max_versions_allowed": self.config.max_versions,
        }
