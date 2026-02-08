"""PRD-107: Application Lifecycle Management."""

from .config import (
    AppState,
    HealthStatus,
    LifecycleConfig,
    ProbeType,
    ShutdownPhase,
)
from .health import (
    DependencyCheck,
    HealthCheckRegistry,
    HealthCheckResult,
    ProbeResponse,
)
from .hooks import (
    Hook,
    HookRegistry,
    HookResult,
)
from .manager import (
    LifecycleEvent,
    LifecycleManager,
)
from .signals import SignalHandler

__all__ = [
    # Config
    "AppState",
    "HealthStatus",
    "LifecycleConfig",
    "ProbeType",
    "ShutdownPhase",
    # Health
    "DependencyCheck",
    "HealthCheckRegistry",
    "HealthCheckResult",
    "ProbeResponse",
    # Hooks
    "Hook",
    "HookRegistry",
    "HookResult",
    # Manager
    "LifecycleEvent",
    "LifecycleManager",
    # Signals
    "SignalHandler",
]
