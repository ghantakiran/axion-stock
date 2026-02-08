"""LifecycleManager singleton orchestrating startup/shutdown."""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import AppState, LifecycleConfig, ShutdownPhase
from .health import HealthCheckRegistry
from .hooks import HookRegistry, HookResult
from .signals import SignalHandler

logger = logging.getLogger(__name__)


@dataclass
class LifecycleEvent:
    """Record of a lifecycle event."""

    event_type: str
    service_name: str
    details: str = ""
    duration_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


class LifecycleManager:
    """Singleton manager orchestrating application startup and shutdown.

    Coordinates health checks, hooks, and signal handling to provide
    clean lifecycle management.
    """

    _instance: Optional["LifecycleManager"] = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[LifecycleConfig] = None) -> "LifecycleManager":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, config: Optional[LifecycleConfig] = None):
        if self._initialized:
            return
        self._initialized = True
        self.config = config or LifecycleConfig()
        self._state = AppState.STOPPED
        self._shutdown_phase = ShutdownPhase.NOT_STARTED
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self._events: List[LifecycleEvent] = []

        # Sub-components
        self.health_registry = HealthCheckRegistry(self.config)
        self.hook_registry = HookRegistry()
        self.signal_handler = SignalHandler()

        # Register shutdown callback with signal handler
        self.signal_handler.register_shutdown_callback(self._on_shutdown_signal)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._initialized = False
            cls._instance = None

    @property
    def state(self) -> AppState:
        """Current application state."""
        return self._state

    @property
    def shutdown_phase(self) -> ShutdownPhase:
        """Current shutdown phase."""
        return self._shutdown_phase

    @property
    def uptime_seconds(self) -> float:
        """Seconds the application has been running."""
        if self._start_time is None:
            return 0.0
        end = self._stop_time or time.time()
        return end - self._start_time

    @property
    def events(self) -> List[LifecycleEvent]:
        """All recorded lifecycle events."""
        return list(self._events)

    @property
    def is_running(self) -> bool:
        """Whether the application is in the RUNNING state."""
        return self._state == AppState.RUNNING

    @property
    def is_shutting_down(self) -> bool:
        """Whether the application is shutting down."""
        return self._state == AppState.SHUTTING_DOWN

    def _record_event(
        self, event_type: str, details: str = "", duration_ms: float = 0.0
    ) -> LifecycleEvent:
        """Record a lifecycle event."""
        event = LifecycleEvent(
            event_type=event_type,
            service_name=self.config.service_name,
            details=details,
            duration_ms=duration_ms,
        )
        self._events.append(event)
        logger.info("Lifecycle event: %s - %s", event_type, details)
        return event

    def startup(self) -> List[HookResult]:
        """Start the application lifecycle.

        Transitions to STARTING, runs startup hooks, then transitions to RUNNING.
        """
        if self._state not in (AppState.STOPPED,):
            logger.warning("Cannot start: current state is %s", self._state.value)
            return []

        start = time.monotonic()
        self._state = AppState.STARTING
        self.health_registry.app_state = AppState.STARTING
        self._start_time = time.time()
        self._stop_time = None
        self._record_event("startup_begin", "Application startup initiated")

        # Register signal handlers if enabled
        if self.config.enable_signal_handlers:
            try:
                self.signal_handler.register_signals()
            except Exception as exc:
                logger.warning("Could not register signal handlers: %s", exc)

        # Run startup hooks
        results = self.hook_registry.run_startup_hooks()
        failures = [r for r in results if not r.success]

        if failures:
            logger.error(
                "Startup had %d hook failures: %s",
                len(failures),
                [f.hook_name for f in failures],
            )
            self._record_event(
                "startup_partial",
                f"{len(failures)} hooks failed out of {len(results)}",
            )
        else:
            logger.info("All %d startup hooks completed successfully", len(results))

        # Transition to running
        duration_ms = (time.monotonic() - start) * 1000
        self._state = AppState.RUNNING
        self.health_registry.app_state = AppState.RUNNING
        self._record_event(
            "startup_complete",
            f"Startup completed in {duration_ms:.1f}ms",
            duration_ms=duration_ms,
        )
        return results

    def shutdown(self) -> List[HookResult]:
        """Initiate graceful shutdown.

        Transitions through shutdown phases: drain requests, close connections,
        run hooks, cleanup, completed.
        """
        if self._state == AppState.STOPPED:
            logger.warning("Already stopped")
            return []

        if self._state == AppState.SHUTTING_DOWN:
            logger.warning("Already shutting down")
            return []

        start = time.monotonic()
        self._state = AppState.SHUTTING_DOWN
        self.health_registry.app_state = AppState.SHUTTING_DOWN
        self._record_event("shutdown_begin", "Graceful shutdown initiated")

        # Phase 1: Drain requests
        self._shutdown_phase = ShutdownPhase.DRAIN_REQUESTS
        self._record_event("shutdown_phase", "Draining in-flight requests")
        logger.info("Shutdown phase: draining requests")

        # Phase 2: Close connections
        self._shutdown_phase = ShutdownPhase.CLOSE_CONNECTIONS
        self._record_event("shutdown_phase", "Closing connections")
        logger.info("Shutdown phase: closing connections")

        # Phase 3: Run shutdown hooks
        self._shutdown_phase = ShutdownPhase.RUN_HOOKS
        self._record_event("shutdown_phase", "Running shutdown hooks")
        results = self.hook_registry.run_shutdown_hooks()
        failures = [r for r in results if not r.success]
        if failures:
            logger.error(
                "Shutdown had %d hook failures: %s",
                len(failures),
                [f.hook_name for f in failures],
            )

        # Phase 4: Cleanup
        self._shutdown_phase = ShutdownPhase.CLEANUP
        self._record_event("shutdown_phase", "Running cleanup")

        # Restore signal handlers
        try:
            self.signal_handler.restore_signals()
        except Exception as exc:
            logger.warning("Error restoring signal handlers: %s", exc)

        # Phase 5: Completed
        self._shutdown_phase = ShutdownPhase.COMPLETED
        self._stop_time = time.time()
        duration_ms = (time.monotonic() - start) * 1000
        self._state = AppState.STOPPED
        self.health_registry.app_state = AppState.STOPPED
        self._record_event(
            "shutdown_complete",
            f"Shutdown completed in {duration_ms:.1f}ms",
            duration_ms=duration_ms,
        )
        return results

    def _on_shutdown_signal(self) -> None:
        """Called when a shutdown signal is received."""
        logger.warning("Shutdown signal received, initiating graceful shutdown")
        self._record_event("signal_received", "Shutdown signal received")
        if self._state == AppState.RUNNING:
            self.shutdown()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive lifecycle status."""
        return {
            "state": self._state.value,
            "shutdown_phase": self._shutdown_phase.value,
            "uptime_seconds": self.uptime_seconds,
            "service_name": self.config.service_name,
            "environment": self.config.environment,
            "event_count": len(self._events),
            "health": self.health_registry.get_status_summary() if self._state == AppState.RUNNING else {},
            "hooks": self.hook_registry.get_hook_count(),
            "signals": self.signal_handler.get_state(),
        }

    @staticmethod
    def generate_sample_events(count: int = 10) -> List[LifecycleEvent]:
        """Generate sample lifecycle events for dashboard display."""
        import random

        event_types = [
            "startup_begin", "startup_complete", "shutdown_begin",
            "shutdown_complete", "health_check", "signal_received",
            "hook_executed", "shutdown_phase",
        ]
        services = ["axion-platform", "data-pipeline", "ml-engine", "api-gateway"]
        events = []
        for i in range(count):
            events.append(
                LifecycleEvent(
                    event_type=random.choice(event_types),
                    service_name=random.choice(services),
                    details=f"Sample event #{i + 1}",
                    duration_ms=random.uniform(10, 5000),
                )
            )
        return events
