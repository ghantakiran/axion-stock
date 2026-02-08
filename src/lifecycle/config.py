"""Configuration for application lifecycle management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class HealthStatus(str, Enum):
    """Health status of a component or the application."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ShutdownPhase(str, Enum):
    """Phases of a graceful shutdown sequence."""
    NOT_STARTED = "not_started"
    DRAIN_REQUESTS = "drain_requests"
    CLOSE_CONNECTIONS = "close_connections"
    RUN_HOOKS = "run_hooks"
    CLEANUP = "cleanup"
    COMPLETED = "completed"


class AppState(str, Enum):
    """Application lifecycle states."""
    STARTING = "starting"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class ProbeType(str, Enum):
    """Kubernetes-compatible health probe types."""
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


# Default timeout and interval constants
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30
DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS = 10
DEFAULT_DRAIN_TIMEOUT_SECONDS = 15
DEFAULT_HOOK_TIMEOUT_SECONDS = 10
DEFAULT_MAX_SHUTDOWN_RETRIES = 3


@dataclass
class LifecycleConfig:
    """Master configuration for application lifecycle management."""

    shutdown_timeout_seconds: int = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    health_check_interval_seconds: int = DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS
    drain_timeout_seconds: int = DEFAULT_DRAIN_TIMEOUT_SECONDS
    hook_timeout_seconds: int = DEFAULT_HOOK_TIMEOUT_SECONDS
    max_shutdown_retries: int = DEFAULT_MAX_SHUTDOWN_RETRIES
    enable_signal_handlers: bool = True
    enable_health_probes: bool = True
    service_name: str = "axion-platform"
    environment: str = "development"
    graceful_shutdown: bool = True
    registered_services: List[str] = field(default_factory=lambda: [
        "database", "cache", "broker", "websocket", "scheduler",
    ])
    probe_endpoints: Dict[str, str] = field(default_factory=lambda: {
        "liveness": "/health/live",
        "readiness": "/health/ready",
        "startup": "/health/startup",
    })
    metadata: Dict[str, str] = field(default_factory=dict)
