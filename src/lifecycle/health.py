"""Health check registry with liveness/readiness/startup probes."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from .config import AppState, HealthStatus, LifecycleConfig, ProbeType

logger = logging.getLogger(__name__)


class DependencyCheck(Protocol):
    """Protocol for dependency health checks."""

    def check(self) -> bool:
        """Return True if the dependency is healthy."""
        ...

    @property
    def name(self) -> str:
        """Name of the dependency."""
        ...


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    response_time_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResponse:
    """Structured response from a health probe."""

    status: str  # "healthy" or "unhealthy"
    checks: Dict[str, Any] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "checks": self.checks,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp,
        }


class HealthCheckRegistry:
    """Registry for health checks with Kubernetes-compatible probe support."""

    def __init__(self, config: Optional[LifecycleConfig] = None):
        self.config = config or LifecycleConfig()
        self._checks: Dict[str, Callable[[], bool]] = {}
        self._dependency_checks: Dict[str, DependencyCheck] = {}
        self._start_time: float = time.time()
        self._app_state: AppState = AppState.STARTING
        self._last_results: Dict[str, HealthCheckResult] = {}

    @property
    def uptime_seconds(self) -> float:
        """Return seconds since registry was created."""
        return time.time() - self._start_time

    @property
    def app_state(self) -> AppState:
        """Current application state."""
        return self._app_state

    @app_state.setter
    def app_state(self, state: AppState) -> None:
        """Set the application state."""
        self._app_state = state

    def register_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a named health check function."""
        self._checks[name] = check_fn
        logger.info("Registered health check: %s", name)

    def unregister_check(self, name: str) -> bool:
        """Unregister a health check by name."""
        if name in self._checks:
            del self._checks[name]
            logger.info("Unregistered health check: %s", name)
            return True
        return False

    def register_dependency(self, dependency: DependencyCheck) -> None:
        """Register a dependency check implementing the DependencyCheck protocol."""
        self._dependency_checks[dependency.name] = dependency
        logger.info("Registered dependency check: %s", dependency.name)

    def unregister_dependency(self, name: str) -> bool:
        """Unregister a dependency by name."""
        if name in self._dependency_checks:
            del self._dependency_checks[name]
            return True
        return False

    def run_check(self, name: str) -> HealthCheckResult:
        """Run a single named health check."""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Check '{name}' not found",
            )
        start = time.monotonic()
        try:
            healthy = self._checks[name]()
            duration_ms = (time.monotonic() - start) * 1000
            status = HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY
            result = HealthCheckResult(
                name=name, status=status, response_time_ms=duration_ms
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=duration_ms,
                message=str(exc),
            )
        self._last_results[name] = result
        return result

    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        for name in self._checks:
            results[name] = self.run_check(name)
        return results

    def run_dependency_checks(self) -> Dict[str, bool]:
        """Run all dependency checks and return results."""
        results = {}
        for name, dep in self._dependency_checks.items():
            try:
                results[name] = dep.check()
            except Exception as exc:
                logger.error("Dependency check '%s' failed: %s", name, exc)
                results[name] = False
        return results

    def liveness_probe(self) -> ProbeResponse:
        """Kubernetes liveness probe -- is the process alive?"""
        # Liveness just checks that the process is not in STOPPED state
        is_alive = self._app_state != AppState.STOPPED
        return ProbeResponse(
            status="healthy" if is_alive else "unhealthy",
            checks={"process_alive": is_alive},
            uptime_seconds=self.uptime_seconds,
        )

    def readiness_probe(self) -> ProbeResponse:
        """Kubernetes readiness probe -- are all dependencies connected?"""
        if self._app_state != AppState.RUNNING:
            return ProbeResponse(
                status="unhealthy",
                checks={"app_state": self._app_state.value},
                uptime_seconds=self.uptime_seconds,
            )

        dep_results = self.run_dependency_checks()
        check_results = self.run_all_checks()

        all_deps_healthy = all(dep_results.values()) if dep_results else True
        all_checks_healthy = all(
            r.status == HealthStatus.HEALTHY for r in check_results.values()
        ) if check_results else True

        is_ready = all_deps_healthy and all_checks_healthy
        checks_dict = {}
        for name, healthy in dep_results.items():
            checks_dict[f"dep:{name}"] = healthy
        for name, result in check_results.items():
            checks_dict[f"check:{name}"] = result.status.value

        return ProbeResponse(
            status="healthy" if is_ready else "unhealthy",
            checks=checks_dict,
            uptime_seconds=self.uptime_seconds,
        )

    def startup_probe(self) -> ProbeResponse:
        """Kubernetes startup probe -- has initialization completed?"""
        is_started = self._app_state in (AppState.RUNNING, AppState.SHUTTING_DOWN)
        return ProbeResponse(
            status="healthy" if is_started else "unhealthy",
            checks={"initialization_complete": is_started, "state": self._app_state.value},
            uptime_seconds=self.uptime_seconds,
        )

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a comprehensive health status summary."""
        check_results = self.run_all_checks()
        dep_results = self.run_dependency_checks()

        healthy_count = sum(
            1 for r in check_results.values() if r.status == HealthStatus.HEALTHY
        )
        total_checks = len(check_results)
        all_healthy = healthy_count == total_checks and all(dep_results.values())

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "app_state": self._app_state.value,
            "uptime_seconds": self.uptime_seconds,
            "checks": {
                name: {
                    "status": r.status.value,
                    "response_time_ms": r.response_time_ms,
                    "message": r.message,
                }
                for name, r in check_results.items()
            },
            "dependencies": dep_results,
            "healthy_checks": healthy_count,
            "total_checks": total_checks,
        }

    def get_registered_checks(self) -> List[str]:
        """Return names of all registered checks."""
        return list(self._checks.keys())

    def get_registered_dependencies(self) -> List[str]:
        """Return names of all registered dependencies."""
        return list(self._dependency_checks.keys())

    def clear(self) -> None:
        """Clear all registered checks."""
        self._checks.clear()
        self._dependency_checks.clear()
        self._last_results.clear()
