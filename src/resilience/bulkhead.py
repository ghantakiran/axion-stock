"""Bulkhead pattern implementation.

Limits concurrent execution to prevent resource exhaustion using
asyncio.Semaphore-based isolation.
"""

import asyncio
import functools
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from .config import BulkheadConfig

logger = logging.getLogger(__name__)


class BulkheadFull(Exception):
    """Raised when the bulkhead has no available slots."""

    def __init__(self, name: str, max_concurrent: int):
        self.name = name
        self.max_concurrent = max_concurrent
        super().__init__(
            f"Bulkhead '{name}' is full ({max_concurrent} concurrent slots used)."
        )


class Bulkhead:
    """Async semaphore-based bulkhead for concurrency limiting.

    Limits the number of concurrent executions to protect downstream
    services and shared resources.
    """

    def __init__(self, config: Optional[BulkheadConfig] = None):
        self._config = config or BulkheadConfig()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_count: int = 0
        self._total_accepted: int = 0
        self._total_rejected: int = 0
        self._lock = threading.Lock()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Lazy-initialize the semaphore (must be in async context)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        return self._semaphore

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def max_concurrent(self) -> int:
        return self._config.max_concurrent

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def total_accepted(self) -> int:
        return self._total_accepted

    @property
    def total_rejected(self) -> int:
        return self._total_rejected

    @property
    def available_slots(self) -> int:
        return self._config.max_concurrent - self._active_count

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute an async function within the bulkhead.

        Args:
            func: Async callable to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the function call.

        Raises:
            BulkheadFull: If no slot is available within the timeout.
        """
        sem = self._get_semaphore()

        try:
            acquired = await asyncio.wait_for(
                self._acquire(sem),
                timeout=self._config.timeout,
            )
        except asyncio.TimeoutError:
            with self._lock:
                self._total_rejected += 1
            raise BulkheadFull(self._config.name, self._config.max_concurrent)

        try:
            with self._lock:
                self._active_count += 1
                self._total_accepted += 1
            result = await func(*args, **kwargs)
            return result
        finally:
            with self._lock:
                self._active_count -= 1
            sem.release()

    async def _acquire(self, sem: asyncio.Semaphore) -> bool:
        """Acquire the semaphore."""
        await sem.acquire()
        return True

    def reset(self) -> None:
        """Reset metrics and semaphore."""
        self._semaphore = None
        self._active_count = 0
        self._total_accepted = 0
        self._total_rejected = 0

    def get_metrics(self) -> Dict[str, Any]:
        """Return current bulkhead metrics."""
        return {
            "name": self._config.name,
            "max_concurrent": self._config.max_concurrent,
            "active_count": self._active_count,
            "available_slots": self.available_slots,
            "total_accepted": self._total_accepted,
            "total_rejected": self._total_rejected,
            "timeout": self._config.timeout,
        }


class BulkheadRegistry:
    """Registry for managing named bulkheads."""

    def __init__(self):
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self, name: str, config: Optional[BulkheadConfig] = None
    ) -> Bulkhead:
        """Get an existing bulkhead or create a new one."""
        with self._lock:
            if name not in self._bulkheads:
                cfg = config or BulkheadConfig(name=name)
                if cfg.name == "default":
                    cfg.name = name
                self._bulkheads[name] = Bulkhead(cfg)
            return self._bulkheads[name]

    def get(self, name: str) -> Optional[Bulkhead]:
        """Get a bulkhead by name."""
        with self._lock:
            return self._bulkheads.get(name)

    def remove(self, name: str) -> bool:
        """Remove a bulkhead."""
        with self._lock:
            return self._bulkheads.pop(name, None) is not None

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Return metrics for all bulkheads."""
        with self._lock:
            return {
                name: bh.get_metrics()
                for name, bh in self._bulkheads.items()
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._bulkheads)


# ── Module-level singleton ───────────────────────────────────────────

_default_registry = BulkheadRegistry()


def get_bulkhead_registry() -> BulkheadRegistry:
    """Return the default global bulkhead registry."""
    return _default_registry


# ── Decorator ────────────────────────────────────────────────────────


def bulkhead(
    name: str = "default",
    config: Optional[BulkheadConfig] = None,
    registry: Optional[BulkheadRegistry] = None,
) -> Callable:
    """Decorator that wraps an async function with a bulkhead.

    Usage:
        @bulkhead("my_service", config=BulkheadConfig(max_concurrent=5))
        async def call_service():
            ...
    """
    reg = registry if registry is not None else _default_registry

    def decorator(func: Callable) -> Callable:
        bh = reg.get_or_create(name, config)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await bh.execute(func, *args, **kwargs)

        wrapper._bulkhead = bh  # type: ignore[attr-defined]
        return wrapper

    return decorator
