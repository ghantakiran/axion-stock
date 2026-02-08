"""Configuration types and service config for centralized config management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ConfigNamespace(str, Enum):
    """Namespaces for organizing configuration entries."""

    TRADING = "trading"
    ML = "ml"
    RISK = "risk"
    API = "api"
    DATA = "data"
    SYSTEM = "system"
    BROKER = "broker"
    NOTIFICATION = "notification"


class ConfigValueType(str, Enum):
    """Supported configuration value types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    SECRET = "secret"


class Environment(str, Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class FeatureFlagType(str, Enum):
    """Types of feature flags."""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"


@dataclass
class ServiceConfig:
    """Configuration for the config service itself."""

    default_environment: Environment = Environment.DEVELOPMENT
    enable_feature_flags: bool = True
    enable_secrets: bool = True
    enable_validation: bool = True
    enable_hot_reload: bool = False
    secrets_encryption_key: Optional[str] = None
    config_change_history_limit: int = 100
    flag_default_value: bool = False
    namespaces: List[ConfigNamespace] = field(
        default_factory=lambda: list(ConfigNamespace)
    )
