"""Centralized Configuration Management (PRD-111).

Provides feature flags, secrets management, environment-specific configs,
config validation, and a unified config store for the Axion platform.
"""

from .config import (
    ConfigNamespace,
    ConfigValueType,
    Environment,
    FeatureFlagType,
    ServiceConfig,
)
from .config_store import ConfigEntry, ConfigStore
from .environments import EnvironmentConfig, EnvironmentResolver
from .feature_flags import FeatureFlag, FeatureFlagService, FlagContext
from .secrets import Secret, SecretsManager
from .validators import (
    ConfigValidator,
    ValidationReport,
    ValidationRule,
    ValidationSeverity,
)

__all__ = [
    "ConfigEntry",
    "ConfigNamespace",
    "ConfigStore",
    "ConfigValidator",
    "ConfigValueType",
    "Environment",
    "EnvironmentConfig",
    "EnvironmentResolver",
    "FeatureFlag",
    "FeatureFlagService",
    "FeatureFlagType",
    "FlagContext",
    "Secret",
    "SecretsManager",
    "ServiceConfig",
    "ValidationReport",
    "ValidationRule",
    "ValidationSeverity",
]
