"""Tests for PRD-111: Centralized Configuration Management."""

from datetime import datetime, timedelta, timezone

from src.config_service.config import (
    ConfigNamespace,
    ConfigValueType,
    Environment,
    FeatureFlagType,
    ServiceConfig,
)
from src.config_service.config_store import ConfigEntry, ConfigStore
from src.config_service.environments import EnvironmentConfig, EnvironmentResolver
from src.config_service.feature_flags import (
    FeatureFlag,
    FeatureFlagService,
    FlagContext,
    FlagStatus,
)
from src.config_service.secrets import SecretsManager
from src.config_service.validators import (
    ConfigValidator,
    ValidationReport,
    ValidationRule,
    ValidationSeverity,
)


class TestServiceConfig:
    """Tests for service configuration."""

    def test_default_config(self):
        config = ServiceConfig()
        assert config.default_environment == Environment.DEVELOPMENT
        assert config.enable_feature_flags is True
        assert config.enable_secrets is True
        assert config.config_change_history_limit == 100

    def test_custom_config(self):
        config = ServiceConfig(
            default_environment=Environment.PRODUCTION,
            enable_hot_reload=True,
            config_change_history_limit=50,
        )
        assert config.default_environment == Environment.PRODUCTION
        assert config.enable_hot_reload is True

    def test_namespace_enum(self):
        assert ConfigNamespace.TRADING.value == "trading"
        assert ConfigNamespace.ML.value == "ml"
        assert ConfigNamespace.RISK.value == "risk"
        assert ConfigNamespace.API.value == "api"

    def test_value_type_enum(self):
        assert ConfigValueType.STRING.value == "string"
        assert ConfigValueType.INTEGER.value == "integer"
        assert ConfigValueType.BOOLEAN.value == "boolean"
        assert ConfigValueType.SECRET.value == "secret"

    def test_environment_enum(self):
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TESTING.value == "testing"

    def test_feature_flag_type_enum(self):
        assert FeatureFlagType.BOOLEAN.value == "boolean"
        assert FeatureFlagType.PERCENTAGE.value == "percentage"
        assert FeatureFlagType.USER_LIST.value == "user_list"


class TestConfigStore:
    """Tests for centralized config store."""

    def setup_method(self):
        self.store = ConfigStore()

    def test_set_and_get(self):
        self.store.set("max_positions", 100, namespace=ConfigNamespace.TRADING)
        val = self.store.get("max_positions", namespace=ConfigNamespace.TRADING)
        assert val == 100

    def test_get_missing_key_returns_default(self):
        val = self.store.get("nonexistent", default="fallback")
        assert val == "fallback"

    def test_get_entry(self):
        self.store.set("api_url", "http://localhost",
                       namespace=ConfigNamespace.API, description="API base URL")
        entry = self.store.get_entry("api_url", ConfigNamespace.API)
        assert entry is not None
        assert entry.description == "API base URL"
        assert entry.key == "api.api_url"

    def test_get_typed_integer(self):
        self.store.set("port", "8080", namespace=ConfigNamespace.API)
        val = self.store.get_typed("port", ConfigNamespace.API,
                                   ConfigValueType.INTEGER)
        assert val == 8080
        assert isinstance(val, int)

    def test_get_typed_boolean(self):
        self.store.set("debug", "true", namespace=ConfigNamespace.SYSTEM)
        val = self.store.get_typed("debug", ConfigNamespace.SYSTEM,
                                   ConfigValueType.BOOLEAN)
        assert val is True

    def test_get_typed_float(self):
        self.store.set("threshold", "0.95", namespace=ConfigNamespace.ML)
        val = self.store.get_typed("threshold", ConfigNamespace.ML,
                                   ConfigValueType.FLOAT)
        assert abs(val - 0.95) < 1e-9

    def test_get_typed_invalid_returns_default(self):
        self.store.set("bad", "not_a_number", namespace=ConfigNamespace.SYSTEM)
        val = self.store.get_typed("bad", ConfigNamespace.SYSTEM,
                                   ConfigValueType.INTEGER, default=42)
        assert val == 42

    def test_delete(self):
        self.store.set("temp", "value", namespace=ConfigNamespace.SYSTEM)
        assert self.store.delete("temp", ConfigNamespace.SYSTEM) is True
        assert self.store.get("temp", ConfigNamespace.SYSTEM) is None

    def test_delete_nonexistent(self):
        assert self.store.delete("nope", ConfigNamespace.SYSTEM) is False

    def test_list_keys(self):
        self.store.set("a", 1, namespace=ConfigNamespace.TRADING)
        self.store.set("b", 2, namespace=ConfigNamespace.TRADING)
        self.store.set("c", 3, namespace=ConfigNamespace.ML)
        keys = self.store.list_keys(ConfigNamespace.TRADING)
        assert len(keys) == 2
        assert "trading.a" in keys
        assert "trading.b" in keys

    def test_list_all_keys(self):
        self.store.set("x", 1, namespace=ConfigNamespace.TRADING)
        self.store.set("y", 2, namespace=ConfigNamespace.ML)
        keys = self.store.list_keys()
        assert len(keys) == 2

    def test_get_namespace(self):
        self.store.set("host", "localhost", namespace=ConfigNamespace.API)
        self.store.set("port", 8080, namespace=ConfigNamespace.API)
        ns = self.store.get_namespace(ConfigNamespace.API)
        assert ns == {"host": "localhost", "port": 8080}

    def test_change_history(self):
        self.store.set("key1", "v1", namespace=ConfigNamespace.SYSTEM,
                       changed_by="admin")
        self.store.set("key1", "v2", namespace=ConfigNamespace.SYSTEM,
                       changed_by="admin")
        history = self.store.get_history("system.key1")
        assert len(history) == 2
        assert history[0].new_value == "v2"
        assert history[1].new_value == "v1"

    def test_history_limit(self):
        config = ServiceConfig(config_change_history_limit=5)
        store = ConfigStore(config)
        for i in range(10):
            store.set(f"k{i}", i, namespace=ConfigNamespace.SYSTEM)
        history = store.get_history()
        assert len(history) <= 5

    def test_sensitive_entry_display(self):
        self.store.set("api_key", "sk-12345", namespace=ConfigNamespace.API,
                       is_sensitive=True)
        entry = self.store.get_entry("api_key", ConfigNamespace.API)
        assert entry.display_value == "***MASKED***"

    def test_count(self):
        self.store.set("a", 1, namespace=ConfigNamespace.SYSTEM)
        self.store.set("b", 2, namespace=ConfigNamespace.SYSTEM)
        assert self.store.count() == 2

    def test_clear(self):
        self.store.set("a", 1, namespace=ConfigNamespace.SYSTEM)
        self.store.clear()
        assert self.store.count() == 0


class TestFeatureFlagService:
    """Tests for feature flag management."""

    def setup_method(self):
        self.service = FeatureFlagService()

    def test_create_boolean_flag(self):
        flag = self.service.create_flag("dark_mode", enabled=True)
        assert flag.name == "dark_mode"
        assert flag.flag_type == FeatureFlagType.BOOLEAN
        assert flag.enabled is True
        assert flag.status == FlagStatus.ACTIVE

    def test_evaluate_boolean_enabled(self):
        self.service.create_flag("feature_x", enabled=True)
        assert self.service.evaluate("feature_x") is True

    def test_evaluate_boolean_disabled(self):
        self.service.create_flag("feature_y", enabled=False)
        assert self.service.evaluate("feature_y") is False

    def test_evaluate_unknown_flag_returns_default(self):
        assert self.service.evaluate("nonexistent") is False

    def test_evaluate_percentage_flag(self):
        self.service.create_flag(
            "new_ui", flag_type=FeatureFlagType.PERCENTAGE,
            enabled=True, percentage=100.0,
        )
        ctx = FlagContext(user_id="user_42")
        assert self.service.evaluate("new_ui", ctx) is True

    def test_evaluate_percentage_zero(self):
        self.service.create_flag(
            "zero_pct", flag_type=FeatureFlagType.PERCENTAGE,
            enabled=True, percentage=0.0,
        )
        ctx = FlagContext(user_id="user_42")
        assert self.service.evaluate("zero_pct", ctx) is False

    def test_evaluate_percentage_deterministic(self):
        self.service.create_flag(
            "det_flag", flag_type=FeatureFlagType.PERCENTAGE,
            enabled=True, percentage=50.0,
        )
        ctx = FlagContext(user_id="user_42")
        result1 = self.service.evaluate("det_flag", ctx)
        result2 = self.service.evaluate("det_flag", ctx)
        assert result1 == result2

    def test_evaluate_percentage_no_user(self):
        self.service.create_flag(
            "pct_no_user", flag_type=FeatureFlagType.PERCENTAGE,
            enabled=True, percentage=50.0,
        )
        assert self.service.evaluate("pct_no_user") is False

    def test_evaluate_user_list_flag(self):
        self.service.create_flag(
            "beta_users", flag_type=FeatureFlagType.USER_LIST,
            enabled=True, user_list=["alice", "bob"],
        )
        ctx_alice = FlagContext(user_id="alice")
        ctx_charlie = FlagContext(user_id="charlie")
        assert self.service.evaluate("beta_users", ctx_alice) is True
        assert self.service.evaluate("beta_users", ctx_charlie) is False

    def test_set_enabled(self):
        self.service.create_flag("toggle", enabled=False)
        self.service.set_enabled("toggle", True)
        assert self.service.evaluate("toggle") is True

    def test_set_percentage(self):
        self.service.create_flag(
            "rollout", flag_type=FeatureFlagType.PERCENTAGE,
            enabled=True, percentage=10.0,
        )
        self.service.set_percentage("rollout", 50.0)
        flag = self.service.get_flag("rollout")
        assert flag.percentage == 50.0

    def test_add_remove_user(self):
        self.service.create_flag(
            "whitelist", flag_type=FeatureFlagType.USER_LIST,
            enabled=True, user_list=["alice"],
        )
        self.service.add_user("whitelist", "bob")
        flag = self.service.get_flag("whitelist")
        assert "bob" in flag.user_list

        self.service.remove_user("whitelist", "alice")
        flag = self.service.get_flag("whitelist")
        assert "alice" not in flag.user_list

    def test_deprecate_flag(self):
        self.service.create_flag("old_feature", enabled=True)
        self.service.deprecate("old_feature")
        assert self.service.evaluate("old_feature") is False

    def test_archive_flag(self):
        self.service.create_flag("archived", enabled=True)
        self.service.archive("archived")
        flag = self.service.get_flag("archived")
        assert flag.status == FlagStatus.ARCHIVED
        assert flag.enabled is False

    def test_delete_flag(self):
        self.service.create_flag("temp_flag")
        assert self.service.delete("temp_flag") is True
        assert self.service.get_flag("temp_flag") is None

    def test_list_flags(self):
        self.service.create_flag("f1")
        self.service.create_flag("f2")
        self.service.create_flag("f3")
        flags = self.service.list_flags()
        assert len(flags) == 3

    def test_list_flags_by_status(self):
        self.service.create_flag("active1")
        self.service.create_flag("dep1")
        self.service.deprecate("dep1")
        active = self.service.list_flags(status=FlagStatus.ACTIVE)
        assert len(active) == 1

    def test_evaluation_log(self):
        self.service.create_flag("logged", enabled=True)
        self.service.evaluate("logged", FlagContext(user_id="user1"))
        log = self.service.get_evaluation_log("logged")
        assert len(log) == 1
        assert log[0]["flag"] == "logged"
        assert log[0]["result"] is True

    def test_clear(self):
        self.service.create_flag("x")
        self.service.clear()
        assert len(self.service.list_flags()) == 0


class TestSecretsManager:
    """Tests for secrets management."""

    def setup_method(self):
        self.manager = SecretsManager(encryption_key="test-key-123")

    def test_store_and_retrieve(self):
        self.manager.store("db_password", "super_secret_123")
        value = self.manager.retrieve("db_password")
        assert value == "super_secret_123"

    def test_retrieve_nonexistent(self):
        assert self.manager.retrieve("nope") is None

    def test_encryption_roundtrip(self):
        original = "api-key-with-special-chars!@#$%"
        self.manager.store("api_key", original)
        retrieved = self.manager.retrieve("api_key")
        assert retrieved == original

    def test_different_keys_different_encryption(self):
        mgr1 = SecretsManager(encryption_key="key1")
        mgr2 = SecretsManager(encryption_key="key2")
        mgr1.store("s1", "hello")
        mgr2.store("s2", "hello")
        s1 = mgr1._secrets["s1"].encrypted_value
        s2 = mgr2._secrets["s2"].encrypted_value
        assert s1 != s2

    def test_rotate_secret(self):
        self.manager.store("token", "old_token")
        assert self.manager.rotate("token", "new_token") is True
        assert self.manager.retrieve("token") == "new_token"

    def test_rotation_count(self):
        self.manager.store("key", "v1")
        self.manager.rotate("key", "v2")
        self.manager.rotate("key", "v3")
        meta = self.manager.get_metadata("key")
        assert meta["rotation_count"] == 2

    def test_rotate_nonexistent(self):
        assert self.manager.rotate("nope", "value") is False

    def test_delete_secret(self):
        self.manager.store("temp", "value")
        assert self.manager.delete("temp") is True
        assert self.manager.exists("temp") is False

    def test_exists(self):
        self.manager.store("exists_test", "value")
        assert self.manager.exists("exists_test") is True
        assert self.manager.exists("nope") is False

    def test_get_metadata(self):
        self.manager.store("meta_test", "value", description="Test secret",
                           tags={"env": "test"})
        meta = self.manager.get_metadata("meta_test")
        assert meta["name"] == "meta_test"
        assert meta["description"] == "Test secret"
        assert meta["tags"]["env"] == "test"
        assert meta["is_expired"] is False

    def test_expired_secret(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        self.manager.store("expired", "value", expires_at=past)
        meta = self.manager.get_metadata("expired")
        assert meta["is_expired"] is True

    def test_list_secrets(self):
        self.manager.store("a", "1")
        self.manager.store("b", "2")
        names = self.manager.list_secrets()
        assert names == ["a", "b"]

    def test_get_expired_list(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        self.manager.store("fresh", "v1")
        self.manager.store("old", "v2", expires_at=past)
        expired = self.manager.get_expired()
        assert "old" in expired
        assert "fresh" not in expired

    def test_access_log(self):
        self.manager.store("logged_secret", "value")
        self.manager.retrieve("logged_secret", accessed_by="admin")
        log = self.manager.get_access_log("logged_secret")
        assert len(log) == 1
        assert log[0].accessed_by == "admin"
        assert log[0].action == "read"

    def test_masked_value(self):
        self.manager.store("mask_test", "sensitive_data")
        secret = self.manager._secrets["mask_test"]
        assert secret.masked_value == "***ENCRYPTED***"

    def test_clear(self):
        self.manager.store("c", "v")
        self.manager.clear()
        assert len(self.manager.list_secrets()) == 0


class TestEnvironmentResolver:
    """Tests for environment configuration resolution."""

    def setup_method(self):
        self.resolver = EnvironmentResolver()

    def test_set_and_get_environment(self):
        self.resolver.set_environment(Environment.PRODUCTION)
        assert self.resolver.get_environment() == Environment.PRODUCTION

    def test_base_config(self):
        self.resolver.set_base({"app_name": "Axion", "debug": False})
        val = self.resolver.resolve("app_name")
        assert val == "Axion"

    def test_environment_override(self):
        self.resolver.set_base({"debug": False})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            values={"debug": True},
        ))
        self.resolver.set_environment(Environment.DEVELOPMENT)
        assert self.resolver.resolve("debug") is True

    def test_inheritance(self):
        self.resolver.set_base({"log_level": "INFO"})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.STAGING,
            values={"db_host": "staging-db"},
        ))
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.PRODUCTION,
            values={"db_host": "prod-db", "replicas": 3},
            inherits_from=Environment.STAGING,
        ))
        self.resolver.set_environment(Environment.PRODUCTION)
        assert self.resolver.resolve("db_host") == "prod-db"
        assert self.resolver.resolve("log_level") == "INFO"

    def test_resolve_all(self):
        self.resolver.set_base({"a": 1, "b": 2})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            values={"b": 20, "c": 30},
        ))
        self.resolver.set_environment(Environment.DEVELOPMENT)
        resolved = self.resolver.resolve_all()
        assert resolved == {"a": 1, "b": 20, "c": 30}

    def test_resolve_default(self):
        assert self.resolver.resolve("missing", default="fallback") == "fallback"

    def test_diff_environments(self):
        self.resolver.set_base({"shared": "same"})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            values={"db": "local", "shared": "same"},
        ))
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.PRODUCTION,
            values={"db": "prod", "shared": "same"},
        ))
        diff = self.resolver.diff(Environment.DEVELOPMENT, Environment.PRODUCTION)
        assert "db" in diff
        assert diff["db"]["development"] == "local"
        assert diff["db"]["production"] == "prod"
        assert "shared" not in diff

    def test_validate_environment(self):
        self.resolver.set_base({"db_host": "localhost"})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.PRODUCTION,
            values={"api_key": "prod-key"},
        ))
        report = self.resolver.validate_environment(
            Environment.PRODUCTION,
            required_keys=["db_host", "api_key", "secret"],
        )
        assert report["valid"] is False
        assert "secret" in report["missing"]
        assert "db_host" in report["present"]

    def test_list_environments(self):
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
        ))
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.PRODUCTION,
        ))
        envs = self.resolver.list_environments()
        assert len(envs) == 2

    def test_get_environment_config(self):
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.STAGING,
            values={"key": "val"},
            description="Staging env",
        ))
        config = self.resolver.get_environment_config(Environment.STAGING)
        assert config is not None
        assert config.description == "Staging env"

    def test_environment_config_has(self):
        ec = EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
            values={"key1": "val1"},
        )
        assert ec.has("key1") is True
        assert ec.has("key2") is False

    def test_clear(self):
        self.resolver.set_base({"a": 1})
        self.resolver.register_environment(EnvironmentConfig(
            environment=Environment.DEVELOPMENT,
        ))
        self.resolver.clear()
        assert len(self.resolver.list_environments()) == 0


class TestConfigValidator:
    """Tests for config validation."""

    def setup_method(self):
        self.validator = ConfigValidator()
        self.store = ConfigStore()

    def test_required_key_present(self):
        self.store.set("host", "localhost", namespace=ConfigNamespace.API)
        self.validator.add_rule(ValidationRule(
            rule_id="R001", key="host",
            namespace=ConfigNamespace.API, required=True,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is True
        assert report.error_count == 0

    def test_required_key_missing(self):
        self.validator.add_rule(ValidationRule(
            rule_id="R002", key="db_url",
            namespace=ConfigNamespace.DATA, required=True,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is False
        assert report.error_count == 1

    def test_type_check_pass(self):
        self.store.set("port", 8080, namespace=ConfigNamespace.API)
        self.validator.add_rule(ValidationRule(
            rule_id="R003", key="port",
            namespace=ConfigNamespace.API, value_type=int,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is True

    def test_type_check_fail(self):
        self.store.set("port", "not_a_number", namespace=ConfigNamespace.API)
        self.validator.add_rule(ValidationRule(
            rule_id="R004", key="port",
            namespace=ConfigNamespace.API, value_type=int,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is False

    def test_min_value(self):
        self.store.set("workers", 0, namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R005", key="workers",
            namespace=ConfigNamespace.SYSTEM, min_value=1,
        ))
        report = self.validator.validate(self.store)
        assert report.error_count == 1

    def test_max_value(self):
        self.store.set("timeout", 1000, namespace=ConfigNamespace.API)
        self.validator.add_rule(ValidationRule(
            rule_id="R006", key="timeout",
            namespace=ConfigNamespace.API, max_value=300,
        ))
        report = self.validator.validate(self.store)
        assert report.error_count == 1

    def test_allowed_values(self):
        self.store.set("log_level", "TRACE", namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R007", key="log_level",
            namespace=ConfigNamespace.SYSTEM,
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"],
        ))
        report = self.validator.validate(self.store)
        assert report.error_count == 1

    def test_allowed_values_pass(self):
        self.store.set("log_level", "INFO", namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R008", key="log_level",
            namespace=ConfigNamespace.SYSTEM,
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR"],
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is True

    def test_custom_validator(self):
        self.store.set("email", "invalid", namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R009", key="email",
            namespace=ConfigNamespace.SYSTEM,
            custom_validator=lambda v: "@" in v,
        ))
        report = self.validator.validate(self.store)
        assert report.error_count == 1

    def test_custom_validator_pass(self):
        self.store.set("email", "admin@axion.com",
                       namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R010", key="email",
            namespace=ConfigNamespace.SYSTEM,
            custom_validator=lambda v: "@" in v,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is True

    def test_custom_validator_exception(self):
        self.store.set("bad", "value", namespace=ConfigNamespace.SYSTEM)
        self.validator.add_rule(ValidationRule(
            rule_id="R011", key="bad",
            namespace=ConfigNamespace.SYSTEM,
            custom_validator=lambda v: 1 / 0,
        ))
        report = self.validator.validate(self.store)
        assert report.error_count == 1

    def test_report_summary(self):
        self.validator.add_rule(ValidationRule(
            rule_id="R012", key="missing",
            namespace=ConfigNamespace.SYSTEM, required=True,
        ))
        self.validator.add_rule(ValidationRule(
            rule_id="R013", key="also_missing",
            namespace=ConfigNamespace.SYSTEM, required=True,
            severity=ValidationSeverity.WARNING,
        ))
        report = self.validator.validate(self.store)
        summary = report.summary()
        assert summary["rules_checked"] == 2
        assert summary["errors"] == 1
        assert summary["warnings"] == 1

    def test_remove_rule(self):
        self.validator.add_rule(ValidationRule(
            rule_id="R014", key="x",
            namespace=ConfigNamespace.SYSTEM,
        ))
        assert self.validator.remove_rule("R014") is True
        assert len(self.validator.get_rules()) == 0

    def test_validation_issue_str(self):
        from src.config_service.validators import ValidationIssue
        issue = ValidationIssue(
            rule_id="R001", key="test.key",
            severity=ValidationSeverity.ERROR,
            message="Missing required key",
        )
        s = str(issue)
        assert "ERROR" in s
        assert "R001" in s

    def test_clear(self):
        self.validator.add_rule(ValidationRule(
            rule_id="R015", key="x",
            namespace=ConfigNamespace.SYSTEM,
        ))
        self.validator.clear()
        assert len(self.validator.get_rules()) == 0

    def test_multiple_rules(self):
        self.store.set("port", 8080, namespace=ConfigNamespace.API)
        self.store.set("host", "localhost", namespace=ConfigNamespace.API)
        self.validator.add_rule(ValidationRule(
            rule_id="R016", key="port",
            namespace=ConfigNamespace.API, value_type=int,
            min_value=1, max_value=65535,
        ))
        self.validator.add_rule(ValidationRule(
            rule_id="R017", key="host",
            namespace=ConfigNamespace.API, required=True,
        ))
        report = self.validator.validate(self.store)
        assert report.is_valid is True
        assert report.rules_checked == 2
        assert report.keys_validated == 2
