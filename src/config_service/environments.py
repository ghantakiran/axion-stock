"""Environment-specific configuration with inheritance and validation."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import Environment

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment.

    Supports inheritance: environment configs inherit from a base config
    and can override specific values.
    """

    environment: Environment
    values: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    inherits_from: Optional[Environment] = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value for this environment."""
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value for this environment."""
        self.values[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in this environment's config."""
        return key in self.values


class EnvironmentResolver:
    """Resolves configuration values across environments with inheritance.

    Environment configs can inherit from a base environment, allowing
    shared defaults with environment-specific overrides.
    """

    def __init__(self, current_environment: Environment = Environment.DEVELOPMENT):
        self._current = current_environment
        self._configs: Dict[Environment, EnvironmentConfig] = {}
        self._base_config: Dict[str, Any] = {}

    def set_environment(self, environment: Environment) -> None:
        """Set the current active environment."""
        self._current = environment
        logger.info("Environment set to: %s", environment.value)

    def get_environment(self) -> Environment:
        """Get the current active environment."""
        return self._current

    def set_base(self, values: Dict[str, Any]) -> None:
        """Set base configuration that all environments inherit from."""
        self._base_config = dict(values)

    def register_environment(self, config: EnvironmentConfig) -> None:
        """Register an environment configuration."""
        self._configs[config.environment] = config
        logger.info("Environment registered: %s", config.environment.value)

    def resolve(self, key: str, default: Any = None,
                environment: Optional[Environment] = None) -> Any:
        """Resolve a config value with inheritance chain.

        Resolution order:
        1. Current environment's explicit values
        2. Inherited environment's values (if inherits_from is set)
        3. Base config values
        4. Default value
        """
        env = environment or self._current
        config = self._configs.get(env)

        if config is not None:
            if config.has(key):
                return config.get(key)
            if config.inherits_from is not None:
                parent = self._configs.get(config.inherits_from)
                if parent is not None and parent.has(key):
                    return parent.get(key)

        if key in self._base_config:
            return self._base_config[key]

        return default

    def resolve_all(self, environment: Optional[Environment] = None) -> Dict[str, Any]:
        """Resolve all config values for an environment, with inheritance applied."""
        env = environment or self._current
        result = dict(self._base_config)

        config = self._configs.get(env)
        if config is not None:
            if config.inherits_from is not None:
                parent = self._configs.get(config.inherits_from)
                if parent is not None:
                    result.update(parent.values)
            result.update(config.values)

        return result

    def get_environment_config(self, environment: Environment) -> Optional[EnvironmentConfig]:
        """Get the raw environment config."""
        return self._configs.get(environment)

    def list_environments(self) -> List[Environment]:
        """List all registered environments."""
        return sorted(self._configs.keys(), key=lambda e: e.value)

    def diff(self, env_a: Environment, env_b: Environment) -> Dict[str, Dict[str, Any]]:
        """Compare two environments and show differences.

        Returns a dict with keys that differ, showing the value in each environment.
        """
        vals_a = self.resolve_all(env_a)
        vals_b = self.resolve_all(env_b)

        all_keys = set(vals_a.keys()) | set(vals_b.keys())
        diff = {}
        for key in sorted(all_keys):
            va = vals_a.get(key)
            vb = vals_b.get(key)
            if va != vb:
                diff[key] = {env_a.value: va, env_b.value: vb}

        return diff

    def validate_environment(self, environment: Environment,
                             required_keys: List[str]) -> Dict[str, Any]:
        """Validate that an environment has all required keys.

        Returns a report with missing and present keys.
        """
        resolved = self.resolve_all(environment)
        missing = [k for k in required_keys if k not in resolved]
        present = [k for k in required_keys if k in resolved]

        return {
            "environment": environment.value,
            "valid": len(missing) == 0,
            "total_required": len(required_keys),
            "present": present,
            "missing": missing,
        }

    def clear(self) -> None:
        """Clear all environment configs."""
        self._configs.clear()
        self._base_config.clear()
