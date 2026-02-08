"""Centralized key-value configuration store with history and namespaces."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import ConfigNamespace, ConfigValueType, ServiceConfig

logger = logging.getLogger(__name__)


@dataclass
class ConfigChange:
    """Record of a configuration change."""

    key: str
    old_value: Any
    new_value: Any
    changed_by: str = "system"
    changed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    reason: str = ""


@dataclass
class ConfigEntry:
    """A single configuration entry in the store."""

    key: str
    value: Any
    value_type: ConfigValueType = ConfigValueType.STRING
    namespace: ConfigNamespace = ConfigNamespace.SYSTEM
    description: str = ""
    is_sensitive: bool = False
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def display_value(self) -> str:
        """Return masked value for sensitive entries."""
        if self.is_sensitive:
            return "***MASKED***"
        return str(self.value)


class ConfigStore:
    """Thread-safe centralized configuration store.

    Supports namespaced keys, typed values, change history, and rollback.
    """

    def __init__(self, config: Optional[ServiceConfig] = None):
        self._config = config or ServiceConfig()
        self._entries: Dict[str, ConfigEntry] = {}
        self._history: List[ConfigChange] = []
        self._lock = threading.RLock()

    def set(
        self,
        key: str,
        value: Any,
        value_type: ConfigValueType = ConfigValueType.STRING,
        namespace: ConfigNamespace = ConfigNamespace.SYSTEM,
        description: str = "",
        is_sensitive: bool = False,
        changed_by: str = "system",
        reason: str = "",
    ) -> ConfigEntry:
        """Set a configuration value. Creates or updates the entry."""
        full_key = f"{namespace.value}.{key}"

        with self._lock:
            old_value = None
            if full_key in self._entries:
                old_value = self._entries[full_key].value

            entry = ConfigEntry(
                key=full_key,
                value=value,
                value_type=value_type,
                namespace=namespace,
                description=description,
                is_sensitive=is_sensitive,
            )
            if old_value is not None:
                entry.updated_at = datetime.now(timezone.utc)

            self._entries[full_key] = entry

            change = ConfigChange(
                key=full_key,
                old_value=old_value,
                new_value=value,
                changed_by=changed_by,
                reason=reason,
            )
            self._history.append(change)

            if len(self._history) > self._config.config_change_history_limit:
                self._history = self._history[
                    -self._config.config_change_history_limit :
                ]

            logger.info("Config set: %s (by %s)", full_key, changed_by)
            return entry

    def get(self, key: str, namespace: ConfigNamespace = ConfigNamespace.SYSTEM,
            default: Any = None) -> Any:
        """Get a configuration value by key and namespace."""
        full_key = f"{namespace.value}.{key}"
        with self._lock:
            entry = self._entries.get(full_key)
            if entry is None:
                return default
            return entry.value

    def get_entry(self, key: str,
                  namespace: ConfigNamespace = ConfigNamespace.SYSTEM) -> Optional[ConfigEntry]:
        """Get the full ConfigEntry object."""
        full_key = f"{namespace.value}.{key}"
        with self._lock:
            return self._entries.get(full_key)

    def get_typed(self, key: str, namespace: ConfigNamespace = ConfigNamespace.SYSTEM,
                  value_type: ConfigValueType = ConfigValueType.STRING,
                  default: Any = None) -> Any:
        """Get a configuration value with type coercion."""
        raw = self.get(key, namespace, default)
        if raw is None:
            return default
        try:
            if value_type == ConfigValueType.INTEGER:
                return int(raw)
            elif value_type == ConfigValueType.FLOAT:
                return float(raw)
            elif value_type == ConfigValueType.BOOLEAN:
                if isinstance(raw, bool):
                    return raw
                return str(raw).lower() in ("true", "1", "yes")
            return raw
        except (ValueError, TypeError):
            return default

    def delete(self, key: str,
               namespace: ConfigNamespace = ConfigNamespace.SYSTEM) -> bool:
        """Delete a configuration entry."""
        full_key = f"{namespace.value}.{key}"
        with self._lock:
            if full_key in self._entries:
                old = self._entries.pop(full_key)
                self._history.append(ConfigChange(
                    key=full_key, old_value=old.value, new_value=None,
                    reason="deleted",
                ))
                logger.info("Config deleted: %s", full_key)
                return True
            return False

    def list_keys(self, namespace: Optional[ConfigNamespace] = None) -> List[str]:
        """List all config keys, optionally filtered by namespace."""
        with self._lock:
            if namespace is None:
                return sorted(self._entries.keys())
            prefix = f"{namespace.value}."
            return sorted(k for k in self._entries if k.startswith(prefix))

    def get_namespace(self, namespace: ConfigNamespace) -> Dict[str, Any]:
        """Get all entries in a namespace as a flat dict."""
        with self._lock:
            prefix = f"{namespace.value}."
            return {
                k[len(prefix):]: e.value
                for k, e in self._entries.items()
                if k.startswith(prefix)
            }

    def get_history(self, key: Optional[str] = None,
                    limit: int = 50) -> List[ConfigChange]:
        """Get change history, optionally filtered by key."""
        with self._lock:
            history = self._history
            if key:
                history = [h for h in history if h.key == key]
            return list(reversed(history[-limit:]))

    def rollback(self, key: str) -> bool:
        """Rollback a key to its previous value."""
        with self._lock:
            key_history = [h for h in self._history if h.key == key]
            if len(key_history) < 2:
                return False
            prev = key_history[-2]
            if prev.old_value is None and key_history[-1].old_value is None:
                return False
            if key in self._entries:
                target_value = key_history[-1].old_value
                if target_value is None:
                    self._entries.pop(key, None)
                else:
                    self._entries[key].value = target_value
                    self._entries[key].updated_at = datetime.now(timezone.utc)
                self._history.append(ConfigChange(
                    key=key,
                    old_value=self._entries.get(key, ConfigEntry(key=key)).value
                    if key in self._entries else None,
                    new_value=target_value,
                    reason="rollback",
                ))
                logger.info("Config rolled back: %s", key)
                return True
            return False

    def count(self) -> int:
        """Return total number of config entries."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Clear all entries and history."""
        with self._lock:
            self._entries.clear()
            self._history.clear()
