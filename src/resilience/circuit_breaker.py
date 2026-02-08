"""Circuit breaker pattern implementation.

Provides fault isolation by monitoring failures and temporarily
disabling calls to failing services.

States:
  CLOSED  -> normal operation, calls pass through
  OPEN    -> failures exceeded threshold, calls rejected
  HALF_OPEN -> recovery testing, limited calls allowed
"""

import asyncio
import functools
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Type

from .config import CircuitBreakerConfig, CircuitState

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and rejects a call."""

    def __init__(self, name: str, remaining: float = 0.0):
        self.name = name
        self.remaining = remaining
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Recovery in {remaining:.1f}s."
        )


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Monitors function calls for failures and transitions between states
    to protect downstream services from cascading failures.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._rejected_calls = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = time.monotonic()
        self._lock = threading.Lock()
        self._half_open_calls = 0

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def rejected_calls(self) -> int:
        return self._rejected_calls

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def _check_state_transition(self) -> None:
        """Check if OPEN -> HALF_OPEN transition should occur."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0

        logger.info(
            "Circuit breaker '%s': %s -> %s",
            self._config.name,
            old_state.value,
            new_state.value,
        )

    def _can_execute(self) -> bool:
        """Check whether a call is allowed in the current state."""
        self._check_state_transition()

        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self._config.half_open_max_calls

        # OPEN
        return False

    def _record_success(self) -> None:
        """Record a successful call."""
        self._success_count += 1
        self._total_calls += 1

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self._config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, exc: Exception) -> None:
        """Record a failed call."""
        # Check if this exception is excluded
        for exc_type in self._config.excluded_exceptions:
            if isinstance(exc, exc_type):
                return

        self._failure_count += 1
        self._total_calls += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function through the circuit breaker (sync)."""
        with self._lock:
            if not self._can_execute():
                self._rejected_calls += 1
                remaining = max(
                    0.0,
                    self._config.recovery_timeout
                    - (time.monotonic() - self._last_failure_time),
                )
                raise CircuitBreakerOpen(self._config.name, remaining)

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            with self._lock:
                self._record_failure(exc)
            raise
        else:
            with self._lock:
                self._record_success()
            return result

    async def call_async(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute an async function through the circuit breaker."""
        with self._lock:
            if not self._can_execute():
                self._rejected_calls += 1
                remaining = max(
                    0.0,
                    self._config.recovery_timeout
                    - (time.monotonic() - self._last_failure_time),
                )
                raise CircuitBreakerOpen(self._config.name, remaining)

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            with self._lock:
                self._record_failure(exc)
            raise
        else:
            with self._lock:
                self._record_success()
            return result

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._rejected_calls = 0

    def get_metrics(self) -> Dict[str, Any]:
        """Return current metrics."""
        with self._lock:
            self._check_state_transition()
            return {
                "name": self._config.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_calls": self._total_calls,
                "rejected_calls": self._rejected_calls,
                "last_failure_time": self._last_failure_time,
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout": self._config.recovery_timeout,
            }


class CircuitBreakerRegistry:
    """Registry for managing named circuit breakers."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get an existing breaker or create a new one."""
        with self._lock:
            if name not in self._breakers:
                cfg = config or CircuitBreakerConfig(name=name)
                if cfg.name == "default":
                    cfg.name = name
                self._breakers[name] = CircuitBreaker(cfg)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a breaker by name, or None."""
        with self._lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a breaker by name. Returns True if removed."""
        with self._lock:
            return self._breakers.pop(name, None) is not None

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Return metrics for all breakers."""
        with self._lock:
            return {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            }

    @property
    def names(self) -> list:
        """Return list of registered breaker names."""
        with self._lock:
            return list(self._breakers.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._breakers)


# ── Module-level singleton registry ──────────────────────────────────

_default_registry = CircuitBreakerRegistry()


def get_registry() -> CircuitBreakerRegistry:
    """Return the default global registry."""
    return _default_registry


# ── Decorators ───────────────────────────────────────────────────────


def circuit_breaker(
    name: str = "default",
    config: Optional[CircuitBreakerConfig] = None,
    registry: Optional[CircuitBreakerRegistry] = None,
) -> Callable:
    """Decorator that wraps a function with a circuit breaker.

    Supports both sync and async functions.

    Usage:
        @circuit_breaker("my_service")
        def call_service():
            ...

        @circuit_breaker("my_async_service")
        async def call_async_service():
            ...
    """
    reg = registry if registry is not None else _default_registry

    def decorator(func: Callable) -> Callable:
        breaker = reg.get_or_create(name, config)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await breaker.call_async(func, *args, **kwargs)

            async_wrapper._circuit_breaker = breaker  # type: ignore[attr-defined]
            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                return breaker.call(func, *args, **kwargs)

            sync_wrapper._circuit_breaker = breaker  # type: ignore[attr-defined]
            return sync_wrapper

    return decorator
