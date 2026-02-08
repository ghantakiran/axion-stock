"""Tests for PRD-124: Secrets Management & API Credential Vaulting."""

import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from src.secrets_vault.config import (
    SecretType,
    RotationStrategy,
    AccessAction,
    VaultConfig,
)
from src.secrets_vault.vault import SecretEntry, SecretsVault
from src.secrets_vault.rotation import RotationPolicy, RotationResult, CredentialRotation
from src.secrets_vault.access import AccessPolicy, AccessAuditEntry, AccessControl
from src.secrets_vault.client import CacheEntry, SecretsClient


# ── Config Tests ──────────────────────────────────────────────────────


class TestVaultConfig:
    def test_secret_type_values(self):
        assert SecretType.API_KEY.value == "api_key"
        assert SecretType.DATABASE_PASSWORD.value == "database_password"
        assert SecretType.OAUTH_TOKEN.value == "oauth_token"
        assert SecretType.CERTIFICATE.value == "certificate"
        assert SecretType.GENERIC.value == "generic"

    def test_secret_type_count(self):
        assert len(SecretType) == 5

    def test_rotation_strategy_values(self):
        assert RotationStrategy.CREATE_THEN_DELETE.value == "create_then_delete"
        assert RotationStrategy.SWAP.value == "swap"
        assert RotationStrategy.MANUAL.value == "manual"

    def test_rotation_strategy_count(self):
        assert len(RotationStrategy) == 3

    def test_access_action_values(self):
        assert AccessAction.READ.value == "read"
        assert AccessAction.WRITE.value == "write"
        assert AccessAction.ROTATE.value == "rotate"
        assert AccessAction.DELETE.value == "delete"
        assert AccessAction.LIST.value == "list"

    def test_access_action_count(self):
        assert len(AccessAction) == 5

    def test_vault_config_defaults(self):
        cfg = VaultConfig()
        assert cfg.encryption_algorithm == "AES-256-GCM"
        assert cfg.default_ttl_seconds == 3600
        assert cfg.max_versions == 10
        assert cfg.rotation_check_interval == 3600
        assert cfg.cache_ttl_seconds == 300
        assert cfg.audit_retention_days == 90

    def test_vault_config_custom(self):
        cfg = VaultConfig(default_ttl_seconds=7200, max_versions=5)
        assert cfg.default_ttl_seconds == 7200
        assert cfg.max_versions == 5

    def test_vault_config_allowed_types(self):
        cfg = VaultConfig()
        assert len(cfg.allowed_secret_types) == 5
        assert "api_key" in cfg.allowed_secret_types

    def test_vault_config_env_fallback(self):
        cfg = VaultConfig()
        assert cfg.enable_env_fallback is True


# ── Vault Tests ───────────────────────────────────────────────────────


class TestSecretsVault:
    def setup_method(self):
        self.config = VaultConfig(max_versions=5)
        self.vault = SecretsVault(config=self.config, encryption_key="test-key-123")

    def test_put_and_get(self):
        entry = self.vault.put("broker/alpaca/api_key", "sk-123abc", SecretType.API_KEY)
        assert entry.key_path == "broker/alpaca/api_key"
        assert entry.version == 1
        assert entry.secret_type == SecretType.API_KEY

    def test_get_value_decrypts(self):
        self.vault.put("db/password", "super-secret-pw")
        value = self.vault.get_value("db/password")
        assert value == "super-secret-pw"

    def test_encryption_roundtrip(self):
        original = "my-api-key-with-special-chars!@#$%"
        self.vault.put("test/key", original)
        decrypted = self.vault.get_value("test/key")
        assert decrypted == original

    def test_encrypted_value_differs(self):
        self.vault.put("test/key", "plaintext-value")
        entry = self.vault.get("test/key")
        assert entry.encrypted_value != "plaintext-value"

    def test_versioning(self):
        self.vault.put("service/token", "v1-token")
        self.vault.put("service/token", "v2-token")
        self.vault.put("service/token", "v3-token")

        latest = self.vault.get("service/token")
        assert latest.version == 3
        assert self.vault.get_value("service/token") == "v3-token"

    def test_get_specific_version(self):
        self.vault.put("svc/key", "value-1")
        self.vault.put("svc/key", "value-2")

        v1 = self.vault.get("svc/key", version=1)
        assert v1 is not None
        assert v1.version == 1

    def test_get_value_specific_version(self):
        self.vault.put("svc/key", "value-1")
        self.vault.put("svc/key", "value-2")
        assert self.vault.get_value("svc/key", version=1) == "value-1"
        assert self.vault.get_value("svc/key", version=2) == "value-2"

    def test_get_nonexistent(self):
        assert self.vault.get("nonexistent/path") is None
        assert self.vault.get_value("nonexistent/path") is None

    def test_get_nonexistent_version(self):
        self.vault.put("svc/key", "value-1")
        assert self.vault.get("svc/key", version=99) is None

    def test_delete(self):
        self.vault.put("temp/secret", "delete-me")
        assert self.vault.delete("temp/secret") is True
        assert self.vault.get("temp/secret") is None

    def test_delete_nonexistent(self):
        assert self.vault.delete("no/such/key") is False

    def test_list_secrets(self):
        self.vault.put("svc-a/key1", "v1")
        self.vault.put("svc-a/key2", "v2")
        self.vault.put("svc-b/key1", "v3")

        all_secrets = self.vault.list_secrets()
        assert len(all_secrets) == 3

    def test_list_secrets_prefix(self):
        self.vault.put("svc-a/key1", "v1")
        self.vault.put("svc-a/key2", "v2")
        self.vault.put("svc-b/key1", "v3")

        filtered = self.vault.list_secrets(prefix="svc-a/")
        assert len(filtered) == 2

    def test_get_versions(self):
        self.vault.put("versioned/key", "v1")
        self.vault.put("versioned/key", "v2")
        self.vault.put("versioned/key", "v3")

        versions = self.vault.get_versions("versioned/key")
        assert len(versions) == 3
        assert versions[0].version == 1
        assert versions[-1].version == 3

    def test_get_versions_empty(self):
        assert self.vault.get_versions("no/key") == []

    def test_max_versions_enforced(self):
        for i in range(8):
            self.vault.put("limited/key", f"value-{i}")

        versions = self.vault.get_versions("limited/key")
        assert len(versions) == 5  # max_versions=5

    def test_rollback_version(self):
        self.vault.put("rb/key", "original-value")
        self.vault.put("rb/key", "updated-value")

        rolled = self.vault.rollback_version("rb/key", 1)
        assert rolled is not None
        assert rolled.version == 3
        assert self.vault.get_value("rb/key") == "original-value"

    def test_rollback_nonexistent_path(self):
        assert self.vault.rollback_version("no/key", 1) is None

    def test_rollback_nonexistent_version(self):
        self.vault.put("rb/key", "val")
        assert self.vault.rollback_version("rb/key", 99) is None

    def test_search_by_path(self):
        self.vault.put("broker/alpaca/key", "k1")
        self.vault.put("broker/ib/key", "k2")
        self.vault.put("db/postgres/pass", "p1")

        results = self.vault.search("broker")
        assert len(results) == 2

    def test_search_by_owner(self):
        self.vault.put("svc/key", "v", owner_service="trading-engine")
        self.vault.put("svc/key2", "v", owner_service="risk-service")

        results = self.vault.search("trading")
        assert len(results) == 1

    def test_search_by_metadata(self):
        self.vault.put("svc/key", "v", metadata={"env": "production"})
        self.vault.put("svc/key2", "v", metadata={"env": "staging"})

        results = self.vault.search("production")
        assert len(results) == 1

    def test_search_no_results(self):
        self.vault.put("a/b", "v")
        assert self.vault.search("zzz") == []

    def test_put_with_owner(self):
        entry = self.vault.put("svc/key", "v", owner_service="my-service")
        assert entry.owner_service == "my-service"

    def test_put_with_metadata(self):
        entry = self.vault.put("svc/key", "v", metadata={"env": "prod"})
        assert entry.metadata["env"] == "prod"

    def test_put_with_ttl(self):
        entry = self.vault.put("ttl/key", "v", ttl_seconds=60)
        assert entry.expires_at is not None
        assert entry.expires_at > datetime.now(timezone.utc)

    def test_put_zero_ttl(self):
        entry = self.vault.put("noexpiry/key", "v", ttl_seconds=0)
        assert entry.expires_at is None

    def test_secret_id_generated(self):
        entry = self.vault.put("svc/key", "v")
        assert len(entry.secret_id) == 16

    def test_statistics(self):
        self.vault.put("a/key", "v1", SecretType.API_KEY, owner_service="svc-a")
        self.vault.put("b/key", "v2", SecretType.DATABASE_PASSWORD, owner_service="svc-b")
        self.vault.put("a/key", "v1-updated", SecretType.API_KEY, owner_service="svc-a")

        stats = self.vault.get_statistics()
        assert stats["total_secrets"] == 2
        assert stats["total_versions"] == 3
        assert stats["by_type"]["api_key"] == 1
        assert stats["by_type"]["database_password"] == 1
        assert stats["by_owner"]["svc-a"] == 1

    def test_statistics_empty(self):
        stats = self.vault.get_statistics()
        assert stats["total_secrets"] == 0
        assert stats["total_versions"] == 0

    def test_statistics_deleted(self):
        self.vault.put("del/key", "v")
        self.vault.delete("del/key")
        stats = self.vault.get_statistics()
        assert stats["deleted_secrets"] == 1


# ── Rotation Tests ────────────────────────────────────────────────────


class TestCredentialRotation:
    def setup_method(self):
        self.vault = SecretsVault(encryption_key="rotation-key")
        self.rotation = CredentialRotation(self.vault)

    def test_add_policy(self):
        policy = self.rotation.add_policy(
            "broker/alpaca/key",
            RotationStrategy.CREATE_THEN_DELETE,
            interval_hours=24,
        )
        assert policy.key_path == "broker/alpaca/key"
        assert policy.strategy == RotationStrategy.CREATE_THEN_DELETE
        assert policy.interval_hours == 24
        assert policy.enabled is True
        assert len(policy.policy_id) == 16

    def test_add_policy_disabled(self):
        policy = self.rotation.add_policy("svc/key", enabled=False)
        assert policy.enabled is False

    def test_remove_policy(self):
        policy = self.rotation.add_policy("svc/key")
        assert self.rotation.remove_policy(policy.policy_id) is True
        assert self.rotation.get_policy(policy.policy_id) is None

    def test_remove_nonexistent_policy(self):
        assert self.rotation.remove_policy("no-such-id") is False

    def test_get_policy(self):
        policy = self.rotation.add_policy("svc/key")
        fetched = self.rotation.get_policy(policy.policy_id)
        assert fetched is not None
        assert fetched.policy_id == policy.policy_id

    def test_execute_rotation(self):
        self.vault.put("broker/key", "old-key", SecretType.API_KEY)
        policy = self.rotation.add_policy("broker/key")

        result = self.rotation.execute_rotation(policy.policy_id, new_value="new-key-abc")
        assert result.success is True
        assert result.old_version == 1
        assert result.new_version == 2
        assert result.duration_seconds >= 0

    def test_execute_rotation_updates_vault(self):
        self.vault.put("svc/token", "original")
        policy = self.rotation.add_policy("svc/token")

        self.rotation.execute_rotation(policy.policy_id, new_value="rotated-token")
        assert self.vault.get_value("svc/token") == "rotated-token"

    def test_execute_rotation_nonexistent_policy(self):
        result = self.rotation.execute_rotation("no-such-id")
        assert result.success is False
        assert "not found" in result.error

    def test_execute_rotation_with_generator(self):
        self.vault.put("svc/key", "initial")
        policy = self.rotation.add_policy("svc/key")
        self.rotation.register_generator("svc/key", lambda: "generated-value-xyz")

        result = self.rotation.execute_rotation(policy.policy_id)
        assert result.success is True
        assert self.vault.get_value("svc/key") == "generated-value-xyz"

    def test_execute_rotation_auto_generates(self):
        self.vault.put("svc/key", "initial")
        policy = self.rotation.add_policy("svc/key")

        result = self.rotation.execute_rotation(policy.policy_id)
        assert result.success is True
        new_val = self.vault.get_value("svc/key")
        assert new_val != "initial"
        assert len(new_val) == 32  # uuid hex

    def test_pre_post_hooks(self):
        hook_log = []
        self.vault.put("svc/key", "v1")
        policy = self.rotation.add_policy("svc/key")

        self.rotation.register_pre_hook("svc/key", lambda path, ver: hook_log.append(("pre", path, ver)))
        self.rotation.register_post_hook("svc/key", lambda path, ver: hook_log.append(("post", path, ver)))

        self.rotation.execute_rotation(policy.policy_id, new_value="v2")
        assert len(hook_log) == 2
        assert hook_log[0][0] == "pre"
        assert hook_log[1][0] == "post"

    def test_rotation_updates_policy_timestamps(self):
        self.vault.put("svc/key", "v1")
        policy = self.rotation.add_policy("svc/key", interval_hours=12)
        assert policy.last_rotated is None

        self.rotation.execute_rotation(policy.policy_id, new_value="v2")
        assert policy.last_rotated is not None
        assert policy.next_rotation > datetime.now(timezone.utc)

    def test_get_due_rotations_none_due(self):
        self.rotation.add_policy("svc/key", interval_hours=24)
        due = self.rotation.get_due_rotations()
        assert len(due) == 0

    def test_get_due_rotations_skips_disabled(self):
        policy = self.rotation.add_policy("svc/key", enabled=False)
        policy.next_rotation = datetime.now(timezone.utc) - timedelta(hours=1)
        due = self.rotation.get_due_rotations()
        assert len(due) == 0

    def test_get_due_rotations_finds_overdue(self):
        policy = self.rotation.add_policy("svc/key")
        policy.next_rotation = datetime.now(timezone.utc) - timedelta(hours=1)
        due = self.rotation.get_due_rotations()
        assert len(due) == 1

    def test_get_rotation_history(self):
        self.vault.put("svc/key", "v1")
        policy = self.rotation.add_policy("svc/key")
        self.rotation.execute_rotation(policy.policy_id, new_value="v2")
        self.rotation.execute_rotation(policy.policy_id, new_value="v3")

        history = self.rotation.get_rotation_history()
        assert len(history) == 2
        assert history[0].success is True

    def test_get_rotation_history_by_path(self):
        self.vault.put("svc/a", "v1")
        self.vault.put("svc/b", "v1")
        p1 = self.rotation.add_policy("svc/a")
        p2 = self.rotation.add_policy("svc/b")
        self.rotation.execute_rotation(p1.policy_id, new_value="v2")
        self.rotation.execute_rotation(p2.policy_id, new_value="v2")

        history = self.rotation.get_rotation_history(key_path="svc/a")
        assert len(history) == 1

    def test_rotation_statistics(self):
        self.vault.put("svc/key", "v1")
        policy = self.rotation.add_policy("svc/key", RotationStrategy.SWAP)
        self.rotation.execute_rotation(policy.policy_id, new_value="v2")

        stats = self.rotation.get_statistics()
        assert stats["total_policies"] == 1
        assert stats["enabled_policies"] == 1
        assert stats["total_rotations"] == 1
        assert stats["successful_rotations"] == 1
        assert stats["failed_rotations"] == 0
        assert stats["by_strategy"]["swap"] == 1

    def test_rotation_statistics_empty(self):
        stats = self.rotation.get_statistics()
        assert stats["total_policies"] == 0
        assert stats["total_rotations"] == 0


# ── Access Control Tests ──────────────────────────────────────────────


class TestAccessControl:
    def setup_method(self):
        self.ac = AccessControl()

    def test_grant_creates_policy(self):
        policy = self.ac.grant("svc-trading", "broker/*", [AccessAction.READ])
        assert policy.subject_id == "svc-trading"
        assert policy.path_pattern == "broker/*"
        assert AccessAction.READ in policy.allowed_actions
        assert len(policy.policy_id) == 16

    def test_check_access_allowed(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        assert self.ac.check_access("svc-a", "broker/alpaca", AccessAction.READ) is True

    def test_check_access_denied_no_policy(self):
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.READ) is False

    def test_check_access_denied_wrong_action(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.DELETE) is False

    def test_check_access_denied_wrong_subject(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        assert self.ac.check_access("svc-b", "broker/key", AccessAction.READ) is False

    def test_check_access_denied_wrong_path(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        assert self.ac.check_access("svc-a", "db/password", AccessAction.READ) is False

    def test_glob_pattern_deep(self):
        self.ac.grant("admin", "**", [AccessAction.READ, AccessAction.WRITE, AccessAction.DELETE])
        assert self.ac.check_access("admin", "any/deep/path", AccessAction.READ) is True

    def test_glob_pattern_wildcard(self):
        self.ac.grant("svc", "broker/*/key", [AccessAction.READ])
        assert self.ac.check_access("svc", "broker/alpaca/key", AccessAction.READ) is True
        assert self.ac.check_access("svc", "broker/ib/key", AccessAction.READ) is True

    def test_expired_policy_denied(self):
        policy = self.ac.grant(
            "svc-a",
            "broker/*",
            [AccessAction.READ],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.READ) is False

    def test_future_expiry_allowed(self):
        self.ac.grant(
            "svc-a",
            "broker/*",
            [AccessAction.READ],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.READ) is True

    def test_revoke(self):
        policy = self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        assert self.ac.revoke(policy.policy_id) is True
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.READ) is False

    def test_revoke_nonexistent(self):
        assert self.ac.revoke("no-such-id") is False

    def test_revoke_all(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        self.ac.grant("svc-a", "db/*", [AccessAction.READ])
        self.ac.grant("svc-b", "broker/*", [AccessAction.READ])

        count = self.ac.revoke_all("svc-a")
        assert count == 2
        assert self.ac.check_access("svc-a", "broker/key", AccessAction.READ) is False
        assert self.ac.check_access("svc-b", "broker/key", AccessAction.READ) is True

    def test_list_policies(self):
        self.ac.grant("svc-a", "a/*", [AccessAction.READ])
        self.ac.grant("svc-b", "b/*", [AccessAction.WRITE])

        all_policies = self.ac.list_policies()
        assert len(all_policies) == 2

    def test_list_policies_by_subject(self):
        self.ac.grant("svc-a", "a/*", [AccessAction.READ])
        self.ac.grant("svc-a", "b/*", [AccessAction.WRITE])
        self.ac.grant("svc-b", "c/*", [AccessAction.READ])

        filtered = self.ac.list_policies(subject_id="svc-a")
        assert len(filtered) == 2

    def test_get_effective_permissions(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        self.ac.grant("svc-a", "broker/alpaca/*", [AccessAction.WRITE, AccessAction.ROTATE])

        perms = self.ac.get_effective_permissions("svc-a", "broker/alpaca/key")
        assert AccessAction.READ in perms
        assert AccessAction.WRITE in perms
        assert AccessAction.ROTATE in perms

    def test_audit_log_recorded(self):
        self.ac.grant("svc-a", "broker/*", [AccessAction.READ])
        self.ac.check_access("svc-a", "broker/key", AccessAction.READ, secret_id="sec-1")

        log = self.ac.get_audit_log()
        assert len(log) == 1
        assert log[0].allowed is True
        assert log[0].requester_id == "svc-a"

    def test_audit_log_denied_recorded(self):
        self.ac.check_access("svc-x", "broker/key", AccessAction.READ)
        log = self.ac.get_audit_log()
        assert len(log) == 1
        assert log[0].allowed is False

    def test_audit_log_filter_subject(self):
        self.ac.check_access("svc-a", "a", AccessAction.READ)
        self.ac.check_access("svc-b", "b", AccessAction.READ)

        log = self.ac.get_audit_log(subject_id="svc-a")
        assert len(log) == 1

    def test_audit_log_filter_action(self):
        self.ac.grant("svc-a", "*", [AccessAction.READ, AccessAction.WRITE])
        self.ac.check_access("svc-a", "k", AccessAction.READ)
        self.ac.check_access("svc-a", "k", AccessAction.WRITE)

        log = self.ac.get_audit_log(action=AccessAction.READ)
        assert len(log) == 1

    def test_statistics(self):
        self.ac.grant("svc-a", "a/*", [AccessAction.READ])
        self.ac.grant("svc-b", "b/*", [AccessAction.WRITE])
        self.ac.check_access("svc-a", "a/key", AccessAction.READ)
        self.ac.check_access("svc-c", "x/key", AccessAction.DELETE)

        stats = self.ac.get_statistics()
        assert stats["total_policies"] == 2
        assert stats["unique_subjects"] == 2
        assert stats["total_audit_entries"] == 2
        assert stats["allowed_requests"] == 1
        assert stats["denied_requests"] == 1

    def test_statistics_empty(self):
        stats = self.ac.get_statistics()
        assert stats["total_policies"] == 0
        assert stats["total_audit_entries"] == 0

    def test_grant_with_description(self):
        policy = self.ac.grant("svc", "p/*", [AccessAction.READ], description="Read access for svc")
        assert policy.description == "Read access for svc"

    def test_check_access_with_ip(self):
        self.ac.grant("svc", "*", [AccessAction.READ])
        self.ac.check_access("svc", "key", AccessAction.READ, ip_address="10.0.0.1")
        log = self.ac.get_audit_log()
        assert log[0].ip_address == "10.0.0.1"


# ── Client Tests ──────────────────────────────────────────────────────


class TestSecretsClient:
    def setup_method(self):
        self.vault = SecretsVault(encryption_key="client-key")
        self.client = SecretsClient(
            vault=self.vault,
            cache_ttl_seconds=300,
            enable_env_fallback=True,
        )

    def test_get_secret_from_vault(self):
        self.vault.put("svc/key", "secret-value")
        assert self.client.get_secret("svc/key") == "secret-value"

    def test_get_secret_caches(self):
        self.vault.put("svc/key", "value-1")
        assert self.client.get_secret("svc/key") == "value-1"

        # Update vault directly
        self.vault.put("svc/key", "value-2")

        # Should still return cached value
        assert self.client.get_secret("svc/key") == "value-1"

    def test_get_secret_cache_hit(self):
        self.vault.put("svc/key", "val")
        self.client.get_secret("svc/key")  # miss
        self.client.get_secret("svc/key")  # hit

        stats = self.client.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_get_secret_nonexistent(self):
        assert self.client.get_secret("no/key") is None

    def test_get_secret_default(self):
        assert self.client.get_secret("no/key", default="fallback") == "fallback"

    def test_get_secret_env_fallback(self, monkeypatch):
        monkeypatch.setenv("SVC_API_KEY", "env-value-123")
        value = self.client.get_secret("svc/api_key")
        assert value == "env-value-123"

    def test_get_secret_env_fallback_disabled(self, monkeypatch):
        monkeypatch.setenv("SVC_KEY", "env-val")
        client = SecretsClient(vault=self.vault, enable_env_fallback=False)
        assert client.get_secret("svc/key") is None

    def test_invalidate(self):
        self.vault.put("svc/key", "val")
        self.client.get_secret("svc/key")
        assert self.client.invalidate("svc/key") is True

        # After invalidation, should fetch from vault again
        self.vault.put("svc/key", "new-val")
        assert self.client.get_secret("svc/key") == "new-val"

    def test_invalidate_nonexistent(self):
        assert self.client.invalidate("no/key") is False

    def test_invalidate_all(self):
        self.vault.put("a", "1")
        self.vault.put("b", "2")
        self.client.get_secret("a")
        self.client.get_secret("b")

        count = self.client.invalidate_all()
        assert count == 2

    def test_refresh(self):
        self.vault.put("svc/key", "original")
        self.client.get_secret("svc/key")

        self.vault.put("svc/key", "updated")
        refreshed = self.client.refresh("svc/key")
        assert refreshed == "updated"

    def test_refresh_nonexistent(self):
        assert self.client.refresh("no/key") is None

    def test_get_cache_stats(self):
        self.vault.put("k", "v")
        self.client.get_secret("k")  # miss
        self.client.get_secret("k")  # hit
        self.client.get_secret("k")  # hit

        stats = self.client.get_cache_stats()
        assert stats["cache_size"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] > 0.6

    def test_cache_stats_empty(self):
        stats = self.client.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_cache_ttl(self):
        client = SecretsClient(vault=self.vault, cache_ttl_seconds=0)
        self.vault.put("svc/key", "val")

        # TTL=0 means immediate expiry; every get is a miss
        client.get_secret("svc/key")
        client.get_secret("svc/key")
        stats = client.get_cache_stats()
        assert stats["misses"] == 2
        assert stats["hits"] == 0

    def test_env_fallback_counter(self, monkeypatch):
        monkeypatch.setenv("SVC_KEY", "env-val")
        self.client.get_secret("svc/key")
        stats = self.client.get_cache_stats()
        assert stats["env_fallbacks"] == 1

    def test_refresh_counter(self):
        self.vault.put("k", "v")
        self.client.get_secret("k")
        self.client.refresh("k")
        stats = self.client.get_cache_stats()
        assert stats["refreshes"] == 1


# ── Dataclass Tests ───────────────────────────────────────────────────


class TestDataclasses:
    def test_secret_entry_fields(self):
        entry = SecretEntry(
            secret_id="abc123",
            key_path="svc/key",
            encrypted_value="enc",
            secret_type=SecretType.API_KEY,
            version=1,
            owner_service="trading",
        )
        assert entry.secret_id == "abc123"
        assert entry.key_path == "svc/key"
        assert entry.secret_type == SecretType.API_KEY
        assert entry.version == 1
        assert entry.owner_service == "trading"
        assert entry.metadata == {}

    def test_secret_entry_defaults(self):
        entry = SecretEntry(
            secret_id="x", key_path="p", encrypted_value="e",
            secret_type=SecretType.GENERIC, version=1,
        )
        assert entry.expires_at is None
        assert entry.rotated_at is None
        assert entry.owner_service == ""

    def test_rotation_policy_fields(self):
        policy = RotationPolicy(
            policy_id="p1",
            key_path="svc/key",
            strategy=RotationStrategy.SWAP,
            interval_hours=12,
        )
        assert policy.policy_id == "p1"
        assert policy.strategy == RotationStrategy.SWAP
        assert policy.interval_hours == 12
        assert policy.enabled is True

    def test_rotation_result_fields(self):
        result = RotationResult(
            success=True,
            old_version=1,
            new_version=2,
            duration_seconds=0.05,
        )
        assert result.success is True
        assert result.error is None

    def test_access_policy_fields(self):
        policy = AccessPolicy(
            policy_id="ap1",
            subject_id="svc-a",
            path_pattern="broker/*",
            allowed_actions=[AccessAction.READ, AccessAction.LIST],
        )
        assert policy.subject_id == "svc-a"
        assert len(policy.allowed_actions) == 2

    def test_access_audit_entry_fields(self):
        entry = AccessAuditEntry(
            entry_id="ae1",
            secret_id="s1",
            requester_id="svc-a",
            action=AccessAction.READ,
            allowed=True,
            reason="granted",
        )
        assert entry.allowed is True
        assert entry.reason == "granted"

    def test_cache_entry_fields(self):
        ce = CacheEntry(
            value="secret-val",
            cached_at=time.time(),
            ttl_seconds=300,
            key_path="svc/key",
            version=3,
        )
        assert ce.value == "secret-val"
        assert ce.version == 3

    def test_vault_config_is_dataclass(self):
        cfg = VaultConfig()
        assert hasattr(cfg, "__dataclass_fields__")

    def test_rotation_policy_defaults(self):
        policy = RotationPolicy(
            policy_id="p1", key_path="k", strategy=RotationStrategy.MANUAL
        )
        assert policy.interval_hours == 24
        assert policy.grace_period_hours == 1
        assert policy.last_rotated is None
        assert policy.enabled is True
