"""Hook registry for startup/shutdown callbacks with priority ordering."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .config import DEFAULT_HOOK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class Hook:
    """A registered lifecycle hook callback."""

    name: str
    callback: Callable
    priority: int = 100
    is_async: bool = False
    timeout_seconds: float = DEFAULT_HOOK_TIMEOUT_SECONDS
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.is_async and not asyncio.iscoroutinefunction(self.callback):
            raise ValueError(
                f"Hook '{self.name}' marked as async but callback is not a coroutine"
            )


@dataclass
class HookResult:
    """Result of executing a hook."""

    hook_name: str
    success: bool
    duration_ms: float = 0.0
    error: Optional[str] = None


class HookRegistry:
    """Registry for startup and shutdown hooks with priority ordering.

    Lower priority number = executed first.
    """

    def __init__(self):
        self._startup_hooks: List[Hook] = []
        self._shutdown_hooks: List[Hook] = []
        self._results: List[HookResult] = []

    @property
    def startup_hooks(self) -> List[Hook]:
        """Return startup hooks sorted by priority (lower first)."""
        return sorted(
            [h for h in self._startup_hooks if h.enabled],
            key=lambda h: h.priority,
        )

    @property
    def shutdown_hooks(self) -> List[Hook]:
        """Return shutdown hooks sorted by priority (lower first)."""
        return sorted(
            [h for h in self._shutdown_hooks if h.enabled],
            key=lambda h: h.priority,
        )

    @property
    def results(self) -> List[HookResult]:
        """Return all hook execution results."""
        return list(self._results)

    def register_startup_hook(
        self,
        name: str,
        callback: Callable,
        priority: int = 100,
        is_async: bool = False,
        timeout_seconds: float = DEFAULT_HOOK_TIMEOUT_SECONDS,
    ) -> Hook:
        """Register a startup hook."""
        hook = Hook(
            name=name,
            callback=callback,
            priority=priority,
            is_async=is_async,
            timeout_seconds=timeout_seconds,
        )
        self._startup_hooks.append(hook)
        logger.info("Registered startup hook '%s' with priority %d", name, priority)
        return hook

    def register_shutdown_hook(
        self,
        name: str,
        callback: Callable,
        priority: int = 100,
        is_async: bool = False,
        timeout_seconds: float = DEFAULT_HOOK_TIMEOUT_SECONDS,
    ) -> Hook:
        """Register a shutdown hook."""
        hook = Hook(
            name=name,
            callback=callback,
            priority=priority,
            is_async=is_async,
            timeout_seconds=timeout_seconds,
        )
        self._shutdown_hooks.append(hook)
        logger.info("Registered shutdown hook '%s' with priority %d", name, priority)
        return hook

    def unregister_startup_hook(self, name: str) -> bool:
        """Unregister a startup hook by name."""
        before = len(self._startup_hooks)
        self._startup_hooks = [h for h in self._startup_hooks if h.name != name]
        removed = len(self._startup_hooks) < before
        if removed:
            logger.info("Unregistered startup hook '%s'", name)
        return removed

    def unregister_shutdown_hook(self, name: str) -> bool:
        """Unregister a shutdown hook by name."""
        before = len(self._shutdown_hooks)
        self._shutdown_hooks = [h for h in self._shutdown_hooks if h.name != name]
        removed = len(self._shutdown_hooks) < before
        if removed:
            logger.info("Unregistered shutdown hook '%s'", name)
        return removed

    def _execute_hook(self, hook: Hook) -> HookResult:
        """Execute a single hook and return the result."""
        start = time.monotonic()
        try:
            if hook.is_async:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            hook.callback(), timeout=hook.timeout_seconds
                        )
                    )
                finally:
                    loop.close()
            else:
                hook.callback()
            duration_ms = (time.monotonic() - start) * 1000
            result = HookResult(
                hook_name=hook.name, success=True, duration_ms=duration_ms
            )
            logger.info(
                "Hook '%s' executed successfully in %.1fms",
                hook.name,
                duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            result = HookResult(
                hook_name=hook.name,
                success=False,
                duration_ms=duration_ms,
                error=str(exc),
            )
            logger.error("Hook '%s' failed: %s", hook.name, exc)
        self._results.append(result)
        return result

    def run_startup_hooks(self) -> List[HookResult]:
        """Run all enabled startup hooks in priority order."""
        results = []
        for hook in self.startup_hooks:
            result = self._execute_hook(hook)
            results.append(result)
        return results

    def run_shutdown_hooks(self) -> List[HookResult]:
        """Run all enabled shutdown hooks in priority order."""
        results = []
        for hook in self.shutdown_hooks:
            result = self._execute_hook(hook)
            results.append(result)
        return results

    def clear(self) -> None:
        """Clear all registered hooks and results."""
        self._startup_hooks.clear()
        self._shutdown_hooks.clear()
        self._results.clear()

    def get_hook_count(self) -> Dict[str, int]:
        """Return counts of registered hooks."""
        return {
            "startup": len(self._startup_hooks),
            "shutdown": len(self._shutdown_hooks),
        }
